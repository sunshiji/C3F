import os
import json
import torch
from PIL import Image
from torch import nn
from sklearn.metrics import confusion_matrix
import seaborn as sns
import matplotlib.pyplot as plt
from torchvision import datasets, transforms
from main_try import Star as create_model

def main():
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")

    # 确保数据预处理与训练时一致
    data_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ])

    # 加载类别标签
    json_path = 'classCVSI-2015_indices.json'
    assert os.path.exists(json_path), f"文件'{json_path}'不存在."
    with open(json_path, "r") as f:
        class_indict = json.load(f)

    model_weight_path = "/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/model_weight/star_wa_CVSI-2015_1_models/star_wa_CVSI-2015_1.pth"
    assert os.path.exists(model_weight_path), f"文件'{model_weight_path}'不存在."

    # 创建模型并加载权重
    model = create_model(out_planes=10).to(device)
    model.backbone.head = nn.Linear(in_features=model.backbone.head.in_features, out_features=10)
    model.backbone = model.backbone.to(device)
    model.load_state_dict(torch.load(model_weight_path, map_location=device), strict=False)
    model.eval()  # 进入验证模式

    # 加载测试数据集
    test_dir = "/home/szh/datasets/CVSI-2015_1/test"
    test_data = datasets.ImageFolder(root=test_dir, transform=data_transform)
    test_loader = torch.utils.data.DataLoader(test_data, batch_size=32, shuffle=False)

    # 初始化变量来跟踪准确率和收集混淆矩阵数据
    all_preds = []
    all_labels = []
    correct_predictions = 0
    total_predictions = 0

    # 遍历测试集
    with torch.no_grad():
        for images, labels in test_loader:
            images = images.to(device)
            labels = labels.to(device)

            # 预测类别
            output = model(images)
            predict = torch.softmax(output, dim=1)
            predicted_class = torch.argmax(predict, dim=1)

            # 收集预测和标签
            all_preds.extend(predicted_class.cpu().numpy())
            all_labels.extend(labels.cpu().numpy())

            # 检查预测是否正确
            correct_predictions += torch.sum(predicted_class == labels).item()
            total_predictions += labels.size(0)

    # 计算准确率
    accuracy = (correct_predictions / total_predictions) * 100
    print(f"总预测数量: {total_predictions}")
    print(f"正确预测数量: {correct_predictions}")
    print(f"准确率: {accuracy:.2f}%")

    # 生成混淆矩阵
    cm = confusion_matrix(all_labels, all_preds)
    # 归一化矩阵，用于着色（颜色反映准确性）
    cm_normalized = cm / cm.sum(axis=1, keepdims=True)

    print("混淆矩阵:\n", cm)

    # 获取按索引顺序排列的标签名列表
    idx_to_class = [class_indict[str(i)] for i in range(len(class_indict))]

    # 可视化混淆矩阵（匹配示例图片样式）
    plt.figure(figsize=(7, 5))  # 更紧凑的图像尺寸
    sns.heatmap(cm_normalized.T, annot=cm.T, fmt='d', cmap='Reds', cbar=True,
                xticklabels=idx_to_class, yticklabels=idx_to_class)
    plt.xlabel('True Labels')
    plt.ylabel('Predicted Labels')
    plt.title('Confusion Matrix')
    plt.xticks(rotation=45)
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig('/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/MLe2e.png')
    plt.show()


if __name__ == '__main__':
    main()
