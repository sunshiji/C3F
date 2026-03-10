import torch
import torch.nn as nn

from timm.layers import DropPath, trunc_normal_
from timm.models import register_model



class ConvBN(torch.nn.Sequential):
    def __init__(self, in_planes, out_planes, kernel_size=1, stride=1, padding=0, dilation=1, groups=1, with_bn=True):
        super().__init__()
        self.add_module('conv', torch.nn.Conv2d(in_planes, out_planes, kernel_size, stride, padding, dilation, groups))
        if with_bn:
            self.add_module('bn', torch.nn.BatchNorm2d(out_planes))
            torch.nn.init.constant_(self.bn.weight, 1)
            torch.nn.init.constant_(self.bn.bias, 0)


class Block(nn.Module):
    def __init__(self, dim, mlp_ratio=3, drop_path=0.):
        super().__init__()
        self.dwconv = ConvBN(dim, dim, 7, 1, (7 - 1) // 2, groups=dim, with_bn=True)
        self.f1 = ConvBN(dim, mlp_ratio * dim, 1, with_bn=False)
        self.f2 = ConvBN(dim, mlp_ratio * dim, 1, with_bn=False)
        self.g = ConvBN(mlp_ratio * dim, dim, 1, with_bn=True)
        self.dwconv2 = ConvBN(dim, dim, 7, 1, (7 - 1) // 2, groups=dim, with_bn=False)
        self.act = nn.ReLU6()
        self.drop_path = DropPath(drop_path) if drop_path > 0. else nn.Identity()

    def forward(self, x):
        input = x
        x = self.dwconv(x)
        x1, x2 = self.f1(x), self.f2(x)
        x = self.act(x1) * x2
        x = self.dwconv2(self.g(x))
        x = input + self.drop_path(x)
        return x


class StarNet(nn.Module):
    def __init__(self, base_dim=32, depths=[3, 3, 12, 5], mlp_ratio=4, drop_path_rate=0.0, num_classes=1000, out_indices=(0, 1, 2, 3), **kwargs):
        super().__init__()
        self.num_classes = num_classes
        self.out_indices = out_indices  # 输出层的索引
        self.in_channel = 32
        self.num_layers = len(depths)
        # stem layer
        self.stem = nn.Sequential(ConvBN(3, self.in_channel, kernel_size=3, stride=2, padding=1), nn.ReLU6())
        dpr = [x.item() for x in torch.linspace(0, drop_path_rate, sum(depths))] # stochastic depth
        # build stages
        self.stages = nn.ModuleList()
        cur = 0
        for i_layer in range(self.num_layers):
            embed_dim = base_dim * 2 ** i_layer
            down_sampler = ConvBN(self.in_channel, embed_dim, 3, 2, 1)
            self.in_channel = embed_dim
            blocks = [Block(self.in_channel, mlp_ratio, dpr[cur + i]) for i in range(depths[i_layer])]
            cur += depths[i_layer]
            self.stages.append(nn.Sequential(down_sampler, *blocks))
        # head
        self.norm = nn.BatchNorm2d(self.in_channel)
        self.avgpool = nn.AdaptiveAvgPool2d(1)
        self.head = nn.Linear(self.in_channel, num_classes)
        self.apply(self._init_weights)

    # def _init_weights(self, m):
    #     if isinstance(m, nn.Linear or nn.Conv2d):
    #         trunc_normal_(m.weight, std=.02)
    #         if isinstance(m, nn.Linear) and m.bias is not None:
    #             nn.init.constant_(m.bias, 0)
    #     elif isinstance(m, nn.LayerNorm or nn.BatchNorm2d):
    #         nn.init.constant_(m.bias, 0)
    #         nn.init.constant_(m.weight, 1.0)

    def _init_weights(self, m):
        if isinstance(m, (nn.Linear, nn.Conv2d)):
            trunc_normal_(m.weight, std=.02)
            if isinstance(m, nn.Linear) and m.bias is not None:
                nn.init.constant_(m.bias, 0)
        elif isinstance(m, (nn.LayerNorm, nn.BatchNorm2d)):
            if m.bias is not None:
                nn.init.constant_(m.bias, 0)
            if m.weight is not None:
                nn.init.constant_(m.weight, 1.0)

    # def forward(self, x):
    #     x = self.stem(x)
    #     for stage in self.stages:
    #         x = stage(x)
    #     # x = torch.flatten(self.avgpool(self.norm(x)), 1)
    #     # return self.head(x)
    #     return x
    def forward(self, x):
        x = self.stem(x)
        outs = []

        for i in range(self.num_layers):
            layer = self.stages[i]
            x = layer(x)  # 获取当前层的输出特征图 x_out 和传递到下一层的特征 x
            x_out = x
            if i in self.out_indices:  # 检查当前层是否需要输出特征（通过 self.out_indices 指定哪些层的输出需要保留）。
                outs.append(x_out)
        return tuple(outs)

# @register_model
# def starnet_s1(pretrained=False, **kwargs):
#     model = StarNet(24, [2, 2, 8, 3], **kwargs)
#
#     return model
#
#
# @register_model
# def starnet_s2(pretrained=False, **kwargs):
#     model = StarNet(32, [1, 2, 6, 2], **kwargs)
#
#     return model


@register_model
def starnet_s3(pretrained=False, **kwargs):
    model = StarNet(32, [2, 2, 8, 4], **kwargs)
    if pretrained:

        ckpt_path = "/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/starnet_s3.pth.tar"
        checkpoint = torch.load(ckpt_path, map_location="cpu")
        state_dict = checkpoint["state_dict"] if "state_dict" in checkpoint else checkpoint
        print(list(state_dict.keys())[:50])
        model.load_state_dict(checkpoint["state_dict"])


    return model


# @register_model
# def starnet_s4(pretrained=False, **kwargs):
#     model = StarNet(32, [3, 3, 12, 5], **kwargs)
#
#     return model
#
#
# # very small networks #
# @register_model
# def starnet_s050(pretrained=False, **kwargs):
#     return StarNet(16, [1, 1, 3, 1], 3, **kwargs)
#
#
# @register_model
# def starnet_s100(pretrained=False, **kwargs):
#     return StarNet(20, [1, 2, 4, 1], 4, **kwargs)
#
#
# @register_model
# def starnet_s150(pretrained=False, **kwargs):
#     return StarNet(24, [1, 2, 4, 2], 3, **kwargs)

if __name__ == '__main__':
    model = starnet_s3(pretrained=True)
    a = torch.randn(1, 3, 224, 224)
    model(a)
    print(model)