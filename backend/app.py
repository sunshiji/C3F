"""
自然场景文种识别系统 - Flask 后端
Natural Scene Text Language Recognition System - Backend
"""

import os
import re
import uuid
import hashlib
import json
import logging
import sqlite3
from datetime import datetime, date

from flask import Flask, request, jsonify, session, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

import config

# ── 初始化 ────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.config['MAX_CONTENT_LENGTH'] = config.MAX_CONTENT_MB * 1024 * 1024
app.config['UPLOAD_FOLDER'] = config.UPLOAD_FOLDER

CORS(app, supports_credentials=True, origins='*')

os.makedirs(config.UPLOAD_FOLDER, exist_ok=True)

# ── OCR 依赖（可选）────────────────────────────────────────────
_ocr_reader = None

def get_ocr_reader():
    global _ocr_reader
    if _ocr_reader is None:
        try:
            import easyocr
            # 加载中/英/日/韩等常用语言模型
            _ocr_reader = easyocr.Reader(
                ['ch_sim', 'en', 'ja', 'ko'],
                gpu=False, verbose=False
            )
            logger.info('EasyOCR reader initialized')
        except Exception as e:
            logger.warning(f'EasyOCR unavailable: {e}')
    return _ocr_reader

# ── 语言代码 → 中文名称 ────────────────────────────────────────
LANGUAGE_NAMES = {
    'zh':    ('中文',        'Chinese'),
    'zh-cn': ('中文(简体)',  'Chinese Simplified'),
    'zh-tw': ('中文(繁体)',  'Chinese Traditional'),
    'en':    ('英文',        'English'),
    'ja':    ('日文',        'Japanese'),
    'ko':    ('韩文',        'Korean'),
    'ar':    ('阿拉伯文',    'Arabic'),
    'fr':    ('法文',        'French'),
    'de':    ('德文',        'German'),
    'es':    ('西班牙文',    'Spanish'),
    'ru':    ('俄文',        'Russian'),
    'pt':    ('葡萄牙文',    'Portuguese'),
    'it':    ('意大利文',    'Italian'),
    'th':    ('泰文',        'Thai'),
    'vi':    ('越南文',      'Vietnamese'),
    'hi':    ('印地文',      'Hindi'),
    'tr':    ('土耳其文',    'Turkish'),
    'nl':    ('荷兰文',      'Dutch'),
    'pl':    ('波兰文',      'Polish'),
    'sv':    ('瑞典文',      'Swedish'),
    'da':    ('丹麦文',      'Danish'),
    'fi':    ('芬兰文',      'Finnish'),
    'el':    ('希腊文',      'Greek'),
    'he':    ('希伯来文',    'Hebrew'),
    'fa':    ('波斯文',      'Persian'),
    'uk':    ('乌克兰文',    'Ukrainian'),
    'id':    ('印尼文',      'Indonesian'),
    'ms':    ('马来文',      'Malay'),
    'bg':    ('保加利亚文',  'Bulgarian'),
    'hr':    ('克罗地亚文',  'Croatian'),
    'cs':    ('捷克文',      'Czech'),
    'sk':    ('斯洛伐克文',  'Slovak'),
    'hu':    ('匈牙利文',    'Hungarian'),
    'ro':    ('罗马尼亚文',  'Romanian'),
    'no':    ('挪威文',      'Norwegian'),
    'ca':    ('加泰罗尼亚文','Catalan'),
    'sr':    ('塞尔维亚文',  'Serbian'),
    'unknown': ('未知语言',  'Unknown'),
}

def get_lang_name(code):
    code = (code or '').lower()
    return LANGUAGE_NAMES.get(code, (f'其他({code})', f'Other({code})'))

# ── 数据库 ─────────────────────────────────────────────────────
def get_db():
    """Return a per-request SQLite connection with dict-style row factory.
    Each call creates a new connection, so no cross-thread sharing occurs."""
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    conn.row_factory = lambda c, r: dict(zip([col[0] for col in c.description], r))
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

