import os
import numpy as np
import cv2

def merge_imgs(imgs, cols, rows, is_h=True):
    """
    将多个小图像按指定行列合并成大图（空白处用白色填充）
    """
    if not imgs:
        raise ValueError("合并图像的输入为空!")

    h, w, c = imgs[0].shape
    large_imgs = np.ones((rows * h, cols * w, c), dtype=np.uint8) * 255

    if is_h:  # 行优先
        for j in range(rows):
            for i in range(cols):
                idx = j * cols + i
                if idx >= len(imgs):
                    break
                # 确保最后一块图像不会超出目标区域
                img_h, img_w, _ = imgs[idx].shape
                large_imgs[j*h:(j+1)*h, i*w:(i+1)*w] = imgs[idx][:min(h, img_h), :min(w, img_w)]
    else:  # 列优先
        for i in range(cols):
            for j in range(rows):
                idx = i * rows + j
                if idx >= len(imgs):
                    break
                # 确保最后一块图像不会超出目标区域
                img_h, img_w, _ = imgs[idx].shape
                large_imgs[j*h:(j+1)*h, i*w:(i+1)*w] = imgs[idx][:min(h, img_h), :min(w, img_w)]

    return large_imgs

def resize_crop_square(img_arr):
    """
    将图像通过“分条带再拼接”的方式变成更接近正方形（尽量避免直接拉伸导致字符变形）
    """
    h, w, c = img_arr.shape
    w_ratio = float(w) / float(h)

    if w_ratio > 4:  # 宽远大于高：垂直分割->垂直堆叠
        x = max(1, int(np.sqrt(w_ratio)))
        gap_w = w // x
        patch_list = []
        for i in range(x):
            # 最后一块把剩余都吃掉，避免丢像素
            start = i * gap_w
            end = (i + 1) * gap_w if i < x - 1 else w
            patch_list.append(img_arr[:, start:end, :])
        img_out = merge_imgs(patch_list, 1, x)

    elif w_ratio < 0.25:  # 高远大于宽：水平分割->水平拼接
        h_ratio = 1.0 / w_ratio
        x = max(1, int(np.sqrt(h_ratio)))
        gap_h = h // x
        patch_list = []
        for i in range(x):
            start = i * gap_h
            end = (i + 1) * gap_h if i < x - 1 else h
            patch_list.append(img_arr[start:end, :, :])
        img_out = merge_imgs(patch_list, x, 1)

    else:
        img_out = img_arr

    return img_out


def process_image(input_path, output_path, final_size=(224, 224), keep_alpha=False):
    """
    读取输入路径图片 -> 预处理成“更接近正方形” -> resize到final_size -> 保存到输出路径
    """
    # 读取
    img = cv2.imread(input_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise FileNotFoundError(f"读图失败：{input_path}")
    # 打印输入图像的宽高
    print(f"输入图像宽度: {img.shape[1]}, 高度: {img.shape[0]}")
    # 统一为3通道BGR（若你需要保留alpha，可改成keep_alpha=True）
    if img.ndim == 2:  # 灰度图
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    elif img.shape[2] == 4:
        if keep_alpha:
            # 先把RGB拿出来处理，最后再把alpha拼回去（更复杂，这里默认不保留alpha）
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        else:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    # 预处理：分条带拼接
    out = resize_crop_square(img)

    # 最终尺寸（Efficient_xxs常用224x224）
    if final_size is not None:
        out = cv2.resize(out, final_size, interpolation=cv2.INTER_AREA)

    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # 保存
    ok = cv2.imwrite(output_path, out)
    if not ok:
        raise IOError(f"保存失败：{output_path}")

    return output_path

if __name__ == "__main__":
    in_path = r"/home/szh/datasets/SIW-13/train/Cambodian/cambodian_000010_1.jpg"
    out_path = r"/home/szh/datasets/SIW-13/cambodian_000010_1.jpg"
    saved = process_image(in_path, out_path, final_size=(224, 224))
    print("已保存：", saved)
