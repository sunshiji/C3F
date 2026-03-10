import torch
import torch.nn as nn
import torch.nn.functional as F
from starnet import starnet_s3
# from starnet_original import starnet_s3
from thop import profile
from hffe_downsample import HFFE, HFFD

from EFC import EFC
from WA import WaveletAttention
from ACA import AdaptiveCoordAtt
up_kwargs = {'mode': 'bilinear', 'align_corners': True}  # 当 'align_corners' 设置为 True 时，表示在进行插值时，输入图像的角点与输出图像的角点对齐。
print('up_kwargs:', up_kwargs)


class Star(nn.Module):
    def __init__(self, out_planes=4, encoder='starnet_s3'):  # out_planes=1表示输出通道数为1，即二分类问题
        super(Star, self).__init__()
        self.encoder = encoder  # encoder='swin_B'：定义所使用的编码器类型（Swin Transformer 或 PVT）。默认为 swin_B

        if self.encoder == 'starnet_s3':
            param_channels = [32, 64, 128, 256]
            self.backbone = starnet_s3()
        else:
            raise ValueError(f"Unsupported encoder: {encoder}")

        c1, c2, c3, c4 = param_channels
        self.up = nn.Upsample(scale_factor=2, mode='bilinear',
                                    align_corners=True)  # 用于将特征图的分辨率扩大 2 倍，使用双线性插值法，并且 align_corners=True 保证角点对齐。
        self.downsample = nn.AvgPool2d(kernel_size=2, stride=2)  # 每次将空间尺寸减小2倍


        # 将通道数从32转换到64
        self.down_conv1 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True)
        )

        # 将通道数从32转换到128
        self.down_conv2 = nn.Sequential(
            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),  # stride=4，输出尺寸是 [1, 128, 14, 14]
            nn.BatchNorm2d(64),
            nn.ReLU(inplace=True),
            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),  # stride=4，输出尺寸是 [1, 128, 14, 14]
            nn.BatchNorm2d(128),
            nn.ReLU(inplace=True)
        )

        self.hfe1 = HFFE(c1, c2, c2, 1)
        self.hfe2 = HFFE(c2, c3, c3, 1)
        self.hfe3 = HFFE(c3, c4, c4, 1)
        # 解码器部分，通过卷积将特征图逐步从高维降到低维，最终得到输出的特征图（输出通道为 out_planes）。

        self.efc1 = EFC(64, 64)
        self.efc2 = EFC(128, 128)
        self.efc3 = EFC(256, 256)

        self.hfd3 = HFFD(c3, c4, c4, c3)
        self.hfd2 = HFFD(c2, c3, c3, c2)
        self.hfd1 = HFFD(c1, c2, c2, c1)
        self.wa1 = WaveletAttention(channels=3, use_fc=True)
        self.aca1 = AdaptiveCoordAtt(in_channels=256, reduction=16)
        self.aca2 = AdaptiveCoordAtt(in_channels=480, reduction=16)

        self.decoder_2 = nn.Sequential(nn.Conv2d(256, 128, 1, bias=False),
                                       nn.BatchNorm2d(128),
                                       nn.ReLU(inplace=True))
        self.decoder_1 = nn.Sequential(nn.Conv2d(128, 64, 1, bias=False),
                                       nn.BatchNorm2d(64),
                                       nn.ReLU(inplace=True))
        self.decoder_0 = nn.Sequential(nn.Conv2d(64, 32, kernel_size=1, bias=False),
                                       nn.BatchNorm2d(32),
                                       nn.ReLU(inplace=True))
        self.dropout = nn.Dropout(p=0.5)  # 0.2~0.5之间自己调
        self.fc = nn.Linear(480, out_planes)


    def forward(self, x):
        x1, x2, x3, x4 = self.backbone(self.wa1(x))

        x_hfe1 = self.hfe1(x1, x2)
        x_hfe2 = self.hfe2(x2, x3)
        x_hfe3 = self.hfe3(x3, x4)


        x_hfd3 = self.hfd3(x3, x_hfe3, self.up(x4))
        x_d2 = self.decoder_2(torch.cat([x3, x_hfd3], 1))  # x_d3:[B,128,H/4,W/4]
        x_hfd2 = self.hfd2(x2, x_hfe2, self.up(x_d2))
        x_d1 = self.decoder_1(torch.cat([x2, x_hfd2], 1))  # x_d1:[B,64,H/2,W/2]
        x_hfd1 = self.hfd1(x1, x_hfe1, self.up(x_d1))
        x_d0 = self.decoder_0(torch.cat([x1, x_hfd1], 1))  # x_d0:[B,32,H,W]

        k1 = self.down_conv1(x_d0)
        # print(k1.shape, flush=True)
        k2 = self.down_conv2(x_d0)

        # print(k1.shape,k2.shape,k3.shape,flush=True)
        e1 = self.efc1((k1,x_d1)) #[1,64,28,28]
        e2 = self.efc2((k2,x_d2)) #[1,128,14,14]
        x4 = self.aca1(x4)
        # e3 = self.efc3((k3,x4)) # [1,256,7,7]

        # 4. 多尺度特征聚合（使用自适应池化）
        e0_gap = F.adaptive_avg_pool2d(x_d0, (1, 1))
        e1_gap = F.adaptive_avg_pool2d(e1, (1, 1))
        e2_gap = F.adaptive_avg_pool2d(e2, (1, 1))
        e3_gap = F.adaptive_avg_pool2d(x4, (1, 1))

        concat_features = torch.cat([e0_gap, e1_gap, e2_gap, e3_gap], dim=1)
        concat_features = self.aca2(concat_features)
        # print("x_hfd3:", x_hfd3.shape, "x_hfd2:", x_hfd2.shape, "x_hfd1:", x_hfd1.shape, flush=True)

        # d1 = F.adaptive_avg_pool2d(x_d0, (1, 1))  # 全局平均池化，输出维度为 (B, C, 1, 1)
        d1 = torch.flatten(concat_features, 1)  # 压缩维度，输出维度为 (B, C)
        d1 = self.fc(self.dropout(d1))
        return d1



if __name__ == '__main__':

    model = Star()
    print(model)
    x = torch.randn(1, 3, 224, 224)
    output = model(x)

    flops, params = profile(model, (x,)) # 用 profile 统计模型复杂度，flops：前向计算所需的 FLOPs（浮点运算次数，params：模型参数量（参数个数）

    print("-" * 50) # 打印 50 个 - 作为分隔线，增强可读性。
    print('FLOPs = ' + str(flops / 1000 ** 3) + ' G') # 把 FLOPs 换算成 “G”（十进制的 Giga，=10^9），并打印，输出单位是 GFLOPs（
    print('Params = ' + str(params / 1000 ** 2) + ' M')


