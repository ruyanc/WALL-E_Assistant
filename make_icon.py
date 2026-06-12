"""生成应用图标 assets/walle.ico。

使用瓦力动画首帧，居中绘制到正方形透明画布上，导出为 .ico。
运行：python make_icon.py
"""

import os
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


def main() -> None:
    app = QApplication([])
    _ = app
    assets = Path(__file__).resolve().parent / "assets"
    assets.mkdir(exist_ok=True)

    ico_path = assets / "walle.ico"
    big = _square_icon(256)
    if not big.save(str(ico_path), "ICO"):
        big.save(str(assets / "walle.png"), "PNG")
        print("已保存 PNG（当前平台不支持 ICO）")
    else:
        print(f"已生成图标: {ico_path}")


if __name__ == "__main__":
    main()
