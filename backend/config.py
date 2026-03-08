# backend/config.py
import os

# ── Flask ──────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('C3F_SECRET_KEY', 'c3f-secret-key-2025-change-in-production')

# ── Paths & Upload ─────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# ── SQLite ────────────────────────────────────────────────────
# 无需安装数据库服务，自动创建文件，可通过环境变量覆盖路径：
#   DB_PATH=/path/to/c3f.db python app.py
DB_PATH = os.environ.get('DB_PATH', os.path.join(BASE_DIR, 'c3f.db'))

# ── OCR 模型目录 ──────────────────────────────────────────────
# 模型权重文件专用目录：backend/models/
# 将 .pth 文件下载到此目录后，后端启动时直接读取，无需联网。
# 下载方法：python backend/download_models.py
# 覆盖路径：OCR_MODEL_DIR=/path/to/models python app.py
MODELS_DIR = os.path.join(BASE_DIR, 'models')

def _resolve_model_dir():
    """Return the model storage directory to use.

    Priority:
    1. OCR_MODEL_DIR env var (explicit override)
    2. backend/models/ — if the directory exists and contains at least one
       .pth weight file (i.e. models have been pre-downloaded)
    3. None  → EasyOCR falls back to ~/.EasyOCR/model/ and may download
    """
    env_dir = os.environ.get('OCR_MODEL_DIR', '').strip()
    if env_dir:
        return env_dir
    if os.path.isdir(MODELS_DIR):
        if any(f.endswith(('.pth', '.pt')) for f in os.listdir(MODELS_DIR)):
            return MODELS_DIR
    return None

OCR_MODEL_DIR = _resolve_model_dir()

# ── EasyOCR 语种列表 ───────────────────────────────────────────
# EasyOCR 支持的语种代码（逗号分隔）。
# 启动时加载的语种越多，占用内存越大；可按需裁剪。
# 覆盖方式：OCR_LANGS=ch_sim,en,ar python app.py
# 完整列表：https://www.jaided.ai/easyocr/
#
# 说明：下列语种 EasyOCR 暂无模型支持，系统改用 Unicode 字符范围检测：
#   希腊文(el)、希伯来文(he)、柬埔寨/高棉文(km)、藏文(bo)、蒙古文(mn)、奥里亚文(or)
_DEFAULT_OCR_LANGS = 'ch_sim,ch_tra,en,ja,ko,ar,hi,ru,th,bn,kn,te'
OCR_LANGS = [l.strip() for l in
             os.environ.get('OCR_LANGS', _DEFAULT_OCR_LANGS).split(',')
             if l.strip()]

# EasyOCR 对不同 Unicode 字符集有兼容性限制，不同字符系的语种不能在同一
# Reader 实例中混用。下表列出已验证的兼容分组，每组独立创建一个 Reader。
# 每个分组都包含 'en'，因为大多数识别网络依赖英文基础权重。
_LANG_GROUP_TEMPLATES = [
    # ch_sim 严格只能与 en 组合（EasyOCR 限制）
    ['ch_sim', 'en'],               # 简体中文
    ['ch_tra', 'en'],               # 繁体中文
    ['ja',     'en'],               # 日文（独立 Reader，不可与 ch_sim 合并）
    ['ko',     'en'],               # 韩文（独立 Reader，不可与 ch_sim 合并）
    ['ar',     'en'],               # 阿拉伯文
    ['hi',     'en'],               # 天城体（印地语）
    ['ru',     'en'],               # 西里尔字母（俄语）
    ['th',     'en'],               # 泰文
    ['bn',     'en'],               # 孟加拉文
    ['kn',     'en'],               # 卡纳达文
    ['te',     'en'],               # 泰卢固文
    # 以下语种当前版本 EasyOCR 不支持，已从列表中移除：
    #   gu（古吉拉特文）、pa（古鲁穆奇/旁遮普文）— EasyOCR 1.7.x 无对应模型
    #   ta（泰米尔文）— 模型检查点输出维度与当前包版本不兼容（size mismatch）
]

def _make_lang_groups(langs):
    """Return per-Reader language lists derived from *langs*.

    Only groups that contain at least one language from *langs* (besides
    'en') are included.  'en' is always appended to every active group
    even when it is absent from *langs*.
    """
    lang_set = set(langs)
    groups = []
    seen = set()
    for template in _LANG_GROUP_TEMPLATES:
        group = [l for l in template if l in lang_set or l == 'en']
        non_en = [l for l in group if l != 'en']
        if not non_en:
            continue
        key = tuple(sorted(group))
        if key not in seen:
            seen.add(key)
            groups.append(group)
    return groups

OCR_LANG_GROUPS = _make_lang_groups(OCR_LANGS)

# GPU 推理开关（需要 CUDA 环境和 GPU 版 PyTorch）
# 关闭：OCR_USE_GPU=0 python app.py
OCR_USE_GPU = os.environ.get('OCR_USE_GPU', '1').strip() not in ('0', 'false', 'no')

# ── Upload limits ──────────────────────────────────────────────
MAX_CONTENT_MB = 16
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}

# ── Server ─────────────────────────────────────────────────────
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False
