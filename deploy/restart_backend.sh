#!/usr/bin/env bash
# 仅重启后端服务（不重新安装依赖）
CONDA_BASE="/home/szh/anaconda3"
CONDA_ENV="c3f"
CONDA_PYTHON="$CONDA_BASE/envs/$CONDA_ENV/bin/python"
BACKEND_DIR="/home/szh/system/C3F/backend"

cd "$BACKEND_DIR"
pkill -f "python app.py" 2>/dev/null || true
nohup "$CONDA_PYTHON" app.py > /tmp/c3f_backend.log 2>&1 &
echo "后端已在后台启动，PID=$!"
echo "日志：tail -f /tmp/c3f_backend.log"