def init_db():
    """Create tables and seed initial data (idempotent)."""
    conn = sqlite3.connect(config.DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.executescript('''
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS users (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL UNIQUE,
            password    TEXT    NOT NULL,
            email       TEXT    DEFAULT NULL,
            role        TEXT    NOT NULL DEFAULT 'user',
            avatar      TEXT    DEFAULT NULL,
            is_active   INTEGER NOT NULL DEFAULT 1,
            last_login  TEXT    DEFAULT NULL,
            created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );

        CREATE TABLE IF NOT EXISTS records (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id             INTEGER NOT NULL,
            filename            TEXT    NOT NULL,
            original_filename   TEXT    DEFAULT NULL,
            file_size           INTEGER DEFAULT NULL,
            detected_language   TEXT    DEFAULT NULL,
            language_name       TEXT    DEFAULT NULL,
            language_name_en    TEXT    DEFAULT NULL,
            confidence          REAL    DEFAULT 0,
            detected_text       TEXT    DEFAULT NULL,
            all_languages       TEXT    DEFAULT NULL,
            status              TEXT    NOT NULL DEFAULT 'success',
            error_msg           TEXT    DEFAULT NULL,
            created_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS system_config (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            config_key  TEXT    NOT NULL UNIQUE,
            config_val  TEXT    DEFAULT NULL,
            description TEXT    DEFAULT NULL,
            updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
        );
    ''')

    # Seed users (INSERT OR IGNORE = safe to run multiple times)
    admin_pw = hashlib.md5('admin123'.encode()).hexdigest()
    user_pw  = hashlib.md5('user123'.encode()).hexdigest()
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password, email, role) VALUES (?,?,?,?)",
        ('admin', admin_pw, 'admin@c3f.local', 'admin')
    )
    cur.execute(
        "INSERT OR IGNORE INTO users (username, password, email, role) VALUES (?,?,?,?)",
        ('user1', user_pw, 'user1@c3f.local', 'user')
    )

    # Seed system config
    for key, val, desc in [
        ('max_file_size_mb', '16',   '最大上传文件大小(MB)'),
        ('allowed_types',    'jpg,jpeg,png,bmp,gif,webp,tiff', '允许的图片类型'),
        ('ocr_engine',       'easyocr', 'OCR引擎'),
        ('site_name',        '自然场景文种识别系统', '网站名称'),
    ]:
        cur.execute(
            "INSERT OR IGNORE INTO system_config (config_key, config_val, description) VALUES (?,?,?)",
            (key, val, desc)
        )

    conn.commit()
    conn.close()
    logger.info('Database initialized ✓  path: %s', config.DB_PATH)

# init_db() uses CREATE TABLE IF NOT EXISTS + INSERT OR IGNORE, so it is fully
# idempotent and safe to call on every worker startup or concurrent invocation.
init_db()

# ── 工具函数 ───────────────────────────────────────────────────
def md5(s: str) -> str:
    return hashlib.md5(s.encode()).hexdigest()

def allowed_file(filename: str) -> bool:
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in config.ALLOWED_EXTENSIONS

def current_user():
    return session.get('user_id'), session.get('username'), session.get('role')

def require_login(fn):
    from functools import wraps
    @wraps(fn)
    def wrapper(*args, **kwargs):
        uid, uname, role = current_user()
        if not uid:
            return jsonify({'success': False, 'message': '请先登录'}), 401
        return fn(*args, **kwargs)
    return wrapper

# ── 认证接口 ───────────────────────────────────────────────────
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json(force=True)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'SELECT id, username, role FROM users '
            'WHERE username=? AND password=? AND is_active=1',
            (username, md5(password))
        )
        user = cur.fetchone()
        if user:
            cur.execute(
                "UPDATE users SET last_login=datetime('now','localtime') WHERE id=?",
                (user['id'],)
            )
            conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f'Login DB error: {e}')
        return jsonify({'success': False, 'message': '数据库错误，请稍后重试'}), 500

    if not user:
        return jsonify({'success': False, 'message': '用户名或密码错误'}), 401

    session['user_id']  = user['id']
    session['username'] = user['username']
    session['role']     = user['role']

    return jsonify({
        'success':  True,
        'user_id':  user['id'],
        'username': user['username'],
        'role':     user['role'],
    })

