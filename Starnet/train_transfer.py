import os
import sys
import json
import time
import random
import logging
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from matplotlib import pyplot as plt
from torch.utils.data import DataLoader
from torchtoolbox.transform import Cutout
from torchvision import transforms, datasets
from tqdm import tqdm
from torch.optim.lr_scheduler import CosineAnnealingLR  # 导入余弦退火调度器
from starnet_original import starnet_s3
from main import Star
def custom_loader(path):
    with Image.open(path) as img:
        if img.mode == 'P':  # 调色板模式
            if 'transparency' in img.info:
                img = img.convert("RGBA")

        elif img.mode in ("RGBA", "LA"):
            img = img.convert("RGBA")
        return img.convert("RGB")

# 设置种子训练模型
# 这段代码通过设置 Python、NumPy 和 PyTorch 的随机种子，并配置 CuDNN 的行为，确保训练过程的可复现性。
def setup_seed(seed):
    random.seed(seed)  # 为python设置随机种子
    np.random.seed(seed)  # 为numpy设置随机种子
    os.environ['PYTHONHASHSEED'] = str(seed)  # 固定 Python 内部的哈希随机化种子。
    torch.manual_seed(seed)  # 为CPU设置随机种子
    torch.cuda.manual_seed(seed)  # 为当前GPU设置随机种子
    torch.cuda.manual_seed_all(seed)  # 为所有GPU设置种子，生成随机数
    # 如果模型在多个 GPU 上运行，这两行代码可以确保所有 GPU 上的随机数生成一致。

    torch.backends.cudnn.deterministic = True  # CuDNN 是 NVIDIA 提供的深度学习库，设置 CuDNN 以确定性方式运行。
    torch.backends.cudnn.benchmark = False  # 关闭 CuDNN 的自动优化功能。
    # torch.backends.cudnn.enabled = False #完全禁用 CuDNN，在某些特殊场景下，禁用 CuDNN 可以避免潜在的不确定性问题，但会导致性能下降。
    torch.backends.cudnn.enabled = True
    os.environ['CUBLAS_WORKSPACE_CONFIG'] = ':16:8'
    # torch.use_deterministic_algorithms(False)
    torch.use_deterministic_algorithms(True, warn_only=True)

def setup_logging(log_dir):
    """设置日志记录"""
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "training.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",  # 只记录消息内容
        handlers=[
            logging.FileHandler(log_file),  # 输出到文件
            logging.StreamHandler(sys.stdout)  # 输出到控制台
        ]
    )
    logging.info("Logging setup complete. Log file: {}".format(log_file))
