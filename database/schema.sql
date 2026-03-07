-- =============================================================
-- 自然场景文种识别系统 - SQLite 数据库设计（参考文档）
-- Natural Scene Text Language Recognition System
-- =============================================================
-- 注：应用启动时会通过 backend/app.py 中的 init_db() 自动建表并
--     写入初始数据，无需手动执行本文件。
-- =============================================================

-- 用户表
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,        -- MD5 hex digest
    email       TEXT    DEFAULT NULL,
    role        TEXT    NOT NULL DEFAULT 'user',   -- 'admin' | 'user'
    avatar      TEXT    DEFAULT NULL,
    is_active   INTEGER NOT NULL DEFAULT 1,
    last_login  TEXT    DEFAULT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 识别记录表
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
    all_languages       TEXT    DEFAULT NULL,   -- JSON stored as TEXT
    status              TEXT    NOT NULL DEFAULT 'success',
    error_msg           TEXT    DEFAULT NULL,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key  TEXT    NOT NULL UNIQUE,
    config_val  TEXT    DEFAULT NULL,
    description TEXT    DEFAULT NULL,
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

-- 初始数据（密码通过 Python MD5 生成，见 app.py init_db()）
-- admin / admin123
-- user1 / user123