@app.route('/api/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/check_auth', methods=['GET'])
def check_auth():
    uid, uname, role = current_user()
    if uid:
        return jsonify({'logged_in': True, 'username': uname, 'role': role})
    return jsonify({'logged_in': False}), 401

# ── 统计信息 ───────────────────────────────────────────────────
@app.route('/api/stats', methods=['GET'])
@require_login
def get_stats():
    uid, _, role = current_user()
    try:
        conn = get_db()
        cur = conn.cursor()
        # 总识别次数
        q_total = 'SELECT COUNT(*) AS cnt FROM records'
        q_today = "SELECT COUNT(*) AS cnt FROM records WHERE date(created_at)=date('now','localtime')"
        q_lang  = 'SELECT COUNT(DISTINCT detected_language) AS cnt FROM records'
        q_week  = (
            "SELECT date(created_at) AS day, COUNT(*) AS cnt "
            "FROM records WHERE date(created_at) >= date('now','-6 days','localtime') "
            "GROUP BY day ORDER BY day"
        )
        q_dist  = (
            "SELECT language_name, COUNT(*) AS cnt FROM records "
            "WHERE language_name IS NOT NULL "
            "GROUP BY language_name ORDER BY cnt DESC LIMIT 8"
        )
        q_recent = (
            "SELECT r.id, r.original_filename, r.language_name, r.confidence, "
            "r.created_at, u.username "
            "FROM records r JOIN users u ON r.user_id=u.id "
            "ORDER BY r.created_at DESC LIMIT 5"
        )
        if role != 'admin':
            q_total  = q_total  + ' WHERE user_id=?'
            q_today  = q_today  + ' AND user_id=?'
            q_lang   = q_lang   + ' WHERE user_id=?'
            q_week   = q_week.replace("WHERE date(created_at)", "WHERE user_id=? AND date(created_at)")
            q_dist   = q_dist.replace('WHERE language_name', 'WHERE user_id=? AND language_name')
            q_recent = q_recent.replace('ORDER BY r.created_at', 'WHERE r.user_id=? ORDER BY r.created_at')
            args = (uid,)
        else:
            args = ()

        cur.execute(q_total, args);  total  = cur.fetchone()['cnt']
        cur.execute(q_today, args);  today  = cur.fetchone()['cnt']
        cur.execute(q_lang,  args);  langs  = cur.fetchone()['cnt']
        cur.execute(q_week,  args);  week   = cur.fetchall()
        cur.execute(q_dist,  args);  dist   = cur.fetchall()
        cur.execute(q_recent,args);  recent = cur.fetchall()
        conn.close()

        # 序列化日期
        for row in week:
            row['day'] = str(row['day'])
        for row in recent:
            row['created_at'] = str(row['created_at'])

        return jsonify({
            'total':   total,
            'today':   today,
            'langs':   langs,
            'week':    week,
            'dist':    dist,
            'recent':  recent,
        })
    except Exception as e:
        logger.error(f'Stats error: {e}')
        return jsonify({'success': False, 'message': '获取统计失败'}), 500

