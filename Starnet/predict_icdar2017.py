import os
import json
import sys
import torch
from PIL import Image
from torch import nn
from torchvision import transforms
import numpy as np
from sklearn.manifold import TSNE
from matplotlib import pyplot as plt
# from torchsummary import summary

# from main_try import Star
from main_try import Star as create_model

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    data_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ])
    # load image
    # 指向需要遍历预测的图像文件夹
    imgs_root = r"/home/szh/datasets/ICDAR2017_1/test"
    # imgs_root1 = ""
    assert os.path.exists(imgs_root), f"file: '{imgs_root}' dose not exist."
    # print(imgs_root,imgs_root1)
    # imgs_root1 = os.path.join(imgs_root, imgs_root1)
    # 读取指定文件夹下所有jpg/png图像路径
    # img_path_list = [os.path.join(imgs_root, i) for i in os.listdir(imgs_root) if i.endswith(".jpg")]
    img_path_list = [os.path.join(imgs_root, i) for i in os.listdir(imgs_root) if i.endswith(".png")]
    # img_path_list1 = [os.path.join(imgs_root1, i) for i in os.listdir(imgs_root) if i.endswith(".jpg")]
    img_path_list1 = [os.path.basename(i) for i in os.listdir(imgs_root) if i.endswith(".png")]

    # read class_indict
    json_path = r'classICDAR2017_indices.json'
    assert os.path.exists(json_path), f"file: '{json_path}' dose not exist."

    json_file = open(json_path, "r")  # 打开json文件
    class_indict = json.load(json_file)  # 加载json文件

    # create model
    # model = Star(out_planes=7,encoder='starnet_s3').to(device)
    # load model weights
    weights_path = r"/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/model_weight/star_wa_ICDAR2017_1_models/star_wa_ICDAR2017_1.pth"  # 替换成你训练好的权重路径
    assert os.path.exists(weights_path), f"file: '{weights_path}' dose not exist."
    # model.load_state_dict(torch.load(weights_path, map_location=device),strict=False)
    # # 加载权重并过滤掉包含"head"的键
    # weights = torch.load(weights_path, map_location=device)
    # weights = {k: v for k, v in weights.items() if 'head' not in k}
    # model.load_state_dict(weights, strict=False)  # strict=False允许部分加载
    # # 删除原来的分类头部并重新定义
    # # del model.backbone.head  # 删除原有的分类头
    # model.backbone.head = torch.nn.Linear(in_features=model.backbone.head.in_features, out_features=7)
    # model = model.to(device)
    model = create_model(out_planes=7).to(device)
    model.backbone.head = nn.Linear(in_features=model.backbone.head.in_features, out_features=7)
    model.load_state_dict(torch.load(weights_path, map_location=device), strict=False)

    # prediction
    model.eval()
    batch_size = 1  # 每次预测时将多少张图片打包成一个batch
    img_feature = []  # 存储每个batch的特征
    img_class = []  # 存储每个batch的类别
    f = open(r'/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/ws_ICDAR2017.txt', 'a+')  # 打开一个文件用于写入结果
    with torch.no_grad():  # 在测试模式下进行预测
        for ids in range(0, len(img_path_list) // batch_size): #循环遍历图像路径列表,每次处理一个batch
            img_list = []  # 存储当前batch的图像
            # img_feature = []
            for img_path in img_path_list[ids * batch_size: (ids + 1) * batch_size]:  #遍历当前batch中的图像路径
                assert os.path.exists(img_path), f"file: '{img_path}' dose not exist."
                # print(img_path)
                img = Image.open(img_path)  #打开图像文件
                img = data_transform(img)  #对图像进行数据转换
                img_list.append(img)  #将转换后的图像添加到img_list列表中
            # batch img
            # 将img_list列表中的所有图像打包成一个batch
            batch_img = torch.stack(img_list, dim=0) #torch.stack() 会将这个列表中的所有张量沿着第0维（即批次维度）堆叠起来，形成一个形状为 [batch_size, C, H, W] 的张量
            output = model(batch_img.to(device)) #将这个batch的图像输入到模型中进行预测
            # 假设模型返回两个输出，分别处理
            # output = [out.cpu() for out in outputs]
            # predict class
            # output, output1 = model(batch_img.to(device)).cpu()
            img_feature.append(output)
            predict = torch.softmax(output, dim=1)
            probs, classes = torch.max(predict, dim=1)
            img_class.append(classes)

            # for idx, (pro, cla) in enumerate(zip(probs, classes)):
            #     print("image: {}  class: {}  prob: {:.3}".format(img_path_list[ids * batch_size + idx],
            #                                                      class_indict[str(cla.numpy())],
            #                                                      pro.numpy()))
            for idx, (pro, cla) in enumerate(zip(probs, classes)):
                print("{},{}".format(img_path_list1[ids * batch_size + idx], class_indict[str(cla.cpu().numpy())]))
                print("{},{}".format(img_path_list1[ids * batch_size + idx], class_indict[str(cla.cpu().numpy())]),
                      file=f)

            # for idx, (pro, cla) in enumerate(zip(probs, classes)):
            #     print("{},{}".format(img_path_list1[ids * batch_size + idx],class_indict[str(cla.numpy())]))
            #     print("{},{}".format(img_path_list1[ids * batch_size + idx],class_indict[str(cla.numpy())]),file=f)
    f.close()

if __name__ == '__main__':
    main()


