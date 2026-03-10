import os
import json
import torch
from matplotlib import pyplot as plt
from sklearn.metrics import precision_score, recall_score, f1_score
from torch import nn
from torchvision import datasets, transforms
from PIL import Image
from starnet_original import starnet_s3 as create_model


def main():
    device = torch.device("cuda:1" if torch.cuda.is_available() else "cpu")

    # 数据预处理（用于模型推理）
    data_transform = transforms.Compose([
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
    ])

    # 加载类别标签
    json_path = 'classCVSI-2015_indices.json'
    assert os.path.exists(json_path), f"文件'{json_path}'不存在."
    # with open(json_path, "r") as f:
    #     class_indict = json.load(f)

    # 创建模型并加载权重
    model_weight_path = "/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/model_weight/wshHmea_CVSI-2015_1_models/wshHmea_CVSI-2015_1.pth"
    assert os.path.exists(model_weight_path), f"文件'{model_weight_path}'不存在."

    model = create_model(out_planes=10).to(device)
    model.head = nn.Linear(model.head.in_features,10)
    model = model.to(device)
    model.load_state_dict(torch.load(model_weight_path, map_location=device), strict=False)
    model.eval()

    # 加载测试数据（包括图像路径）
    test_dir = "/home/szh/datasets/CVSI-2015_1/test"
    test_data = datasets.ImageFolder(root=test_dir)

    correct_predictions = 0
    total_predictions = 0
    incorrect_images = []
    all_preds = []
    all_labels = []

    # 遍历测试样本
    with torch.no_grad():
        for img_path, label in test_data.samples:
            original_img = Image.open(img_path).convert("RGB")
            img = data_transform(original_img).unsqueeze(0).to(device)

            output = model(img)
            predict = torch.softmax(output, dim=1)
            predicted_class = torch.argmax(predict, dim=1).item()
            # 添加到 all_preds 和 all_labels
            all_preds.append(predicted_class)
            all_labels.append(label)
            if predicted_class == label:
                correct_predictions += 1
            else:
                incorrect_images.append((original_img, predicted_class, label))

            total_predictions += 1

    # 准确率输出
    accuracy = (correct_predictions / total_predictions) * 100
    print(f"总预测数量: {total_predictions}")
    print(f"正确预测数量: {correct_predictions}")
    print(f"准确率: {accuracy:.2f}%")

    # 精确率、召回率和F1分数
    precision = precision_score(all_labels, all_preds, average='weighted')
    recall = recall_score(all_labels, all_preds, average='weighted')
    f1 = f1_score(all_labels, all_preds, average='weighted')

    print(f"精确率 (Precision): {precision:.4f}")
    print(f"召回率 (Recall): {recall:.4f}")
    print(f"F1分数 (F1-Score): {f1:.4f}")
    # # 显示预测错误图像
    # if incorrect_images:
    #     print("显示预测错误的图片：")
    #     for img, predicted_class, true_class in incorrect_images:
    #         plt.imshow(img)
    #         plt.title(f"预测: {class_indict[str(predicted_class)]}, 真实: {class_indict[str(true_class)]}")
    #         plt.axis('off')
    #         plt.show()


if __name__ == '__main__':
    main()
