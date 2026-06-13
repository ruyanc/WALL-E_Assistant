#!/usr/bin/env bash
# WALL-E macOS 一键打包：生成 dist/WALL-E.app 与 dist/WALL-E.dmg
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/4] Python 虚拟环境..."
if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/4] 安装依赖..."
python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt

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
echo " 将 DMG 发给 Mac 用户，拖入「应用程序」即可安装。"
echo "============================================================"
