"""验证瞳孔透明区域已填为黑色（无透明/白色双瞳孔）。"""
from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from walle import walle_sprite as ws  # noqa: E402


def pupil_opaque_dark_ratio(pm: QPixmap, cx: int, cy: int, pupil_r: int) -> float:
    img = pm.toImage().convertToFormat(QImage.Format_ARGB32)
    ok = total = 0
    r2 = pupil_r * pupil_r
    for dy in range(-pupil_r, pupil_r + 1):
        for dx in range(-pupil_r, pupil_r + 1):
            if dx * dx + dy * dy > r2:
                continue
            x, y = cx + dx, cy + dy
            if not (0 <= x < img.width() and 0 <= y < img.height()):
                continue
            c = img.pixelColor(x, y)
            total += 1
            if c.alpha() >= 240 and ws._lum(c) < 40:
                ok += 1
    return ok / total if total else 0.0


def main() -> int:
    app = QApplication([])
    ws._load_frame.cache_clear()
    ws._eye_centers_for_frame.cache_clear()
    ws.get_frame_scaled.cache_clear()

    checks = [
        ("idle", "0_0", 160),
        ("idle", "0_1", 160),
        ("look", "1_3", 160),
        ("rest", "4_2", 400),
        ("talk", "6_0", 160),
    ]
    failed = []
    for anim, frame, size in checks:
        pm = ws.get_frame_scaled(frame, size)
        img = pm.toImage()
        raw = ws._defringe_pixmap(
            QPixmap(str(ROOT / "walle" / "assets" / "frames" / f"{frame}.png"))
        ).toImage()
        centers = ws._find_eye_centers(raw)
        if len(centers) < 2:
            failed.append(f"{anim}/{frame}: only {len(centers)} eye(s) detected")
            continue
        rw, rh = raw.width(), raw.height()
        w, h = img.width(), img.height()
        pr = max(4, int(round(min(w, h) * 0.022)))
        scaled = [(int(cx * w / rw), int(cy * h / rh)) for cx, cy in centers]
        ratios = [pupil_opaque_dark_ratio(pm, cx, cy, pr) for cx, cy in scaled]
        ok = all(r >= 0.65 for r in ratios)
        status = "OK" if ok else "FAIL"
        print(f"{status} {anim}/{frame}@{size} centers={scaled} dark={ratios}")
        if not ok:
            failed.append(f"{anim}/{frame}: dark ratios {ratios}")

    if failed:
        print("FAILED:")
        for line in failed:
            print(" ", line)
        return 1
    print("all eye checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
