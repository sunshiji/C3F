#!/usr/bin/env bash
# =============================================================
# 自然场景文种识别系统 - 一键部署脚本（无 sudo 版）
# 目标服务器：Ubuntu   用户：szh   路径：/home/szh/system/C3F
# 环境管理：Conda（/home/szh/anaconda3）无代理
# 说明：全程不需要 sudo 权限；后端通过用户级 systemd 管理；
#       前端由 Flask 直接托管，访问端口 5000。
# =============================================================
set -e

CONDA_BASE="/home/szh/anaconda3"
CONDA_ENV="c3f"
CONDA_BIN="$CONDA_BASE/bin/conda"
CONDA_PYTHON="$CONDA_BASE/envs/$CONDA_ENV/bin/python"

SYSTEM_DIR="/home/szh/system/C3F"
BACKEND_DIR="$SYSTEM_DIR/backend"
FRONTEND_DIR="$SYSTEM_DIR/frontend"

# ── 数据库连接参数（可通过环境变量覆盖）─────────────────────────
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-3306}"
DB_USER="${DB_USER:-c3f_user}"
DB_PASSWORD="${DB_PASSWORD:-c3f_pass}"
DB_NAME="${DB_NAME:-c3f_db}"

USER_SYSTEMD_DIR="$HOME/.config/systemd/user"
SERVICE_FILE="$USER_SYSTEMD_DIR/c3f.service"

echo "================================================================"
echo "  自然场景文种识别系统 - 部署脚本（无 sudo / Conda）"
echo "================================================================"

# ── 前置检查 ──────────────────────────────────────────────────
echo "[检查] 确认 conda 可用..."
if [ ! -f "$CONDA_BIN" ]; then
    echo "[错误] 未在 $CONDA_BASE 找到 conda，请检查安装路径。"
    exit 1
fi
echo "  conda：$CONDA_BIN ✓"

# ── 1. 系统依赖提示（无 sudo，需管理员预装）──────────────────
echo "[1/6] 系统依赖检查（本步骤不安装，仅提示）..."
missing_hint=0
for cmd in mysql tesseract; do
    if ! command -v "$cmd" &>/dev/null; then
        echo "  [提示] 命令 '$cmd' 未找到，请联系管理员确认已安装对应软件包。"
        missing_hint=1
    fi
done
# 检查 libGL（EasyOCR/OpenCV 需要）
if ! ldconfig -p 2>/dev/null | grep -q "libGL\.so"; then
    echo "  [提示] 未检测到 libGL，若 OCR 功能异常请联系管理员安装 libgl1。"
    missing_hint=1
fi
[ "$missing_hint" -eq 0 ] && echo "  系统依赖检查通过 ✓"

# ── 2. 创建目录 ───────────────────────────────────────────────
echo "[2/6] 创建项目目录..."
mkdir -p "$BACKEND_DIR/uploads"
mkdir -p "$FRONTEND_DIR"
mkdir -p "$SYSTEM_DIR/logs"   # nginx 日志目录（可选 nginx 使用）
echo "  目录创建完成 ✓"

# ── 3. 同步代码 ───────────────────────────────────────────────
echo "[3/6] 同步代码文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
if [ "$(realpath "$SCRIPT_DIR")" = "$(realpath "$SYSTEM_DIR")" ]; then
    echo "  检测到原地部署（脚本已在 $SYSTEM_DIR 中），跳过文件复制。"
else
    cp -r "$SCRIPT_DIR/backend/"*  "$BACKEND_DIR/"
    cp -r "$SCRIPT_DIR/frontend/"* "$FRONTEND_DIR/"
fi
chmod 755 "$BACKEND_DIR/uploads"
echo "  代码同步完成 ✓"

# ── 4. Conda 环境 & 依赖 ──────────────────────────────────────
echo "[4/6] 配置 Conda 环境（关闭代理）..."

