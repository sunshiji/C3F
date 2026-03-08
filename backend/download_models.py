#!/usr/bin/env python3
"""
download_models.py — 一次性 EasyOCR 模型下载工具
=================================================
在**有网络**的环境中运行本脚本，将所有 EasyOCR 模型权重文件下载到指定目录。
下载完成后，将目录路径配置到 OCR_MODEL_DIR 环境变量，服务启动时将直接读取
本地文件，不再发起任何网络请求。

EasyOCR 对不同 Unicode 字符集的语种有兼容性限制（例如泰文只能与英文搭配），
本脚本自动按兼容分组分批下载，无需手动处理。

用法
----
# 下载到默认目录 backend/ocr_models（推荐）
python backend/download_models.py

# 下载到自定义目录
python backend/download_models.py --model-dir /data/easyocr_models

# 下载指定语种（默认下载全部 13 个）
python backend/download_models.py --langs ch_sim,en,ja,ko

环境变量
--------
OCR_MODEL_DIR  — 覆盖 --model-dir 参数，与 app.py 使用同一变量
OCR_LANGS      — 覆盖 --langs 参数，与 app.py 使用同一变量
"""

import argparse
import os
import sys

# ── 默认值（与 config.py 保持一致）──────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MODEL_DIR = os.path.join(_SCRIPT_DIR, 'ocr_models')
_DEFAULT_LANGS = 'ch_sim,ch_tra,en,ja,ko,ar,hi,ru,th,bn,ta,kn,te'

# Import grouping logic from config.py to avoid duplicating the template list.
sys.path.insert(0, _SCRIPT_DIR)
from config import _make_lang_groups  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description='下载 EasyOCR 模型权重到本地目录',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        '--model-dir', '-d',
        default=os.environ.get('OCR_MODEL_DIR', _DEFAULT_MODEL_DIR),
        help=f'模型保存目录（默认：{_DEFAULT_MODEL_DIR}）',
    )
    parser.add_argument(
        '--langs', '-l',
        default=os.environ.get('OCR_LANGS', _DEFAULT_LANGS),
        help='逗号分隔的 EasyOCR 语种代码（默认：全部 13 个）',
    )
    parser.add_argument(
        '--gpu', action='store_true', default=False,
        help='下载时使用 GPU（仅影响加载验证，下载本身不需要 GPU）',
    )
    return parser.parse_args()


def main():
    args = parse_args()
    langs = [l.strip() for l in args.langs.split(',') if l.strip()]
    model_dir = os.path.abspath(args.model_dir)
    groups = _make_lang_groups(langs)

    print('=' * 60)
    print('EasyOCR 模型下载工具')
    print('=' * 60)
    print(f'目标目录 : {model_dir}')
    print(f'语种列表 : {", ".join(langs)}')
    print(f'分组数量 : {len(groups)} 组（EasyOCR 每组独立 Reader）')
    print(f'GPU 模式 : {"是" if args.gpu else "否（下载仅需 CPU）"}')
    print('-' * 60)

    os.makedirs(model_dir, exist_ok=True)

    try:
        import easyocr
    except ImportError:
        print('\n[错误] 未找到 easyocr，请先安装：', file=sys.stderr)
        print('  pip install easyocr', file=sys.stderr)
        sys.exit(1)

    print('\n正在按兼容分组逐批下载模型文件，请稍候……')
    print('（首次运行约需下载 1–3 GB，请确保网络畅通）\n')

    failed = []
    for i, group in enumerate(groups, 1):
        print(f'[{i}/{len(groups)}] 下载分组：{", ".join(group)}')
        try:
            easyocr.Reader(
                group,
                gpu=args.gpu,
                model_storage_directory=model_dir,
                download_enabled=True,
                verbose=True,
            )
            print(f'  ✓ 完成\n')
        except Exception as exc:
            print(f'  ✗ 失败：{exc}\n', file=sys.stderr)
            failed.append((group, str(exc)))

    print('=' * 60)
    if failed:
        print(f'✗ {len(failed)} 个分组下载失败：')
        for group, err in failed:
            print(f'  {", ".join(group)}: {err}')
        print()
        print('排查建议：')
        print('  1. 检查网络连接：curl -I https://github.com')
        print('  2. 如有代理，请先设置：export https_proxy=http://proxy:port')
        print('  3. 重新运行本脚本（已下载的文件会被自动跳过）')
        print('=' * 60)
        sys.exit(1)

    print('✓ 所有模型下载完成！')
    print(f'  模型目录：{model_dir}')
    print()
    print('下一步：将以下环境变量写入 systemd 服务文件后重启服务')
    print()
    print(f'  Environment="OCR_MODEL_DIR={model_dir}"')
    print()
    print('或直接启动：')
    print(f'  OCR_MODEL_DIR={model_dir} python backend/app.py')
    print('=' * 60)


if __name__ == '__main__':
    main()
