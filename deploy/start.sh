#!/usr/bin/env bash
# =============================================================
# 自然场景文种识别系统 - 一键部署脚本
# 目标服务器：Ubuntu   用户：szh   路径：/home/szh/system
# =============================================================
set -e

SYSTEM_DIR="/home/szh/system"
BACKEND_DIR="$SYSTEM_DIR/backend"
FRONTEND_DIR="$SYSTEM_DIR/frontend"
DB_NAME="c3f_db"
NGINX_CONF="/etc/nginx/sites-available/c3f"
NGINX_LINK="/etc/nginx/sites-enabled/c3f"
SERVICE_FILE="/etc/systemd/system/c3f.service"

echo "================================================================"
echo "  自然场景文种识别系统 - 部署脚本"
echo "================================================================"

# ── 1. 更新系统 & 安装依赖 ───────────────────────────────────
echo "[1/8] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y python3 python3-pip python3-venv \
     nginx mysql-server tesseract-ocr \
     libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev

# ── 2. 创建目录 ──────────────────────────────────────────────
echo "[2/8] 创建项目目录..."
mkdir -p "$BACKEND_DIR/uploads"
mkdir -p "$FRONTEND_DIR"

# ── 3. 部署代码（假设已 git clone 到当前目录）────────────────
echo "[3/8] 同步代码文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cp -r "$SCRIPT_DIR/backend/"* "$BACKEND_DIR/"
cp -r "$SCRIPT_DIR/frontend/"* "$FRONTEND_DIR/"
chmod 755 "$BACKEND_DIR/uploads"

# ── 4. Python 虚拟环境 & 安装依赖 ───────────────────────────
echo "[4/8] 配置 Python 虚拟环境..."
cd "$BACKEND_DIR"
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip -q
pip install -r requirements.txt -q
deactivate

# ── 5. 配置 MySQL ─────────────────────────────────────────────
echo "[5/8] 初始化数据库..."
echo "请手动输入 MySQL root 密码（或直接回车如果无密码）："
mysql -u root -p < "$SCRIPT_DIR/database/schema.sql" || \
  mysql -u root < "$SCRIPT_DIR/database/schema.sql"
echo "数据库初始化完成。"

# ── 6. 配置 Nginx ─────────────────────────────────────────────
echo "[6/8] 配置 Nginx..."
sudo cp "$SCRIPT_DIR/deploy/nginx.conf" "$NGINX_CONF"
sudo ln -sf "$NGINX_CONF" "$NGINX_LINK" 2>/dev/null || true
# 移除默认配置
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
sudo nginx -t && sudo systemctl reload nginx
echo "Nginx 配置完成。"

# ── 7. 创建 systemd 服务 ──────────────────────────────────────
echo "[7/8] 创建系统服务..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=C3F Natural Scene Language Recognition System
After=network.target mysql.service

[Service]
Type=simple
User=szh
WorkingDirectory=$BACKEND_DIR
ExecStart=$BACKEND_DIR/venv/bin/python app.py
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable c3f
sudo systemctl restart c3f
echo "系统服务启动完成。"

# ── 8. 完成 ───────────────────────────────────────────────────
echo "[8/8] 部署完成！"
echo ""
echo "================================================================"
echo "  访问地址：http://10.109.119.208/"
echo "  默认账号：admin / admin123"
echo "  默认账号：user1 / user123"
echo "================================================================"
echo ""
echo "服务状态查看：  sudo systemctl status c3f"
echo "后端日志查看：  sudo journalctl -u c3f -f"
echo "Nginx日志查看： sudo tail -f /var/log/nginx/c3f_access.log"
