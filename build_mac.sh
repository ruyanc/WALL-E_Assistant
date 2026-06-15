#!/usr/bin/env bash
# WALL-E macOS 一键打包：生成 dist/WALL-E.app 与 dist/WALL-E.dmg
set -euo pipefail
cd "$(dirname "$0")"

if [ "$(uname -s)" != "Darwin" ]; then
  echo "[错误] DMG 只能在 macOS 上构建（需要 hdiutil 与 macOS 版 PyInstaller 产物）。"
  echo "  - 在 Mac 上运行: ./build_mac.sh"
  echo "  - 或在 Windows 触发 GitHub Actions: gh workflow run build-macos-dmg.yml"
  exit 1
fi

export MACOSX_DEPLOYMENT_TARGET="${MACOSX_DEPLOYMENT_TARGET:-11.0}"
VERSION="$(python3 scripts/read_version.py)"

echo "=== WALL-E macOS 打包 v${VERSION} ==="

echo "[1/4] Python 虚拟环境..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/4] 安装依赖..."
python -m pip install --upgrade pip -q
python -m pip install -r requirements-dev.txt -q

echo "[3/4] 图标与 PyInstaller 打包..."
python make_icon.py
python -m PyInstaller --noconfirm --clean WALL-E-mac.spec

echo "[4/4] 生成 DMG..."
bash scripts/build_dmg.sh

echo ""
echo "============================================================"
echo " 打包完成"
echo "   app: dist/WALL-E.app"
echo "   dmg: dist/WALL-E.dmg"
echo "   dmg: dist/WALL-E-${VERSION}.dmg"
echo " 将 DMG 发给 Mac 用户，拖入「应用程序」即可安装。"
echo "============================================================"
