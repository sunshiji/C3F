-- =============================================================
-- 自然场景文种识别系统 - MySQL 8 数据库设计
-- Natural Scene Text Language Recognition System
-- =============================================================

CREATE DATABASE IF NOT EXISTS c3f_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE c3f_db;

-- -------------------------------------------------------------
-- 用户表
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id          INT           NOT NULL AUTO_INCREMENT,
    username    VARCHAR(50)   NOT NULL UNIQUE COMMENT '用户名',
    password    VARCHAR(64)   NOT NULL        COMMENT 'MD5密码',
    email       VARCHAR(100)  DEFAULT NULL    COMMENT '邮箱',
    role        ENUM('admin','user') NOT NULL DEFAULT 'user' COMMENT '角色',
    avatar      VARCHAR(255)  DEFAULT NULL    COMMENT '头像URL',
    is_active   TINYINT(1)   NOT NULL DEFAULT 1 COMMENT '是否启用',
    last_login  DATETIME      DEFAULT NULL    COMMENT '最后登录时间',
    created_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='用户表';

-- -------------------------------------------------------------
-- 识别记录表
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS records (
    id                  INT           NOT NULL AUTO_INCREMENT,
    user_id             INT           NOT NULL                    COMMENT '用户ID',
    filename            VARCHAR(255)  NOT NULL                    COMMENT '存储文件名',
    original_filename   VARCHAR(255)  DEFAULT NULL                COMMENT '原始文件名',
    file_size           INT           DEFAULT NULL                COMMENT '文件大小(字节)',
    detected_language   VARCHAR(20)   DEFAULT NULL                COMMENT '识别语言代码',
    language_name       VARCHAR(50)   DEFAULT NULL                COMMENT '语言名称(中文)',
    language_name_en    VARCHAR(50)   DEFAULT NULL                COMMENT '语言名称(英文)',
    confidence          FLOAT         DEFAULT 0                   COMMENT '置信度(0-100)',
    detected_text       TEXT          DEFAULT NULL                COMMENT 'OCR识别文本',
    all_languages       JSON          DEFAULT NULL                COMMENT '全部语言概率JSON',
    status              ENUM('success','failed','processing')
                        NOT NULL DEFAULT 'success'                COMMENT '识别状态',
    error_msg           VARCHAR(255)  DEFAULT NULL                COMMENT '错误信息',
    created_at          DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    INDEX idx_user_id   (user_id),
    INDEX idx_created   (created_at),
    INDEX idx_language  (detected_language),
    CONSTRAINT fk_records_user FOREIGN KEY (user_id)
        REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='识别记录表';

-- -------------------------------------------------------------
-- 系统配置表（可选扩展）
-- -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS system_config (
    id          INT           NOT NULL AUTO_INCREMENT,
    config_key  VARCHAR(100)  NOT NULL UNIQUE COMMENT '配置键',
    config_val  TEXT          DEFAULT NULL   COMMENT '配置值',
    description VARCHAR(255)  DEFAULT NULL   COMMENT '说明',
    updated_at  DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
  COMMENT='系统配置表';

-- -------------------------------------------------------------
-- 初始数据
-- password: admin123 → MD5 = 0192023a7bbd73250516f069df18b500
-- password: user123  → MD5 = 6f96cfdfe5ccc627cadf24b41725b4e9
-- -------------------------------------------------------------
INSERT INTO users (username, password, email, role) VALUES
    ('admin', MD5('admin123'), 'admin@c3f.local', 'admin'),
    ('user1', MD5('user123'),  'user1@c3f.local', 'user')
ON DUPLICATE KEY UPDATE username = username;

INSERT INTO system_config (config_key, config_val, description) VALUES
    ('max_file_size_mb', '16',   '最大上传文件大小(MB)'),
    ('allowed_types',    'jpg,jpeg,png,bmp,gif,webp,tiff', '允许的图片类型'),
    ('ocr_engine',       'easyocr', 'OCR引擎'),
    ('site_name',        '自然场景文种识别系统', '网站名称')
ON DUPLICATE KEY UPDATE config_key = config_key;
