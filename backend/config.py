# backend/config.py
import os

# ── Flask ──────────────────────────────────────────────────────
SECRET_KEY = os.environ.get('C3F_SECRET_KEY', 'c3f-secret-key-2025-change-in-production')

# ── MySQL 8 ───────────────────────────────────────────────────
DB_CONFIG = {
    'host':     os.environ.get('DB_HOST',     'localhost'),
    'port':     int(os.environ.get('DB_PORT', 3306)),
    'user':     os.environ.get('DB_USER',     'root'),
    'password': os.environ.get('DB_PASSWORD', 'root'),
    'db':       os.environ.get('DB_NAME',     'c3f_db'),
    'charset':  'utf8mb4',
    'cursorclass': None,        # will be set in app.py
}

# ── Upload ─────────────────────────────────────────────────────
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
MAX_CONTENT_MB = 16
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'tiff'}

# ── Server ─────────────────────────────────────────────────────
HOST = '0.0.0.0'
PORT = 5000
DEBUG = False