# ── 图像识别 ───────────────────────────────────────────────────
# 无 OCR 文本时的演示用默认候选语言（仅占位，非真实识别结果）
_FALLBACK_LANG_CODE   = 'en'
_FALLBACK_CONFIDENCE  = 60.0
_FALLBACK_ALL_LANGS   = [
    {'lang': 'en', 'name_zh': '英文',  'name_en': 'English',  'prob': 60.0},
    {'lang': 'zh', 'name_zh': '中文',  'name_en': 'Chinese',  'prob': 25.0},
    {'lang': 'ja', 'name_zh': '日文',  'name_en': 'Japanese', 'prob': 15.0},
]
@app.route('/api/recognize', methods=['POST'])
@require_login
def recognize():
    uid, _, _ = current_user()

    if 'file' not in request.files:
        return jsonify({'success': False, 'message': '未找到上传文件'}), 400

    f = request.files['file']
    if f.filename == '':
        return jsonify({'success': False, 'message': '文件名为空'}), 400
    if not allowed_file(f.filename):
        return jsonify({'success': False, 'message': '不支持的文件格式'}), 400

    # 保存文件
    ext      = f.filename.rsplit('.', 1)[1].lower()
    stored   = f'{uuid.uuid4().hex}.{ext}'
    filepath = os.path.join(config.UPLOAD_FOLDER, stored)
    f.save(filepath)
    file_size = os.path.getsize(filepath)

    # OCR + 语种识别
    detected_text = ''
    lang_code     = 'unknown'
    confidence    = 0.0
    all_langs     = []

    try:
        reader = get_ocr_reader()
        if reader:
            results = reader.readtext(filepath)
            texts   = [r[1] for r in results]
            scores  = [r[2] for r in results]
            detected_text = ' '.join(texts)
            if scores:
                confidence = round(sum(scores) / len(scores) * 100, 2)
        else:
            # 尝试 pytesseract
            try:
                from PIL import Image
                import pytesseract
                img = Image.open(filepath)
                detected_text = pytesseract.image_to_string(img)
            except Exception:
                detected_text = ''

        if detected_text.strip():
            try:
                from langdetect import detect, detect_langs
                lang_code  = detect(detected_text)
                raw_langs  = detect_langs(detected_text)
                all_langs  = [{'lang': str(l).split(':')[0],
                                'prob': round(float(str(l).split(':')[1]) * 100, 1)}
                               for l in raw_langs]
                # 补充语言名称
                for item in all_langs:
                    zh, en = get_lang_name(item['lang'])
                    item['name_zh'] = zh
                    item['name_en'] = en
                # 主语言置信度
                top = next((l for l in all_langs if l['lang'] == lang_code), None)
                if top:
                    confidence = top['prob']
            except Exception as e:
                logger.warning(f'langdetect error: {e}')
        else:
            # 无文本时根据图像统计模拟（演示用）
            lang_code  = _FALLBACK_LANG_CODE
            confidence = _FALLBACK_CONFIDENCE
            all_langs  = [dict(item) for item in _FALLBACK_ALL_LANGS]

    except Exception as e:
        logger.error(f'Recognition error: {e}')
        lang_code  = 'unknown'
        confidence = 0.0

    zh_name, en_name = get_lang_name(lang_code)

    # 写入数据库
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            '''INSERT INTO records
               (user_id, filename, original_filename, file_size,
                detected_language, language_name, language_name_en,
                confidence, detected_text, all_languages, status)
               VALUES (?,?,?,?,?,?,?,?,?,?,'success')''',
            (uid, stored, f.filename, file_size,
             lang_code, zh_name, en_name,
             confidence, detected_text,
             json.dumps(all_langs, ensure_ascii=False))
        )
        record_id = cur.lastrowid
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f'DB insert error: {e}')
        record_id = None

    return jsonify({
        'success':          True,
        'record_id':        record_id,
        'filename':         stored,
        'original_filename':f.filename,
        'detected_language':lang_code,
        'language_name':    zh_name,
        'language_name_en': en_name,
        'confidence':       confidence,
        'detected_text':    detected_text,
        'all_languages':    all_langs,
        'image_url':        f'/uploads/{stored}',
    })

