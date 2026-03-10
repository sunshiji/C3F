import numpy as np
import seaborn as sns
import matplotlib.pyplot as plt

# 混淆矩阵内容（GT 行 vs Detection 列）
cm = np.array([
    [4760,  340,   1,   10,   20,   3,   8],
    [ 91, 59694, 110,  328, 193,  38, 83],
    [   31,  339, 3489, 833, 39, 16, 3],
    [  35, 1934, 920, 5075, 169,  6,  18],
    [  16, 1581,  171,  430, 10757, 27, 10],
    [   6,  224,  4,   16,   20, 2274,  1],
    [  25,  711,   3,   35,   16,  7, 2699]
])

# 标签名
labels = ['Arabic', 'Latin', 'Chinese', 'Japanese', 'Korean', 'Bangla', 'Symbols']

# 归一化矩阵，用于着色（颜色反映准确性）
cm_normalized = cm / cm.sum(axis=1, keepdims=True)

plt.figure(figsize=(7, 5))
# 使用归一化结果做热图，原始数量作为注释
heatmap = sns.heatmap(cm_normalized.T, annot=cm.T, fmt='d', cmap='Oranges', cbar=True,
            xticklabels=labels, yticklabels=labels)



plt.xlabel("True Labels")
plt.ylabel("Predicted Labels")
plt.title("Confusion Matrix")
plt.xticks(rotation=45)
plt.yticks(rotation=0)
plt.tight_layout()
plt.savefig("/home/szh/code/pytorchProject/Rewrite-the-Stars-main/starnet/ICDAR2017.png")
plt.show()

