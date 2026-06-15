#!/usr/bin/env bash
# WSL/Ubuntu：创建含 pip 的虚拟环境并安装 buildozer
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv-android"

echo "=== WALL-E Android 构建环境 ==="

if ! command -v python3 >/dev/null; then
  echo "请先安装: sudo apt install python3 python3-venv python3-full"
  exit 1
fi

echo "[1/6] 删除旧虚拟环境（若存在）..."
rm -rf "$VENV"

echo "[2/6] 创建虚拟环境 $VENV ..."
python3 -m venv "$VENV"

PY="$VENV/bin/python"
if [[ ! -x "$PY" ]]; then
  echo "虚拟环境创建失败"
  exit 1
fi

echo "[3/6] 安装 pip（NTFS /mnt/c 上 venv 常不带 pip，需手动引导）..."
if ! "$PY" -m pip --version >/dev/null 2>&1; then
  "$PY" -m ensurepip --upgrade 2>/dev/null || true
fi
if ! "$PY" -m pip --version >/dev/null 2>&1; then
  echo "      ensurepip 不可用，使用 get-pip.py ..."
  curl -fsSL https://bootstrap.pypa.io/get-pip.py -o /tmp/get-pip-walle.py
  "$PY" /tmp/get-pip-walle.py
  rm -f /tmp/get-pip-walle.py
fi

"$PY" -m pip --version

echo "[4/6] 安装 buildozer、cython、pillow ..."
"$PY" -m pip install -U pip wheel
"$PY" -m pip install "cython<3.1" buildozer pillow

echo "[5/6] 配置 Gradle 国内镜像（避免 dl.google.com SSL 失败）..."
mkdir -p "$HOME/.gradle/init.d"
cp "$ROOT/gradle/china-mirror.gradle" "$HOME/.gradle/init.d/china-mirror.gradle"

echo "[6/6] 准备同步包与应用资源 ..."
"$PY" "$ROOT/prepare_sync.py"
"$PY" "$ROOT/prepare_assets.py"

echo ""
echo "完成。打包 APK："
echo ""
echo "  推荐（更快，ext4 原生目录）："
echo "    chmod +x build_wsl_native.sh && ./build_wsl_native.sh"
echo ""
echo "  或在本目录直接构建（/mnt/c 较慢）："
echo "  source $VENV/bin/activate"
echo "  python -m buildozer -v android debug"
echo ""
echo "若仍提示 externally-managed-environment，请始终用："
echo "  $PY -m pip install <包名>"
echo "  $PY -m buildozer -v android debug"
