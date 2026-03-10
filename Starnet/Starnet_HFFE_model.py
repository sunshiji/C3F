import torch
import torch.nn as nn
import torch.nn.functional as F
from starnet import starnet_s3
from thop import profile
from hffe_downsample import HFFE, HFFD, HAFNet, Res_block
from GMWTConvs import GMWTConvs
up_kwargs = {'mode': 'bilinear', 'align_corners': True}  # 当 'align_corners' 设置为 True 时，表示在进行插值时，输入图像的角点与输出图像的角点对齐。
print('up_kwargs:', up_kwargs)

class Star(nn.Module):
    def __init__(self, out_planes=4, encoder='starnet_s3'):  # out_planes=1表示输出通道数为1，即二分类问题
        super(Star, self).__init__()
        self.encoder = encoder  # encoder='swin_B'：定义所使用的编码器类型（Swin Transformer 或 PVT）。默认为 swin_B
        block = Res_block
        param_blocks = [2, 2, 2]  # 每个 stage 用多少个 block：都用 2 个
        if self.encoder == 'starnet_s3':
            param_channels = [32, 64, 128, 256]
            self.backbone = starnet_s3()
        else:
            raise ValueError(f"Unsupported encoder: {encoder}")

        c1, c2, c3, c4 = param_channels
        self.up = nn.Upsample(scale_factor=2, mode='bilinear',
                                    align_corners=True)  # 用于将特征图的分辨率扩大 2 倍，使用双线性插值法，并且 align_corners=True 保证角点对齐。
        self.downsample = nn.AvgPool2d(kernel_size=2, stride=2)  # 每次将空间尺寸减小2倍
        self.hfe1 = HFFE(c1, c2, c2, 1)
        self.hfe2 = HFFE(c2, c3, c3, 1)
        self.hfe3 = HFFE(c3, c4, c4, 1)
        # 解码器部分，通过卷积将特征图逐步从高维降到低维，最终得到输出的特征图（输出通道为 out_planes）。

        self.hfd3 = HFFD(c3, c4, c4, c3)
        self.hfd2 = HFFD(c2, c3, c3, c2)
        self.hfd1 = HFFD(c1, c2, c2, c1)
        self.GMWTConvs1 = GMWTConvs(32, 32)
        self.GMWTConvs2 = GMWTConvs(64, 64)
        self.GMWTConvs3 = GMWTConvs(128, 128)
        self.GMWTConvs4 = GMWTConvs(256, 256)
        self.conv_init = nn.Conv2d(3, param_channels[0], 1, 1)



        # self.middle_layer = self._make_layer(param_channels[2], param_channels[3], block, param_blocks[2])

        self.decoder_2 = nn.Sequential(nn.Conv2d(256, 128, 1, bias=False),
                                       nn.BatchNorm2d(128),
                                       nn.ReLU(inplace=True))
        self.decoder_1 = nn.Sequential(nn.Conv2d(128, 64, 1, bias=False),
                                       nn.BatchNorm2d(64),
                                       nn.ReLU(inplace=True))
        self.decoder_0 = nn.Sequential(nn.Conv2d(64, 128, kernel_size=3, stride=1, padding=1, bias=False),
                                       nn.BatchNorm2d(128),
                                       nn.ReLU(inplace=True),
                                       nn.Conv2d(128, 256, 1, bias=False),
                                       nn.BatchNorm2d(256),
                                       nn.ReLU(inplace=True),
                                      nn.Conv2d(256, out_planes, kernel_size=1, stride=1))
        # self.output_0 = nn.Conv2d(param_channels[0], 1, 1)  # 32
        # self.output_1 = nn.Conv2d(param_channels[1], 1, 1)  # 64
        # self.output_2 = nn.Conv2d(param_channels[2], 1, 1)  # 128
        # self.output_3 = nn.Conv2d(param_channels[3], 1, 1)  # 256

        # self.final = nn.Conv2d(4, 1, 3, 1, 1)
        # 把 4 个尺度的 mask（都上采样到同尺寸后）拼成 4 通道，再用 3×3 卷积融合成最终 1 通道输出。



        # self.decoder1 = nn.Sequential(nn.Conv2d(mutil_channel[0], 16, kernel_size=3, stride=1, padding=1, bias=False),
        #                               nn.ReLU(),
        #                               nn.Conv2d(16, out_planes, kernel_size=1, stride=1))

    def forward(self, x):
        x1, x2, x3, x4 = self.backbone(x)  # 得到多个尺度的特征图 x1, x2, x3, x4。
        # print(x1.shape, x2.shape, x3.shape, x4.shape)

        x_hfe1 = self.hfe1(x1, x2)
        x_hfe2 = self.hfe2(x2, x3)
        x_hfe3 = self.hfe3(x3, x4)

        # print("x_hfe1:", x_hfe1.shape, "x_hfe2:", x_hfe2.shape,"x_hfe3:", x_hfe3.shape, flush=True)

        x_hfd3 = self.hfd3(x3, x_hfe3, self.up(x4))

        x_d2 = self.decoder_2(torch.cat([x3, x_hfd3], 1))  # x_d3:[B,128,H/4,W/4]
        x_hfd2 = self.hfd2(x2, x_hfe2, self.up(x_d2))

        x_d1 = self.decoder_1(torch.cat([x2, x_hfd2], 1))  # x_d1:[B,64,H/2,W/2]

        x_hfd1 = self.hfd1(x1, x_hfe1, self.up(x_d1))

        x_d0 = self.decoder_0(torch.cat([x1, x_hfd1], 1))  # x_d0:[B,32,H,W]
        # print("x_hfd3:", x_hfd3.shape, "x_hfd2:", x_hfd2.shape, "x_hfd1:", x_hfd1.shape, flush=True)

        d1 = F.adaptive_avg_pool2d(x_d0, (1, 1))  # 全局平均池化，输出维度为 (B, C, 1, 1)

        d1 = torch.flatten(d1, 1)  # 压缩维度，输出维度为 (B, C)
        # d1 = d1.mean(dim=(2, 3))  # (B, C)

        return d1

# if __name__ == '__main__':
#
#     model = Star()
#     print(model)
#     x = torch.randn(1, 3, 224, 224)
#     output = model(x)
#
#     flops, params = profile(model, (x,)) # 用 profile 统计模型复杂度，flops：前向计算所需的 FLOPs（浮点运算次数，params：模型参数量（参数个数）
#
#     print("-" * 50) # 打印 50 个 - 作为分隔线，增强可读性。
#     print('FLOPs = ' + str(flops / 1000 ** 3) + ' G') # 把 FLOPs 换算成 “G”（十进制的 Giga，=10^9），并打印，输出单位是 GFLOPs（
#     print('Params = ' + str(params / 1000 ** 2) + ' M')