# 禁用代理，避免无代理网络时请求超时
"$CONDA_BIN" config --set proxy_servers.http  "" 2>/dev/null || true
"$CONDA_BIN" config --set proxy_servers.https "" 2>/dev/null || true

# 若环境已存在则跳过创建
if "$CONDA_BIN" env list | grep -q "^$CONDA_ENV "; then
    echo "  Conda 环境 '$CONDA_ENV' 已存在，跳过创建。"
else
    "$CONDA_BIN" env create \
        -n "$CONDA_ENV" \
        -f "$SCRIPT_DIR/deploy/environment.yml" \
        --no-default-packages
fi

# pip 安装时同样禁用代理
"$CONDA_BASE/envs/$CONDA_ENV/bin/pip" install \
    --no-proxy \
    -r "$BACKEND_DIR/requirements.txt" -q

echo "  Conda 环境配置完成 ✓  Python：$CONDA_PYTHON"

# ── 5. 数据库初始化 ───────────────────────────────────────────
echo "[5/6] 初始化数据库（MySQL 需已由管理员安装并运行）..."
if ! command -v mysql &>/dev/null; then
    echo "  [跳过] mysql 客户端未找到，跳过数据库检查。"
    echo "  请联系管理员依次执行："
    echo "    1. mysql -u root -p < $SCRIPT_DIR/database/schema.sql"
    echo "    2. mysql -u root -p < $SCRIPT_DIR/deploy/db_admin_setup.sql"
elif MYSQL_PWD="$DB_PASSWORD" mysql -u "$DB_USER" -h "$DB_HOST" -P "$DB_PORT" \
         -e "SELECT 1" "$DB_NAME" >/dev/null 2>&1; then
    echo "  数据库连接正常，跳过重复初始化 ✓"
else
    echo "  [提示] 无法以用户 '$DB_USER' 连接数据库 '$DB_NAME'。"
    echo ""
    echo "  ── 请联系管理员执行以下命令（需 MySQL root 权限）──"
    echo "    步骤 1：建库建表（首次部署）"
    echo "      mysql -u root -p < $SCRIPT_DIR/database/schema.sql"
    echo "    步骤 2：创建应用用户并授权"
    echo "      mysql -u root -p < $SCRIPT_DIR/deploy/db_admin_setup.sql"
    echo "  ─────────────────────────────────────────────────────"
    echo ""
    echo "  若管理员使用了自定义密码，请以如下方式重新运行部署脚本："
    echo "    DB_PASSWORD=<实际密码> bash deploy/start.sh"
    echo ""
    echo "  数据库配置完成前，应用将无法正常登录。"
fi

# ── 6. 用户级 systemd 服务 ────────────────────────────────────
echo "[6/6] 创建用户级 systemd 服务（无需 sudo）..."
mkdir -p "$USER_SYSTEMD_DIR"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=C3F Natural Scene Language Recognition System
After=network.target

[Service]
Type=simple
WorkingDirectory=$BACKEND_DIR
ExecStart=$CONDA_PYTHON $BACKEND_DIR/app.py
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"
Environment="DB_HOST=$DB_HOST"
Environment="DB_PORT=$DB_PORT"
Environment="DB_USER=$DB_USER"
Environment="DB_PASSWORD=$DB_PASSWORD"
Environment="DB_NAME=$DB_NAME"

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable c3f
systemctl --user restart c3f
echo "  用户服务启动完成 ✓"

# ── 完成 ──────────────────────────────────────────────────────
echo ""
echo "================================================================"
echo "  部署完成！"
echo ""
echo "  访问地址：http://10.109.119.208:5000/"
echo "  默认账号：admin / admin123"
echo "  默认账号：user1 / user123"
echo ""
echo "  注：如需开机自动启动（注销后保持运行），请联系管理员执行："
echo "      loginctl enable-linger szh"
echo "================================================================"
echo ""
echo "服务状态查看：  systemctl --user status c3f"
echo "后端日志查看：  journalctl --user -u c3f -f"
echo "快速重启：      bash $SYSTEM_DIR/deploy/restart_backend.sh"
