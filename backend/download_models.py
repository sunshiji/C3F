#!/usr/bin/env python3
"""
download_models.py — EasyOCR 模型权重下载工具
==============================================
在**有网络**的环境中运行本脚本，将所有 EasyOCR 模型权重文件下载到
backend/models/ 目录。下载完成后，后端启动时将直接读取本地文件，
不再发起任何网络请求。

支持的语种
----------
EasyOCR 支持的语种（已验证）：
  ch_sim  — 简体中文
  ch_tra  — 繁体中文
  en      — 英文（拉丁文）
  ja      — 日文
  ko      — 韩文
  ar      — 阿拉伯文
  hi      — 印地语（天城体）
  ru      — 俄文（西里尔）
  th      — 泰文
  bn      — 孟加拉文
  kn      — 卡纳达文
  te      — 泰卢固文
  gu      — 古吉拉特文
  pa      — 旁遮普文（古鲁穆奇字母）
  ta      — 泰米尔文（注：1.7.x 可能有兼容性警告，自动跳过）

通过 Unicode 字符范围检测（无需 OCR 权重）：
  el (希腊文)、he (希伯来文)、km (柬埔寨/高棉文)、
  bo (藏文)、mn (蒙古文)、or (奥里亚文)

用法
----
  # 下载全部支持语种的模型到默认目录 backend/models/
  python backend/download_models.py

  # 下载到自定义目录
  python backend/download_models.py --model-dir /data/ocr_models

  # 只下载指定语种
  python backend/download_models.py --langs ch_sim,en,ja

环境变量
--------
  OCR_MODEL_DIR  — 覆盖 --model-dir 参数（与 app.py 同一变量）
  OCR_LANGS      — 覆盖 --langs 参数（与 app.py 同一变量）
"""

import argparse
import os
import sys

# ── 默认值（与 config.py 保持一致）──────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_DEFAULT_MODEL_DIR = os.path.join(_SCRIPT_DIR, 'models')
_DEFAULT_LANGS = 'ch_sim,ch_tra,en,ja,ko,ar,hi,ru,th,bn,kn,te,gu,pa,ta'

# Import grouping logic from config.py to avoid duplicating the template list.
sys.path.insert(0, _SCRIPT_DIR)
from config import _make_lang_groups  # noqa: E402


def parse_args():
    parser = argparse.ArgumentParser(
        description='下载 EasyOCR 模型权重到本地目录（backend/models/）',
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
        help='逗号分隔的 EasyOCR 语种代码（默认：全部 15 个）',
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
    print('EasyOCR 模型权重下载工具')
    print('=' * 60)
    print(f'目标目录 : {model_dir}')
    print(f'语种列表 : {", ".join(langs)}')
    print(f'分组数量 : {len(groups)} 组（EasyOCR 每组独立 Reader）')
    print(f'GPU 模式 : {"是" if args.gpu else "否（下载仅需 CPU）"}')
    print('-' * 60)
    print()
    print('注：以下语种通过 Unicode 字符范围检测，无需 OCR 模型权重：')
    print('  希腊文(el)、希伯来文(he)、柬埔寨文(km)、藏文(bo)、')
    print('  蒙古文(mn)、奥里亚文(or)')
    print('-' * 60)

    os.makedirs(model_dir, exist_ok=True)

    try:
        import easyocr
    except ImportError:
        print('\n[错误] 未找到 easyocr，请先安装：', file=sys.stderr)
        print('  pip install easyocr==1.7.1', file=sys.stderr)
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
        print(f'✗ {len(failed)} 个分组下载失败（不影响其余语种正常使用）：')
        for group, err in failed:
            print(f'  {", ".join(group)}: {err}')
        print()
        print('排查建议：')
        print('  1. 检查网络连接：curl -I https://github.com')
        print('  2. 如有代理，请先设置：export https_proxy=http://proxy:port')
        print('  3. 重新运行本脚本（已下载的文件会被自动跳过）')
        print('=' * 60)
        # Partial success is acceptable — only exit non-zero if ALL groups failed
        if len(failed) == len(groups):
            sys.exit(1)
        return

    print('✓ 所有模型下载完成！')
    print(f'  模型目录：{model_dir}')
    print()
    print('后端将在检测到目录中含有 .pth 文件时自动使用本地模型，')
    print('无需额外配置环境变量。')
    print()
    print('如需手动指定目录，可在 systemd 服务文件中添加：')
    print()
    print(f'  Environment="OCR_MODEL_DIR={model_dir}"')
    print()
    print('或直接启动：')
    print(f'  OCR_MODEL_DIR={model_dir} python backend/app.py')
    print('=' * 60)


if __name__ == '__main__':
    main()

