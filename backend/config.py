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

# ── EasyOCR ───────────────────────────────────────────────────
# Comma-separated EasyOCR language codes loaded at startup.
# Reduce this list for faster startup; extend it for broader coverage.
# Override via env: OCR_LANGS=ch_sim,en,ar python app.py
# Full language list: https://www.jaided.ai/easyocr/
_DEFAULT_OCR_LANGS = 'ch_sim,ch_tra,en,ja,ko,ar,hi,ru,th,bn,ta,kn,te'
OCR_LANGS = [l.strip() for l in
             os.environ.get('OCR_LANGS', _DEFAULT_OCR_LANGS).split(',')
             if l.strip()]

# EasyOCR enforces per-script language compatibility: languages from
# incompatible Unicode script families (e.g. Thai vs. CJK) cannot be
# combined in a single Reader instance.  The templates below group
# known-compatible languages; one Reader is created per active group.
# Each template includes 'en' because most recognition networks require it.
_LANG_GROUP_TEMPLATES = [
    ['ch_sim', 'ch_tra', 'en', 'ja', 'ko'],   # CJK + Latin
    ['ar', 'en'],                               # Arabic
    ['hi', 'en'],                               # Devanagari (Hindi)
    ['ru', 'en'],                               # Cyrillic (Russian)
    ['th', 'en'],                               # Thai  — strict 2-lang limit
    ['bn', 'en'],                               # Bengali
    ['ta', 'en'],                               # Tamil
    ['kn', 'en'],                               # Kannada
    ['te', 'en'],                               # Telugu
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

# Directory where EasyOCR reads model weight files.
# Point this to a folder of pre-downloaded .pth files to avoid any
# network access at startup.
# Override via env: OCR_MODEL_DIR=/path/to/models python app.py
# Default: None → EasyOCR uses ~/.EasyOCR/model/
OCR_MODEL_DIR = os.environ.get('OCR_MODEL_DIR') or None

# Use GPU for EasyOCR inference (significantly faster than CPU).
# Requires a CUDA-capable GPU and the GPU build of PyTorch.
# Set to "0" to fall back to CPU: OCR_USE_GPU=0 python app.py
OCR_USE_GPU = os.environ.get('OCR_USE_GPU', '1').strip() not in ('0', 'false', 'no')

# ── Upload limits ──────────────────────────────────────────────
MAX_CONTENT_MB = 16
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}

# ── Server ─────────────────────────────────────────────────────
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False