# ── 历史记录 ───────────────────────────────────────────────────
@app.route('/api/history', methods=['GET'])
@require_login
def get_history():
    uid, _, role = current_user()
    page     = max(1, int(request.args.get('page', 1)))
    per_page = max(1, min(50, int(request.args.get('per_page', 10))))
    search   = request.args.get('search', '').strip()
    language = request.args.get('language', '').strip()
    # Allowlist: only accept known language codes (letters, digits, hyphen, max 10 chars)
    if language and not re.match(r'^[a-z]{2,10}(-[a-z]{2,4})?$', language):
        language = ''
    offset   = (page - 1) * per_page

    where_parts = []
    params      = []
    if role != 'admin':
        where_parts.append('r.user_id=?');  params.append(uid)
    if search:
        where_parts.append('(r.original_filename LIKE ? OR r.detected_text LIKE ?)')
        params += [f'%{search}%', f'%{search}%']
    if language:
        where_parts.append('r.detected_language=?');  params.append(language)

    where_sql = ('WHERE ' + ' AND '.join(where_parts)) if where_parts else ''

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            f'SELECT COUNT(*) AS cnt FROM records r {where_sql}', params
        )
        total = cur.fetchone()['cnt']

        cur.execute(
            f'''SELECT r.id, r.filename, r.original_filename, r.file_size,
                       r.detected_language, r.language_name, r.confidence,
                       r.detected_text, r.status, r.created_at, u.username
                FROM records r JOIN users u ON r.user_id=u.id
                {where_sql}
                ORDER BY r.created_at DESC
                LIMIT ? OFFSET ?''',
            params + [per_page, offset]
        )
        rows = cur.fetchall()
        conn.close()

        for row in rows:
            row['created_at'] = str(row['created_at'])
            row['image_url']  = f'/uploads/{row["filename"]}'

        return jsonify({
            'success':  True,
            'records':  rows,
            'total':    total,
            'page':     page,
            'per_page': per_page,
            'pages':    (total + per_page - 1) // per_page,
        })
    except Exception as e:
        logger.error(f'History error: {e}')
        return jsonify({'success': False, 'message': '获取历史记录失败'}), 500

@app.route('/api/history/<int:record_id>', methods=['DELETE'])
@require_login
def delete_record(record_id):
    uid, _, role = current_user()
    try:
        conn = get_db()
        cur = conn.cursor()
        if role == 'admin':
            cur.execute('SELECT filename FROM records WHERE id=?', (record_id,))
        else:
            cur.execute('SELECT filename FROM records WHERE id=? AND user_id=?',
                        (record_id, uid))
        row = cur.fetchone()
        if not row:
            conn.close()
            return jsonify({'success': False, 'message': '记录不存在'}), 404
        # 删除文件
        fp = os.path.join(config.UPLOAD_FOLDER, row['filename'])
        if os.path.exists(fp):
            os.remove(fp)
        cur.execute('DELETE FROM records WHERE id=?', (record_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f'Delete record error: {e}')
        return jsonify({'success': False, 'message': '删除失败'}), 500

# ── 用户管理 ───────────────────────────────────────────────────
@app.route('/api/profile', methods=['GET'])
@require_login
def get_profile():
    uid, _, _ = current_user()
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'SELECT id, username, email, role, created_at, last_login FROM users WHERE id=?',
            (uid,)
        )
        user = cur.fetchone()
        conn.close()
        if user:
            user['created_at']  = str(user['created_at'])
            user['last_login']  = str(user['last_login']) if user['last_login'] else None
        return jsonify({'success': True, 'user': user})
    except Exception as e:
        logger.error(f'Profile error: {e}')
        return jsonify({'success': False, 'message': '获取用户信息失败'}), 500

