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

# ── Upload limits ──────────────────────────────────────────────
MAX_CONTENT_MB = 16
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}

# ── Server ─────────────────────────────────────────────────────
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False
