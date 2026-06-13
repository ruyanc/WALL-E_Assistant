#!/usr/bin/env bash
# 将 dist/WALL-E.app 封装为可分发 DMG（含 Applications 快捷方式）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/WALL-E.app"
DMG="$ROOT/dist/WALL-E.dmg"
STAGING="$ROOT/build/dmg-staging"

if [ ! -d "$APP" ]; then
  echo "[错误] 未找到 $APP，请先运行 ./build_mac.sh"
  exit 1
fi

rm -f "$DMG"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -sf /Applications "$STAGING/Applications"

hdiutil create -volname "WALL-E" -srcfolder "$STAGING" -ov -format UDZO "$DMG"
rm -rf "$STAGING"

echo "[DMG] 已生成: $DMG"
