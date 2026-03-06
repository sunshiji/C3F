#!/usr/bin/env bash
# =============================================================
# 自然场景文种识别系统 - 一键部署脚本
# 目标服务器：Ubuntu   用户：szh   路径：/home/szh/system/C3F
# 环境管理：Conda（不使用代理）
# =============================================================
set -e

SYSTEM_DIR="/home/szh/system/C3F"
BACKEND_DIR="$SYSTEM_DIR/backend"
FRONTEND_DIR="$SYSTEM_DIR/frontend"
CONDA_ENV="c3f"
NGINX_CONF="/etc/nginx/sites-available/c3f"
NGINX_LINK="/etc/nginx/sites-enabled/c3f"
SERVICE_FILE="/etc/systemd/system/c3f.service"

echo "================================================================"
echo "  自然场景文种识别系统 - 部署脚本（Conda 版）"
echo "================================================================"

# ── 定位 conda 安装目录 ────────────────────────────────────────
# 依次检查常见路径；也可通过环境变量 CONDA_BASE 覆盖
if [ -z "$CONDA_BASE" ]; then
    for _candidate in \
        "$HOME/miniconda3" "$HOME/anaconda3" \
        "/opt/miniconda3"  "/opt/anaconda3"  \
        "/opt/conda"
    do
        if [ -f "$_candidate/bin/conda" ]; then
            CONDA_BASE="$_candidate"
            break
        fi
    done
fi

if [ -z "$CONDA_BASE" ]; then
    echo "[错误] 未找到 conda，请将 conda 安装目录赋值给 CONDA_BASE 后重试。"
    echo "  例如：CONDA_BASE=/home/szh/miniconda3 bash deploy/start.sh"
    exit 1
fi

CONDA_BIN="$CONDA_BASE/bin/conda"
CONDA_PYTHON="$CONDA_BASE/envs/$CONDA_ENV/bin/python"
echo "  使用 conda：$CONDA_BIN"

# ── 1. 系统依赖（不含 python3-pip / python3-venv）─────────────
echo "[1/8] 安装系统依赖..."
sudo apt-get update -qq
sudo apt-get install -y \
     nginx mysql-server tesseract-ocr \
     libgl1 libglib2.0-0 libsm6 libxext6 libxrender-dev

# ── 2. 创建目录 ───────────────────────────────────────────────
echo "[2/8] 创建项目目录..."
mkdir -p "$BACKEND_DIR/uploads"
mkdir -p "$FRONTEND_DIR"

# ── 3. 同步代码 ───────────────────────────────────────────────
echo "[3/8] 同步代码文件..."
SCRIPT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cp -r "$SCRIPT_DIR/backend/"*  "$BACKEND_DIR/"
cp -r "$SCRIPT_DIR/frontend/"* "$FRONTEND_DIR/"
chmod 755 "$BACKEND_DIR/uploads"

# ── 4. Conda 环境 & 依赖 ──────────────────────────────────────
echo "[4/8] 配置 Conda 环境（关闭代理）..."

# 显式禁用 conda 代理，避免无代理服务器时请求超时
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

# 在 conda 环境内通过 pip 安装时同样禁用代理
"$CONDA_BASE/envs/$CONDA_ENV/bin/pip" install \
    --no-proxy \
    -r "$BACKEND_DIR/requirements.txt" -q

echo "  Conda 环境配置完成，Python：$CONDA_PYTHON"

# ── 5. 数据库 ─────────────────────────────────────────────────
echo "[5/8] 初始化数据库..."
echo "请输入 MySQL root 密码（无密码直接回车）："
mysql -u root -p < "$SCRIPT_DIR/database/schema.sql" || \
  mysql -u root   < "$SCRIPT_DIR/database/schema.sql"
echo "  数据库初始化完成。"

# ── 6. Nginx ──────────────────────────────────────────────────
echo "[6/8] 配置 Nginx..."
sudo cp "$SCRIPT_DIR/deploy/nginx.conf" "$NGINX_CONF"
sudo ln -sf "$NGINX_CONF" "$NGINX_LINK" 2>/dev/null || true
sudo rm -f /etc/nginx/sites-enabled/default 2>/dev/null || true
sudo nginx -t && sudo systemctl reload nginx
echo "  Nginx 配置完成。"

# ── 7. systemd 服务（使用 conda 环境的 python 绝对路径）────────
echo "[7/8] 创建系统服务..."
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=C3F Natural Scene Language Recognition System
After=network.target mysql.service

[Service]
Type=simple
User=szh
WorkingDirectory=$BACKEND_DIR
ExecStart=$CONDA_PYTHON $BACKEND_DIR/app.py
Restart=always
RestartSec=5
Environment="PYTHONUNBUFFERED=1"

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable c3f
sudo systemctl restart c3f
echo "  服务启动完成。"

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
