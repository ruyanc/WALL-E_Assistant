"""诊断眼睛瞳孔像素（无 GUI 窗口）。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from walle import walle_sprite as ws  # noqa: E402


def analyze_pm(pm: QPixmap, label: str) -> None:
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    w, h = img.width(), img.height()
    centers = ws._find_eye_centers(img)
    print(f"--- {label} {w}x{h} centers={centers}")
    for i, (cx, cy) in enumerate(centers):
        for r in (0, 2, 4, 6):
            c = img.pixelColor(cx + r, cy)
            print(
                f"  eye{i} ({cx + r},{cy}) lum={ws._lum(c):.0f} "
                f"a={c.alpha()} rgb=({c.red()},{c.green()},{c.blue()})"
            )
        trans = white = dark = 0
        for dy in range(-8, 9):
            for dx in range(-8, 9):
                if dx * dx + dy * dy > 64:
                    continue
                c = img.pixelColor(cx + dx, cy + dy)
                if c.alpha() < 30:
                    trans += 1
                elif ws._lum(c) > 200:
                    white += 1
                else:
                    dark += 1
        print(f"  eye{i} disk: transparent={trans} white={white} dark={dark}")


def main() -> None:
    app = QApplication([])
    frames = ROOT / "walle" / "assets" / "frames"

    raw = QPixmap(str(frames / "0_0.png"))
    analyze_pm(raw, "raw 0_0")
    analyze_pm(ws._defringe_pixmap(raw), "defringe 0_0")

    ws._load_frame.cache_clear()
    ws.get_frame_scaled.cache_clear()
    analyze_pm(ws.get_frame_scaled("0_0", 160), "idle scaled 160")
    analyze_pm(ws.get_frame_scaled("4_2", 400), "rest 4_2 scaled 400")
    analyze_pm(ws.get_frame_scaled("1_3", 160), "look 1_3 scaled 160")

    out = ROOT / "scripts" / "eye_diag_out.png"
    ws.get_frame_scaled("0_0", 160).save(str(out))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