def main():

    # 设置日志目录
    log_dir = "/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/newlogs/wshHea_transfer_CVSI-2015_1_log"
    setup_logging(log_dir)
    device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
    print("using {} device.".format(device))
    data_transform = {
        "train": transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ColorJitter(brightness=.5, hue=.3),
            transforms.GaussianBlur(kernel_size=(5, 9), sigma=(0.1, 5)),
            Cutout(),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ]),
        "val": transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.5, 0.5, 0.5], [0.5, 0.5, 0.5])
        ])}


    data_root = os.path.abspath(os.path.join(os.getcwd(), "/home/szh/datasets"))  # get data root path
    image_path = os.path.join(data_root, "CVSI-2015_1")  # flower data set path
    assert os.path.exists(image_path), "{} path does not exist.".format(image_path)
    train_dataset = datasets.ImageFolder(root=os.path.join(image_path, "train"),
                                         loader=custom_loader,
                                         transform=data_transform["train"])
    train_num = len(train_dataset)

    # {'daisy':0, 'dandelion':1, 'roses':2, 'sunflower':3, 'tulips':4}
    language_list = train_dataset.class_to_idx
    cla_dict = dict((val, key) for key, val in language_list.items())
    # write dict into json file
    json_str = json.dumps(cla_dict, indent=4)  # 格式化输出json字符串
    with open('class_indices.json', 'w') as json_file:
        json_file.write(json_str)

    batch_size = 16
    nw = min([os.cpu_count(), batch_size if batch_size > 1 else 0, 8])  # number of workers
    logging.info('Using {} dataloader workers every process'.format(nw))

    train_loader = DataLoader(train_dataset,
                              batch_size=batch_size, shuffle=True,
                              num_workers=nw)

    validate_dataset = datasets.ImageFolder(root=os.path.join(image_path, "val"),
                                            loader=custom_loader,
                                            transform=data_transform["val"])
    val_num = len(validate_dataset)
    validate_loader = DataLoader(validate_dataset,
                                 batch_size=batch_size, shuffle=False,
                                 num_workers=nw)

    logging.info("using {} images for training, {} images for validation.".format(train_num,
                                                                                  val_num))
    out_planes = len(train_dataset.classes)
    net = Star(out_planes=out_planes, encoder='starnet_s3')
    net = net.to(device)

    # load pretrain weights
    model_weight_path = "/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/model_weight/wshHea_SIW-13_1_models/wshHea_SIW-13_1.pth"
    assert os.path.exists(model_weight_path), "file {} does not exist.".format(model_weight_path)


    ckpt = torch.load(model_weight_path, map_location="cpu")
    state_dict = ckpt["state_dict"] if "state_dict" in ckpt else ckpt
    # 映射到 net.backbone.*
    new_state_dict = {}
    for k, v in state_dict.items():
        # 去掉多卡前缀
        if k.startswith("module."):
            k = k[len("module."):]
        # 如果 ckpt 里本来就没有 backbone. 前缀，就加上
        if not k.startswith("backbone."):
            k = "backbone." + k
        new_state_dict[k] = v

    # 删掉分类头权重（避免类别数不一致导致 shape mismatch）
    for k in list(new_state_dict.keys()):
        if k.startswith("backbone.head."):
            del new_state_dict[k]
    # 加载
    missing, unexpected = net.load_state_dict(new_state_dict, strict=False)
    logging.info(f"Pretrain loaded. missing={len(missing)}, unexpected={len(unexpected)}")
    # 重建分类头：用 out_planes（不要写死4）
    if hasattr(net.backbone, "head") and isinstance(net.backbone.head, nn.Linear):
        in_dim = net.backbone.head.in_features
        net.backbone.head = nn.Linear(in_dim, out_planes)

    net = net.to(device)
    # 计算并打印模型的总参数量
    total = sum([param.nelement() for param in net.parameters()])
    logging.info("Number of parameters: %.2fM" % (total / 1e6))

    # define loss function
    loss_function = nn.CrossEntropyLoss()

    # construct an optimizer
    # optimizer = torch.optim.SGD(net.parameters(), lr=1e-4, momentum=0.9, weight_decay=1e-4)
    optimizer = torch.optim.AdamW(net.parameters(), lr=1e-4, weight_decay=1e-4)


    epochs = 200
    scheduler = CosineAnnealingLR(optimizer, T_max=epochs, eta_min=1e-6)

    # ===== Early Stopping (monitor val_loss) =====
    patience = 50  # 连续多少个epoch无提升就停止（可调）

    # 初始化（放在训练循环外）
    best_acc = 0
    best_epoch = 0
    early_stop_counter = 0

    # 可选：acc 的最小提升阈值，防止抖动
    min_delta_acc = 1e-4  # 例如 1e-4 或 1e-3（acc通常是0~1）


    save_dir = "/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/model_weight/wshHea_transfer_CVSI-2015_1_models"  # 保存模型的目录,
    os.makedirs(save_dir, exist_ok=True)
    save_path = '/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/model_weight/wshHea_transfer_CVSI-2015_1_models/wshHea_transfer_CVSI-2015_1.pth'
    train_steps = len(train_loader)
    # 初始化记录列表
    train_losses = []
    val_losses = []
    train_accuracies = []
    val_accuracies = []

    # 开始记录时间
    start_time = time.time()
    for epoch in range(epochs):
        # train
        net.train()
        running_loss = 0.0
        correct_train = 0
        total_train = 0
        train_bar = tqdm(train_loader, file=sys.stdout)
        for step, data in enumerate(train_bar):
            images, labels = data
            optimizer.zero_grad()
            logits = net(images.to(device))

            loss = loss_function(logits, labels.to(device))
            loss.backward()
            optimizer.step()

            # print statistics
            running_loss += loss.item()
            _, predicted = torch.max(logits, 1)
            correct_train += (predicted == labels.to(device)).sum().item()
            total_train += labels.size(0)

            train_bar.desc = "train epoch[{}/{}] loss:{:.4f}".format(epoch + 1, epochs, loss)
        train_loss = running_loss / train_steps
        train_acc = correct_train / total_train
        train_losses.append(train_loss)
        train_accuracies.append(train_acc)

        # validate
        net.eval()

        val_running_loss = 0.0
        correct_val = 0
        total_val = 0

        with torch.no_grad():
            val_bar = tqdm(validate_loader, file=sys.stdout)
            for val_data in val_bar:
                val_images, val_labels = val_data
                outputs = net(val_images.to(device))
                loss = loss_function(outputs, val_labels.to(device))
                val_running_loss += loss.item()
                _, predicted = torch.max(outputs, 1)
                correct_val += (predicted == val_labels.to(device)).sum().item()
                total_val += val_labels.size(0)  # batch_size

                val_bar.desc = "valid epoch[{}/{}]".format(epoch + 1, epochs)
        val_loss = val_running_loss / len(validate_loader)
        val_acc = correct_val / total_val
        val_losses.append(val_loss)
        val_accuracies.append(val_acc)

        logging.info('[epoch %d] train_loss: %.4f  val_loss: %.4f  train_accuracy: %.4f  val_accuracy: %.4f' %
              (epoch + 1, train_loss, val_loss, train_acc, val_acc))

        # 在验证完成后清理缓存
        torch.cuda.empty_cache()
        scheduler.step()  # 调用余弦退火调度器

        # ===== 早停策略 ModelCheckpoint + EarlyStopping: monitor val_acc =====
        if val_acc > best_acc:
            best_acc = val_acc
            best_epoch = epoch + 1
            # early_stop_counter = 0
            torch.save(net.state_dict(), save_path)  # 保存“验证准确率最高”的权重
            logging.info(
                f"✅ Best model saved (val_acc improved). best_acc={best_acc:.4f} at epoch={best_epoch}"
            )
        # else:
        #     early_stop_counter += 1
        #     logging.info(
        #         f"⏳ EarlyStopping counter: {early_stop_counter}/{patience} (best_acc={best_acc:.4f} at epoch={best_epoch})"
        #     )

        #     if early_stop_counter >= patience:
        #         logging.info(
        #             f"🛑 Early stopping triggered at epoch {epoch + 1}. Best epoch: {best_epoch}, best_acc: {best_acc:.4f}"
        #         )
        #         break
        # ===== 训练结束后打印 =====
    logging.info(f"Best validation accuracy: {best_acc:.4f}")

    # 结束记录时间
    end_time = time.time()
    total_time = end_time - start_time
    logging.info("total time: {:.4f}s".format(total_time))


    plt.figure(figsize=(12, 6))  # 设置图片大小
    # 设置全局轴的网格线在图像之下
    plt.rcParams['axes.axisbelow'] = True  # 确保网格线在图像之下

    # 绘制 Loss 和 Accuracy 在同一张图上
    plt.plot(range(1, len(val_losses) + 1), train_losses, label='Train Loss', color='blue', linestyle='-')
    plt.plot(range(1, len(val_losses) + 1), val_losses, label='Validation Loss', color='orange', linestyle='--')
    plt.plot(range(1, len(val_losses) + 1), train_accuracies, label='Train Accuracy', color='green', linestyle='-')
    plt.plot(range(1, len(val_losses) + 1), val_accuracies, label='Validation Accuracy', color='red', linestyle='--')

    # 添加标签和标题
    plt.xlabel('Epochs')
    plt.ylabel('Values')
    plt.title('Training and Validation Loss & Accuracy')
    plt.legend()

    # 设置网格背景
    plt.grid(color='gray', linestyle='-', linewidth=0.3, alpha=0.2)  # 淡灰色网格线

    # 保存和显示图像
    plt.tight_layout()  # 调整子图间距
    plt.savefig(r"/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/picture/wshHea_transfer_CVSI-2015_1_plot.png", dpi=300)
    plt.show()


if __name__ == '__main__':
    setup_seed(42)
    print('已经初始化种子')
    main()