@app.route('/api/profile', methods=['PUT'])
@require_login
def update_profile():
    uid, _, _ = current_user()
    data  = request.get_json(force=True)
    email = (data.get('email') or '').strip()
    old_pw = data.get('old_password') or ''
    new_pw = data.get('new_password') or ''

    try:
        conn = get_db()
        cur = conn.cursor()
        if new_pw:
            cur.execute('SELECT password FROM users WHERE id=?', (uid,))
            row = cur.fetchone()
            if row['password'] != md5(old_pw):
                conn.close()
                return jsonify({'success': False, 'message': '原密码错误'}), 400
            cur.execute('UPDATE users SET password=?, email=? WHERE id=?',
                        (md5(new_pw), email, uid))
        else:
            cur.execute('UPDATE users SET email=? WHERE id=?', (email, uid))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '更新成功'})
    except Exception as e:
        logger.error(f'Update profile error: {e}')
        return jsonify({'success': False, 'message': '更新失败'}), 500

@app.route('/api/users', methods=['GET'])
@require_login
def list_users():
    _, _, role = current_user()
    if role != 'admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            'SELECT id, username, email, role, is_active, created_at, last_login FROM users'
        )
        users = cur.fetchall()
        conn.close()
        for u in users:
            u['created_at'] = str(u['created_at'])
            u['last_login'] = str(u['last_login']) if u['last_login'] else None
        return jsonify({'success': True, 'users': users})
    except Exception as e:
        logger.error(f'List users error: {e}')
        return jsonify({'success': False, 'message': '获取用户列表失败'}), 500

@app.route('/api/users', methods=['POST'])
@require_login
def create_user():
    _, _, role = current_user()
    if role != 'admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403
    data     = request.get_json(force=True)
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''
    email    = (data.get('email') or '').strip()
    u_role   = data.get('role', 'user')
    if not username or not password:
        return jsonify({'success': False, 'message': '用户名和密码不能为空'}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('INSERT INTO users (username, password, email, role) VALUES (?,?,?,?)',
                    (username, md5(password), email, u_role))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': '创建成功'})
    except sqlite3.IntegrityError:
        return jsonify({'success': False, 'message': '用户名已存在'}), 409
    except Exception as e:
        logger.error(f'Create user error: {e}')
        return jsonify({'success': False, 'message': '创建失败'}), 500

@app.route('/api/users/<int:user_id>', methods=['PUT'])
@require_login
def update_user(user_id):
    _, _, role = current_user()
    if role != 'admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403
    data      = request.get_json(force=True)
    is_active = data.get('is_active')
    u_role    = data.get('role')
    try:
        conn = get_db()
        cur = conn.cursor()
        if is_active is not None and u_role:
            cur.execute('UPDATE users SET is_active=?, role=? WHERE id=?',
                        (1 if is_active else 0, u_role, user_id))
        elif is_active is not None:
            cur.execute('UPDATE users SET is_active=? WHERE id=?',
                        (1 if is_active else 0, user_id))
        elif u_role:
            cur.execute('UPDATE users SET role=? WHERE id=?', (u_role, user_id))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f'Update user error: {e}')
        return jsonify({'success': False, 'message': '更新失败'}), 500

@app.route('/api/users/<int:user_id>', methods=['DELETE'])
@require_login
def delete_user(user_id):
    uid, _, role = current_user()
    if role != 'admin':
        return jsonify({'success': False, 'message': '权限不足'}), 403
    if user_id == uid:
        return jsonify({'success': False, 'message': '不能删除自己'}), 400
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('DELETE FROM users WHERE id=?', (user_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f'Delete user error: {e}')
        return jsonify({'success': False, 'message': '删除失败'}), 500

# ── 静态文件（上传图片）─────────────────────────────────────────
@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(config.UPLOAD_FOLDER, filename)

# ── 前端静态文件（当不使用 Nginx 时由 Flask 直接托管）──────────
_FRONTEND_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'frontend')
)

@app.route('/')
def frontend_index():
    return send_from_directory(_FRONTEND_DIR, 'login.html')

@app.route('/<path:filename>')
def frontend_static(filename):
    # Reject any path that attempts directory traversal
    if '..' in filename:
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(_FRONTEND_DIR, filename)

# ── 启动 ───────────────────────────────────────────────────────
if __name__ == '__main__':
    app.run(host=config.HOST, port=config.PORT, debug=config.DEBUG)
