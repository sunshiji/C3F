#!/usr/bin/env bash
# 仅重启后端服务（不重新安装依赖）
BACKEND_DIR="/home/szh/system/C3F/backend"
CONDA_ENV="c3f"

# 定位 conda 安装目录
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
    echo "[错误] 未找到 conda，请设置 CONDA_BASE 环境变量后重试。"
    exit 1
fi

CONDA_PYTHON="$CONDA_BASE/envs/$CONDA_ENV/bin/python"

cd "$BACKEND_DIR"
pkill -f "python app.py" 2>/dev/null || true
nohup "$CONDA_PYTHON" app.py > /tmp/c3f_backend.log 2>&1 &
echo "后端已在后台启动，PID=$!"
echo "日志：tail -f /tmp/c3f_backend.log"
