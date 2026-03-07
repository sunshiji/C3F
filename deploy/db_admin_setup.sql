-- =============================================================
-- C3F 数据库用户授权脚本（需要 MySQL root 权限，管理员执行一次）
-- =============================================================
-- 前置条件：请先以 root 执行 database/schema.sql 完成建库建表
--   mysql -u root -p < database/schema.sql
--
-- 然后执行本脚本，创建应用专用用户并授权：
--   mysql -u root -p < deploy/db_admin_setup.sql
--
-- 若需自定义用户名或密码，直接修改下方的 'c3f_user' 和 'c3f_pass'，
-- 并在启动应用前通过环境变量告知应用：
--   DB_USER=your_user DB_PASSWORD=your_pass bash deploy/start.sh
-- =============================================================

-- 创建应用专用数据库账号（仅能访问 c3f_db，不影响其他库）
CREATE USER IF NOT EXISTS 'c3f_user'@'localhost' IDENTIFIED BY 'c3f_pass';

-- 授予对 c3f_db 的完整权限
GRANT ALL PRIVILEGES ON c3f_db.* TO 'c3f_user'@'localhost';

FLUSH PRIVILEGES;

SELECT '数据库用户 c3f_user 授权完成 ✓' AS status;
