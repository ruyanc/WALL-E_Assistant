"""打包前准备：应用图标（与桌面快捷方式一致）。"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def _project_root() -> Path:
    env = os.environ.get("WALLE_PROJECT_ROOT")
    if env:
        return Path(env)
    parent = ROOT.parent
    if (parent / "assets" / "walle.png").is_file() or (parent / "make_icon.py").is_file():
        return parent
    return parent


PROJECT_ROOT = _project_root()
ICON_SRC = PROJECT_ROOT / "assets" / "walle.png"
FONT_DST = ROOT / "assets" / "fonts" / "walle_ui.ttf"
FONT_BOLD_DST = ROOT / "assets" / "fonts" / "walle_ui_bold.ttf"


def _font_sources() -> list[Path]:
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    wsl_win = Path("/mnt/c/Windows/Fonts")
    names = ("simhei.ttf", "msyh.ttc", "msyhbd.ttc", "simsun.ttc")
    out: list[Path] = []
    for base in (win, wsl_win):
        for name in names:
            p = base / name
            if p.is_file():
                out.append(p)
    return out


def _bold_font_sources() -> list[Path]:
    win = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    wsl_win = Path("/mnt/c/Windows/Fonts")
    names = ("msyhbd.ttc", "simhei.ttf", "msyh.ttc")
    out: list[Path] = []
    for base in (win, wsl_win):
        for name in names:
            p = base / name
            if p.is_file():
                out.append(p)
    return out


def _copy_first(srcs: list[Path], dst: Path, label: str) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_file():
        return
    for src in srcs:
        shutil.copy2(src, dst)
        print(f"已复制{label} {src.name} -> {dst}")
        return
    raise SystemExit(f"未找到{label}字体，请手动复制到 {dst}")


def _ensure_font() -> None:
    _copy_first(_font_sources(), FONT_DST, "常规字体")


def _ensure_bold_font() -> None:
    try:
        _copy_first(_bold_font_sources(), FONT_BOLD_DST, "粗体字体")
    except SystemExit:
        if FONT_DST.is_file():
            shutil.copy2(FONT_DST, FONT_BOLD_DST)
            print(f"未找到粗体源，已用常规字体作为粗体占位 -> {FONT_BOLD_DST}")


def _ensure_icon() -> Path:
    if ICON_SRC.is_file():
        return ICON_SRC
    bundled = ROOT / "assets" / "icon.png"
    if bundled.is_file():
        return bundled
    print(f"未找到 {ICON_SRC}，尝试运行 make_icon.py ...")
    make_icon = PROJECT_ROOT / "make_icon.py"
    if sys.platform == "win32" and make_icon.is_file():
        subprocess.run([sys.executable, str(make_icon)], check=False, cwd=PROJECT_ROOT)
        if ICON_SRC.is_file():
            return ICON_SRC
    raise SystemExit(
        "缺少应用图标 assets/walle.png。\n"
        "请在 Windows 项目根目录运行：python make_icon.py\n"
        f"或在 WSL 构建前设置：export WALLE_PROJECT_ROOT=/mnt/c/.../WALL-E\n"
        f"当前查找路径：{ICON_SRC}"
    )


def _ensure_presplash(out_path: Path) -> None:
    """启动图：纯色背景（与 APP 底色一致），不显示瓦力欢迎页。"""
    size = 512
    bg = (245, 242, 237)
    try:
        from PIL import Image

        Image.new("RGB", (size, size), bg).save(out_path, "PNG")
        print(f"已生成纯色启动图（无欢迎页）-> {out_path}")
        return
    except ImportError:
        pass
    except Exception as exc:
        print(f"启动图生成失败 ({exc})")
    # 无 Pillow 时复制图标（仍比缺文件好）
    icon = out_path.parent / "icon.png"
    if icon.is_file():
        shutil.copy2(icon, out_path)


def main() -> int:
    _ensure_font()
    _ensure_bold_font()
    src = _ensure_icon()
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    shutil.copy2(src, assets / "icon.png")
    _ensure_presplash(assets / "presplash.png")
    print(f"已复制图标到 {assets}/icon.png（与桌面快捷方式一致）")
    print(f"中文字体：{FONT_DST}")
    print(f"粗体字体：{FONT_BOLD_DST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
