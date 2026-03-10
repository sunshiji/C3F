import torch
import torch.nn as nn
from thop import profile
import torch.nn.functional as F
# import thop


def autopad(k, p=None, d=1):  # kernel, padding, dilation  给卷积层自动计算padding，让输出的空间尺寸尽量保持 “same”
    # Pad to 'same' shape outputs
    if d > 1:
        k = d * (k - 1) + 1 if isinstance(k, int) else [d * (x - 1) + 1 for x in k]  # actual kernel-size
    if p is None:
        p = k // 2 if isinstance(k, int) else [x // 2 for x in k]  # auto-pad
    return p


class h_sigmoid(nn.Module):
    def __init__(self, inplace=True):
        super(h_sigmoid, self).__init__()
        self.relu = nn.ReLU6(inplace=inplace)  # ReLU6(z) = min(max(z,0),6)

    def forward(self, x):
        return self.relu(x + 3) / 6

class h_swish(nn.Module):
    def __init__(self, inplace=True):
        super(h_swish, self).__init__()
        self.sigmoid = h_sigmoid(inplace=inplace)

    def forward(self, x):
        return x * self.sigmoid(x)


class CoordAttiton(nn.Module): # 坐标注意力
    # 分别沿 高度方向 和 宽度方向 做池化，得到两个“带位置信息”的注意力权重，再对输入做逐元素加权。
    def __init__(self, inp, oup, reduction=32):
        super(CoordAttiton, self).__init__()
        self.pool_h = nn.AdaptiveAvgPool2d((None, 1))
        self.pool_w = nn.AdaptiveAvgPool2d((1, None))

        mip = max(8, inp // reduction)

        self.conv1 = nn.Conv2d(inp, mip, kernel_size=1, stride=1, padding=0)
        self.bn1 = nn.BatchNorm2d(mip)
        self.act = h_swish()

        self.conv_h = nn.Conv2d(mip, oup, kernel_size=1, stride=1, padding=0)
        self.conv_w = nn.Conv2d(mip, oup, kernel_size=1, stride=1, padding=0)

    def forward(self, x):
        identity = x

        n, c, h, w = x.size()
        x_h = self.pool_h(x) # [N, C, H, 1]
        x_w = self.pool_w(x).permute(0, 1, 3, 2)   # pool_w: [N,C,1,W] -> permute -> [N,C,W,1]

        y = torch.cat([x_h, x_w], dim=2) #  [N, C, H+W, 1]
        y = self.conv1(y)
        y = self.bn1(y)
        y = self.act(y)

        x_h, x_w = torch.split(y, [h, w], dim=2) #  # x_h: [N,mip,H,1], x_w: [N,mip,W,1]
        x_w = x_w.permute(0, 1, 3, 2) # [N,mip,1,W]

        a_h = self.conv_h(x_h).sigmoid() # [N, oup, H, 1]
        a_w = self.conv_w(x_w).sigmoid() # [N, oup, 1, W]

        out = identity * a_w * a_h # 广播乘法 -> [N, C(or oup), H, W]

        return out
# CoordAtt：分别保留 H 和 W 的位置信息，能更好捕捉“长条结构/方向性”，同时计算量仍很轻。

class CBR(nn.Module):
    def __init__(self, c1, c2, k=1, s=1, p=None, g=1, d=1, act=True):
        super().__init__()
        self.conv = nn.Conv2d(c1, c2, k, s, autopad(k, p, d), groups=g, dilation=d, bias=False)
        self.bn = nn.BatchNorm2d(c2)
        self.act = nn.ReLU()
        # self.act = self.default_act if ahaoct is True else act if isinstance(act, nn.Module) else nn.Identity()

    def forward(self, x):
        x = self.conv(x)
        x = self.bn(x)
        x = self.act(x)
        return x

    def forward_fuse(self, x):# 推理加速
        return self.act(self.conv(x)) # 用于 BN 融合（BN Fusion）之后的推理


class ChannelAttention(nn.Module):
    def __init__(self, in_planes, ratio=16):
        super(ChannelAttention, self).__init__()
        self.avg_pool = nn.AdaptiveAvgPool2d(1)
        self.max_pool = nn.AdaptiveMaxPool2d(1)
        self.fc1   = nn.Conv2d(in_planes, in_planes // 16, 1, bias=False)
        self.relu1 = nn.ReLU()
        self.fc2   = nn.Conv2d(in_planes // 16, in_planes, 1, bias=False)
        self.sigmoid = nn.Sigmoid()
    def forward(self, x):
        res = x
        avg_out = self.fc2(self.relu1(self.fc1(self.avg_pool(x)))) # 平均池化得到的通道“打分”
        max_out = self.fc2(self.relu1(self.fc1(self.max_pool(x))))
        out = avg_out + max_out
        return self.sigmoid(out) * res # 把通道打分变成 0~1 的权重 w:[N,C,1,1]，再进行逐元素相乘

class SpatialAttention(nn.Module):
    def __init__(self, kernel_size=7):
        super(SpatialAttention, self).__init__()
        assert kernel_size in (3, 7), 'kernel size must be 3 or 7'
        padding = 3 if kernel_size == 7 else 1
        self.conv1 = nn.Conv2d(2, 1, kernel_size, padding=padding, bias=False)
        self.sigmoid = nn.Sigmoid()
    def forward(self, x):
        x_source = x
        avg_out = torch.mean(x, dim=1, keepdim=True) # 通道维度被压缩为 1
        max_out, _ = torch.max(x, dim=1, keepdim=True) # 计算每个通道的最大值。
        x = torch.cat([avg_out, max_out], dim=1) # [N, 2, H, W]
        x = self.conv1(x)
        return self.sigmoid(x) * x_source


def conv_relu_bn(in_channel, out_channel, dirate=1):
    return nn.Sequential(
        nn.Conv2d(
            in_channels=in_channel,
            out_channels=out_channel,
            kernel_size=3,
            stride=1,
            padding=dirate,
            dilation=dirate,
        ),
        nn.BatchNorm2d(out_channel),
        nn.ReLU(inplace=True),
    )



class Res_block(nn.Module):#用于捕捉特征并保留较低级别的特征信息。它结合了常规卷积层、空洞卷积、通道注意力和空间注意力，以增强模型的学习能力。
    def __init__(self, in_ch, out_ch, stride = 1):
        super(Res_block, self).__init__()
        self.conv_layer = nn.Sequential(
            conv_relu_bn(in_ch, in_ch, 1),
            conv_relu_bn(in_ch, out_ch, 1),
        )  # 定义常规卷积层（conv_layer），用来进行普通卷积操作。

        self.dconv_layer = nn.Sequential(
            conv_relu_bn(in_ch, in_ch, 2),
            conv_relu_bn(in_ch, out_ch, 4),
        ) # 定义空洞卷积层（dconv_layer），用于进行空洞卷积
        self.final_layer = conv_relu_bn(out_ch * 2, out_ch, 1)

        self.ca = ChannelAttention(out_ch)
        self.sa = SpatialAttention()

    def forward(self, x):
        conv_out = self.conv_layer(x)
        dconv_out = self.dconv_layer(x)
        out = torch.concat([conv_out,  dconv_out], dim=1)
        out = self.final_layer(out)
        out = self.ca(out)
        out = self.sa(out)
        return out



class HFFE(nn.Module):
    def __init__(self, feature_low_channel, feature_high_channel, out_channel, kernel_size):
        super(HFFE, self).__init__()
        self.conv_block_low = nn.Sequential(
            CBR(feature_low_channel, feature_low_channel // 16, kernel_size),
            nn.Conv2d(feature_low_channel // 16, 1, 1, padding=0),
            nn.Sigmoid()
        )

        self.conv_block_high = nn.Sequential(
            CBR(feature_high_channel, feature_high_channel // 16, kernel_size),
            nn.Conv2d(feature_high_channel // 16, 1, 1, padding=0),
            nn.Sigmoid()
        )
        # conv1、conv2、conv3 是用于进一步调整通道数的卷积层：
        self.conv1 = CBR(feature_low_channel, out_channel, 1)
        self.conv2 = CBR(feature_high_channel, out_channel, 1)
        self.conv3 = CBR(feature_low_channel + feature_high_channel, out_channel, 1)

        self.Up_to_2 = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)

        self.feature_low_sa = SpatialAttention() # 分别对低层次和高层次特征应用空间注意力，增强模型对空间重要区域的关注。
        self.feature_high_sa = SpatialAttention()

        self.ca = CoordAttiton(out_channel,out_channel) # 通道注意力模块，处理输出特征图（out_channel），增强通道间的相关性。

        self.conv_final = CBR(out_channel * 2, out_channel, 1) # # 融合增强后的高低特征

    def forward(self,x_low, x_high):
        b1, c1, w1, h1 = x_low.size()
        b2, c2, w2, h2 = x_high.size()
        if (w1, h1) != (w2, h2):
            x_high = self.Up_to_2(x_high)

        source_low = x_low
        source_high = x_high

        x_low = self.feature_low_sa(x_low)
        x_high = self.feature_high_sa(x_high)

        x_low_map = self.conv_block_low(x_low)
        x_high_map = self.conv_block_high(x_high)

        x_mix = torch.cat([source_low * x_high_map, source_high * x_low_map], 1)
        x_ca = torch.sigmoid(self.ca(self.conv3(x_mix)))


        x_low_att = x_ca * self.conv1((source_low + x_low))
        x_high_att = x_ca * self.conv2((source_high + x_high))

        out = self.conv_final(torch.cat([x_low_att, x_high_att], 1))

        return out


class HFFD(nn.Module): # 它主要结合了卷积、空洞卷积、特征拼接等多种技术，旨在通过多层次的特征融合和处理生成最终的输出。
    def __init__(self, inchannel_encode, inchannel_hfe, inchannel_decode, out_channel):
        super(HFFD, self).__init__()
        # inchannel_encode：编码器部分输入的通道数  # inchannel_hfe：与 HFE（可能是 Hybrid Feature Enhancement）相关的输入通道数
        # inchannel_decode：解码器部分输入的通道数。
        self.conv1 = nn.Conv2d(inchannel_encode, out_channel, kernel_size=1, stride=1, bias=True)
        self.conv2 = nn.Conv2d(inchannel_hfe, out_channel, kernel_size=1, stride=1, bias=True)
        self.conv3 = nn.Conv2d(inchannel_decode, out_channel, kernel_size=1, stride=1, bias=True)

        self.conv4 = nn.Conv2d(out_channel * 2, out_channel, kernel_size=1, stride=1, bias=True)

        self.layer_conv1 = CBR(out_channel * 2, out_channel, 1) # 这四个卷积层分别对拼接后的特征进行处理
        self.layer_conv2 = CBR(out_channel * 2, out_channel, 1)
        self.layer_conv3 = CBR(out_channel * 2, out_channel, 1)
        self.layer_conv4 = CBR(out_channel * 2, out_channel * 3, 1)

        # Dilation convolutions
        # 这些是空洞卷积层，使用不同的空洞率（dilation），以增加感受野而不增加计算量。
        self.layer_dil1 = nn.Sequential(
            nn.Conv2d(out_channel, out_channel, kernel_size=3, stride=1, padding=1, dilation=1, bias=True),
            nn.BatchNorm2d(out_channel),
            nn.ReLU()
        )
        self.layer_dil2 = nn.Sequential(
            nn.Conv2d(out_channel, out_channel, kernel_size=3, stride=1, padding=2, dilation=2, bias=True),
            nn.BatchNorm2d(out_channel),
            nn.ReLU()
        )
        self.layer_dil3 = nn.Sequential(
            nn.Conv2d(out_channel, out_channel, kernel_size=3, stride=1, padding=5, dilation=5, bias=True),
            nn.BatchNorm2d(out_channel),
            nn.ReLU()
        )
        # Concatenation and output layers
        # 来自空洞卷积的多个特征图拼接后，经过卷积和批量归一化，再应用 ReLU 激活。
        self.layer_cat = nn.Sequential(
            nn.Conv2d(out_channel * 3, out_channel, kernel_size=3, stride=1, padding=1, bias=True),
            nn.BatchNorm2d(out_channel),
            nn.ReLU()
        )
        self.layer_out = nn.Sequential(
            nn.Conv2d(out_channel * 3, out_channel, kernel_size=3, stride=1, padding=1, bias=True),
            nn.BatchNorm2d(out_channel),
            nn.ReLU()
        )

    def forward(self, x_e, x_hfe ,x_d):

        x_e = self.conv1(x_e)
        x_hfe = self.conv2(x_hfe)
        x_d = self.conv3(x_d)

        x = torch.cat((x_e, x_d),dim=1)

        x1 = self.layer_conv1(x)
        x2 = self.layer_conv2(x)
        x3 = self.layer_conv3(x)
        x4 = self.layer_conv4(x)

        # Apply dilated convolutions
        x_dil3 = self.layer_dil3(x3)
        x_dil2 = self.layer_dil2(x2 + x_dil3)
        x_dil1 = self.layer_dil1(x1 + x_dil2)

        # Concatenate the dilated features
        x_cat = torch.cat((x_dil3, x_dil2, x_dil1), dim=1)

        # Pass through the final layers and output
        out = self.layer_out(x_cat + x4)
        out = self.conv4(torch.cat((out, x_hfe), dim=1))

        return out




class HAFNet(nn.Module):
    def __init__(self,Train=False, in_channels=3):
        super().__init__()
        self.Train=Train # Train 控制 forward 最后返回什么：True：返回多尺度输出列表（用于训练/深监督），False：只返回最终输出
        block = Res_block
        param_channels = [32, 64, 128, 256] # 每个尺度的通道数
        param_blocks = [2, 2, 2] # 每个 stage 用多少个 block：都用 2 个
        self.pool = nn.MaxPool2d(2,2) # 2×2 最大池化，stride=2：把特征图 H、W 各减半。
        self.up = nn.Upsample(scale_factor=2, mode='bilinear', align_corners=True)
        self.up_4 = nn.Upsample(scale_factor=4, mode='bilinear', align_corners=True)
        self.up_8 = nn.Upsample(scale_factor=8, mode='bilinear', align_corners=True)
        self.up_16 = nn.Upsample(scale_factor=16, mode='bilinear', align_corners=True)

        self.hfe1 = HFFE(param_channels[0], param_channels[1], param_channels[1],1)
        self.hfe2 = HFFE(param_channels[1], param_channels[2], param_channels[2],1)
        self.hfe3 = HFFE(param_channels[2], param_channels[3], param_channels[3],1)



        self.hfd3 = HFFD(param_channels[2], param_channels[3], param_channels[3], param_channels[2])
        self.hfd2 = HFFD(param_channels[1], param_channels[2], param_channels[2], param_channels[1])
        self.hfd1 = HFFD(param_channels[0], param_channels[1], param_channels[1], param_channels[0])



        self.conv_init = nn.Conv2d(3, param_channels[0], 1, 1)

        self.encoder_0 = self._make_layer(param_channels[0], param_channels[0], block)
        self.encoder_1 = self._make_layer(param_channels[0], param_channels[1], block, param_blocks[0])
        self.encoder_2 = self._make_layer(param_channels[1], param_channels[2], block, param_blocks[1])

        self.middle_layer = self._make_layer(param_channels[2], param_channels[3], block, param_blocks[2])


        self.decoder_2 = self._make_layer(param_channels[3], param_channels[2], block,
                                          param_blocks[1])
        self.decoder_1 = self._make_layer(param_channels[2], param_channels[1], block,
                                          param_blocks[0])
        self.decoder_0 = self._make_layer(param_channels[1], param_channels[0], block)

        self.output_0 = nn.Conv2d(param_channels[0], 1, 1) #32
        self.output_1 = nn.Conv2d(param_channels[1], 1, 1) # 64
        self.output_2 = nn.Conv2d(param_channels[2], 1, 1) # 128
        self.output_3 = nn.Conv2d(param_channels[3], 1, 1) # 256


        self.final = nn.Conv2d(4, 1, 3, 1, 1)
        # 把 4 个尺度的 mask（都上采样到同尺寸后）拼成 4 通道，再用 3×3 卷积融合成最终 1 通道输出。

    def _make_layer(self, in_channels, out_channels, block, block_num=1):
        layer = []
        layer.append(block(in_channels, out_channels))
        for _ in range(block_num - 1):
            layer.append(block(out_channels, out_channels))
        return nn.Sequential(*layer)

    def forward(self, x):
        x_e0 = self.encoder_0(self.conv_init(x)) # encoder_0 输出 x_e0:[B,32,H,W]
        # print("x_e0:", x_e0.shape, flush=True)
        x_e1 = self.encoder_1(self.pool(x_e0)) # x_e1:[B,64,H/2,W/2]
        # print("x_e1:", x_e1.shape, flush=True)
        x_e2 = self.encoder_2(self.pool(x_e1)) # x_e2:[B,128,H/4,W/4]
        # print("x_e2:", x_e2.shape, flush=True)

        x_m = self.middle_layer(self.pool(x_e2)) # x_m:[B,256,H/8,W/8]
        # print("x_m:", x_m.shape, flush=True)
        x_hfe1 = self.hfe1(x_e0, x_e1) # 相邻层增强融合
        # print("x_hfe1:", x_hfe1.shape, flush=True)
        x_hfe2 = self.hfe2(x_e1, x_e2)
        # print("x_hfe2:", x_hfe2.shape, flush=True)
        x_hfe3 = self.hfe3(x_e2, x_m)
        print("x_hfe1:", x_hfe1.shape,"x_hfe2:", x_hfe2.shape,"x_hfe3:", x_hfe3.shape, flush=True)

        x_hfd3 = self.hfd3(x_e2,x_hfe3, self.up(x_m))
        x_d2 = self.decoder_2(torch.cat([x_e2, x_hfd3], 1)) # x_d3:[B,128,H/4,W/4]

        x_hfd2 = self.hfd2(x_e1,x_hfe2, self.up(x_d2))
        x_d1 = self.decoder_1(torch.cat([x_e1, x_hfd2], 1)) # x_d1:[B,64,H/2,W/2]

        x_hfd1 = self.hfd1(x_e0,x_hfe1, self.up(x_d1))

        x_d0 = self.decoder_0(torch.cat([x_e0, x_hfd1], 1)) # x_d0:[B,32,H,W]
        print("x_d2:", x_d2.shape,"x_d1:", x_d1.shape,"x_d0:", x_d0.shape, flush=True)
        print("x_hfd3:", x_hfd3.shape,"x_hfd2:", x_hfd2.shape,"x_hfd1:", x_hfd1.shape, flush=True)
        # 多尺度输出与最终融合
        mask0 = self.output_0(x_d0) # mask0:[B,1,H,W]
        mask1 = self.output_1(x_d1) # mask1:[B,1,H/2,W/2]
        mask2 = self.output_2(x_d2) # mask2:[B,1,H/4,W/4]
        mask3 = self.output_3(x_m) # mask3:[B,1,H/8,W/8]
        output = self.final(torch.cat([mask0, self.up(mask1), self.up_4(mask2), self.up_8(mask3)], dim=1))
        mask1 = F.interpolate(mask1, scale_factor=2, mode='bilinear', align_corners=True)
        mask2 = F.interpolate(mask2, scale_factor=4, mode='bilinear', align_corners=True)
        mask3 = F.interpolate(mask3, scale_factor=8, mode='bilinear', align_corners=True)
        # mask1/2/3 全部插值到 [B,1,H,W]，方便计算 loss

        if self.Train:
            return [torch.sigmoid(output),torch.sigmoid(mask0), torch.sigmoid(mask1), torch.sigmoid(mask2),
                    torch.sigmoid(mask3)] # 训练：返回 [final, mask0, mask1, mask2, mask3]（深监督）
        else:
            return torch.sigmoid(output) # 推理：只返回 final

#
if __name__ == '__main__':

    model = HAFNet(Train=True)
    print(model)
    x = torch.randn(1, 3, 56, 56)
    output = model(x)

    flops, params = profile(model, (x,)) # 用 profile 统计模型复杂度，flops：前向计算所需的 FLOPs（浮点运算次数，params：模型参数量（参数个数）

    print("-" * 50) # 打印 50 个 - 作为分隔线，增强可读性。
    print('FLOPs = ' + str(flops / 1000 ** 3) + ' G') # 把 FLOPs 换算成 “G”（十进制的 Giga，=10^9），并打印，输出单位是 GFLOPs（
    print('Params = ' + str(params / 1000 ** 2) + ' M')

    if len(output)>1:
        print([o.shape for o in output])


    else:
        print("Output shape:", output.shape)