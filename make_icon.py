"""生成应用图标 assets/walle.ico / walle.png / walle.icns。

使用瓦力动画首帧，居中绘制到正方形透明画布上。
Windows 导出 .ico；macOS 额外生成 .icns 供 .app / DMG 使用。
运行：python make_icon.py
"""

import os
import shutil
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QColor, QImage, QPainter, QPixmap  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from walle.walle_sprite import render_walle  # noqa: E402


def _square_icon(side: int) -> QPixmap:
    """把瓦力帧居中放入 side×side 透明正方形画布。"""
    frame = render_walle(int(side * 0.92), state="idle")
    canvas = QImage(side, side, QImage.Format_ARGB32)
    canvas.fill(QColor(0, 0, 0, 0))
    p = QPainter(canvas)
    p.setRenderHint(QPainter.SmoothPixmapTransform, True)
    ox = (side - frame.width()) // 2
    oy = (side - frame.height()) // 2
    p.drawPixmap(ox, oy, frame)
    p.end()
    return QPixmap.fromImage(canvas)


def _write_icns(assets: Path, png_path: Path) -> Path | None:
    if sys.platform != "darwin":
        return None
    iconset = assets / "walle.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir()
    entries = [
        ("icon_16x16.png", 16),
        ("icon_16x16@2x.png", 32),
        ("icon_32x32.png", 32),
        ("icon_32x32@2x.png", 64),
        ("icon_128x128.png", 128),
        ("icon_128x128@2x.png", 256),
        ("icon_256x256.png", 256),
        ("icon_256x256@2x.png", 512),
        ("icon_512x512.png", 512),
        ("icon_512x512@2x.png", 1024),
    ]
    for name, size in entries:
        out = iconset / name
        subprocess.run(["sips", "-z", str(size), str(size), str(png_path), "--out", str(out)], check=True)
    icns_path = assets / "walle.icns"
    subprocess.run(["iconutil", "-c", "icns", str(iconset), "-o", str(icns_path)], check=True)
    shutil.rmtree(iconset)
    return icns_path


def main() -> None:
    app = QApplication([])
    _ = app
    assets = Path(__file__).resolve().parent / "assets"
    assets.mkdir(exist_ok=True)

    png_path = assets / "walle.png"
    _square_icon(256).save(str(png_path), "PNG")
    print(f"已生成 PNG: {png_path}")

    ico_path = assets / "walle.ico"
    if _square_icon(256).save(str(ico_path), "ICO"):
        print(f"已生成 ICO: {ico_path}")
    else:
        print("当前平台未写入 ICO（Windows 打包请在本机运行）")

    icns = _write_icns(assets, png_path)
    if icns:
        print(f"已生成 ICNS: {icns}")


if __name__ == "__main__":
    main()
