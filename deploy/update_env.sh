#!/usr/bin/env bash
# =============================================================
# 自然场景文种识别系统 - 已有环境依赖更新脚本
# =============================================================
# 用途：Conda 环境 c3f 已存在的情况下，只替换/更新 pip 依赖。
#       不重新创建环境，不重复安装 Conda 包，速度快。
#
# 适用场景：
#   - 代码更新后 requirements.txt 发生变化（新增或删除了依赖）
#   - 从旧版本（含 PyMySQL）升级到新版本（SQLite-only）
#
# 用法：
#   bash deploy/update_env.sh
# =============================================================
set -e

CONDA_BASE="${CONDA_BASE:-/home/szh/anaconda3}"
CONDA_ENV="c3f"
CONDA_BIN="$CONDA_BASE/bin/conda"
PIP="$CONDA_BASE/envs/$CONDA_ENV/bin/pip"
SYSTEM_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$SYSTEM_DIR/backend"

echo "================================================================"
echo "  C3F - 依赖更新脚本（仅更新 pip 包，不重建 Conda 环境）"
echo "================================================================"

# ── 检查环境是否存在 ─────────────────────────────────────────
if [ ! -f "$PIP" ]; then
    echo "[错误] Conda 环境 '$CONDA_ENV' 不存在或路径有误。"
    echo "  请先运行完整部署脚本：bash deploy/start.sh"
    exit 1
fi
echo "[检查] Conda 环境 '$CONDA_ENV' 已存在 ✓"

# ── 禁用代理 ─────────────────────────────────────────────────
"$CONDA_BIN" config --set proxy_servers.http  "" 2>/dev/null || true
"$CONDA_BIN" config --set proxy_servers.https "" 2>/dev/null || true

# ── 1. 卸载已从依赖列表中移除的包 ────────────────────────────
echo "[1/2] 卸载已移除的依赖..."
# ⚠️  每次从依赖中删除一个包时，请在这里手动添加对应的 uninstall 行
REMOVED_PACKAGES=(
    pymysql     # 从 MySQL 迁移到 SQLite 后移除
)
any_removed=0
for pkg in "${REMOVED_PACKAGES[@]}"; do
    if "$PIP" show "$pkg" >/dev/null 2>&1; then
        "$PIP" uninstall -y "$pkg"
        echo "  已卸载: $pkg ✓"
        any_removed=1
    else
        echo "  $pkg 未安装，跳过"
    fi
done
[ "$any_removed" -eq 0 ] && echo "  无需卸载的包 ✓"

# ── 2. 安装/更新当前 requirements.txt 中的所有包 ─────────────
echo "[2/2] 安装/更新依赖（--no-proxy）..."
"$PIP" install --no-proxy -r "$BACKEND_DIR/requirements.txt"
echo "  依赖更新完成 ✓"

# ── 完成 ──────────────────────────────────────────────────────
echo ""
echo "================================================================"
echo "  依赖更新完成！"
echo ""
echo "  如需重启后端服务，请执行："
echo "    systemctl --user restart c3f"
echo "  或："
echo "    bash $SYSTEM_DIR/deploy/restart_backend.sh"
echo "================================================================"
