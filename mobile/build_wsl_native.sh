#!/usr/bin/env bash
# 在 WSL 原生 ext4 目录（~/WALL-E-mobile）构建 APK，避免 /mnt/c 上 I/O 慢。
# 用法：在 WSL 内 cd 到 mobile 目录后执行 ./build_wsl_native.sh
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${WALLE_MOBILE_BUILD_DIR:-$HOME/WALL-E-mobile}"
VENV="$DEST/.venv-android"
export WALLE_PROJECT_ROOT="$(dirname "$SRC")"

echo "=== WALL-E Android 原生目录构建 ==="
echo "源: $SRC"
echo "目标: $DEST"
echo "项目根: $WALLE_PROJECT_ROOT"

mkdir -p "$DEST"
echo "[1/4] rsync 源码到 ext4 ..."
rsync -a --delete \
  --exclude '.buildozer' \
  --exclude 'bin' \
  --exclude '.venv-android' \
  --exclude '__pycache__' \
  --exclude '.git' \
  "$SRC/" "$DEST/"

if [[ ! -x "$VENV/bin/python" ]]; then
  echo "[2/4] 首次构建：安装虚拟环境与 buildozer ..."
  bash "$DEST/setup_wsl.sh"
else
  echo "[2/4] 准备资源与同步包 ..."
  "$VENV/bin/python" "$DEST/prepare_sync.py"
  "$VENV/bin/python" "$DEST/prepare_assets.py"
fi

echo "[3/4] buildozer android debug ..."
cd "$DEST"
source "$VENV/bin/activate"
python -m buildozer -v android debug

echo "[4/4] 复制 APK 回 Windows 目录 ..."
mkdir -p "$SRC/bin"
shopt -s nullglob
apks=("$DEST/bin"/*.apk)
if ((${#apks[@]} == 0)); then
  echo "未找到 APK，请检查 buildozer 输出"
  exit 1
fi
cp -v "${apks[@]}" "$SRC/bin/"
echo ""
echo "完成。APK 位于: $SRC/bin/"
