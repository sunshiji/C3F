#!/usr/bin/env bash
# 仅重启后端服务（不重新安装依赖）
BACKEND_DIR="/home/szh/system/backend"
cd "$BACKEND_DIR"
source venv/bin/activate
pkill -f "python app.py" 2>/dev/null || true
nohup python app.py > /tmp/c3f_backend.log 2>&1 &
echo "后端已在后台启动，PID=$!"
echo "日志：tail -f /tmp/c3f_backend.log"
