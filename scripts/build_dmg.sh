#!/usr/bin/env bash
# 将 dist/WALL-E.app 封装为可分发 DMG（含 Applications 快捷方式）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="$ROOT/dist/WALL-E.app"
STAGING="$ROOT/build/dmg-staging"
VERSION="$(python3 "$ROOT/scripts/read_version.py")"
DMG_VERSIONED="$ROOT/dist/WALL-E-${VERSION}.dmg"
DMG_DEFAULT="$ROOT/dist/WALL-E.dmg"

if [ ! -d "$APP" ]; then
  echo "[错误] 未找到 $APP，请先运行 ./build_mac.sh"
  exit 1
fi

rm -f "$DMG_VERSIONED" "$DMG_DEFAULT"
rm -rf "$STAGING"
mkdir -p "$STAGING"
cp -R "$APP" "$STAGING/"
ln -sf /Applications "$STAGING/Applications"

for doc in "操作手册.md" "USER_GUIDE.md" "sync_config.example.json"; do
  if [ -f "$ROOT/$doc" ]; then
    cp "$ROOT/$doc" "$STAGING/"
  fi
done
if [ -f "$ROOT/GUIDE/sync/CLOUDBASE_SETUP.md" ]; then
  cp "$ROOT/GUIDE/sync/CLOUDBASE_SETUP.md" "$STAGING/CLOUDBASE_SETUP.md"
fi

hdiutil create -volname "WALL-E" -srcfolder "$STAGING" -ov -format UDZO "$DMG_VERSIONED"
cp -f "$DMG_VERSIONED" "$DMG_DEFAULT"
rm -rf "$STAGING"

echo "[DMG] 已生成:"
echo "       $DMG_VERSIONED"
echo "       $DMG_DEFAULT"
