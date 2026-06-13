"""将桌面版动画资源复制到 mobile/assets（打包 APK 前执行）。"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT.parent / "walle" / "assets"
DST = ROOT / "assets"


def main() -> int:
    if not (SRC / "frames").is_dir():
        print(f"未找到 {SRC / 'frames'}，请先确认桌面版资源存在。")
        return 1
    if DST.exists():
        shutil.rmtree(DST)
    shutil.copytree(SRC, DST)
    n = len(list((DST / "frames").glob("*.png")))
    print(f"已复制资源到 {DST}（{n} 张帧图）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
