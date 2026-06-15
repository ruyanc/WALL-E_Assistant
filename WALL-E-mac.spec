# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：生成 macOS WALL-E.app。"""

import re
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

_root = Path(SPECPATH)
_version = re.search(
    r"__version__\s*=\s*[\"']([^\"']+)[\"']",
    (_root / "walle" / "__init__.py").read_text(encoding="utf-8"),
).group(1)

_icon = _root / "assets" / "walle.icns"
if not _icon.is_file():
    _icon = _root / "assets" / "walle.png"

_datas = [
    (_root / "assets" / "walle.png", "assets"),
    (_root / "walle" / "assets" / "frames", "walle/assets/frames"),
    (_root / "walle" / "assets" / "animations.json", "walle/assets"),
]
_icns = _root / "assets" / "walle.icns"
if _icns.is_file():
    _datas.append((str(_icns), "assets"))

try:
    import certifi

    _datas.append((certifi.where(), "certifi/cacert.pem"))
except ImportError:
    pass

hiddenimports = collect_submodules("walle.sync")
hiddenimports.append("certifi")

a = Analysis(
    [str(_root / "run.py")],
    pathex=[str(_root)],
    binaries=[],
    datas=_datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "PySide6.QtWebEngineCore",
        "PySide6.QtWebEngineWidgets",
        "PySide6.Qt3DCore",
        "PySide6.QtCharts",
        "PySide6.QtDataVisualization",
        "PySide6.QtMultimedia",
        "PySide6.QtQuick3D",
        "PySide6.QtPdf",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="WALL-E",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="WALL-E",
)

app = BUNDLE(
    coll,
    name="WALL-E.app",
    icon=str(_icon) if _icon.is_file() else None,
    bundle_identifier="org.walle.pet",
    info_plist={
        "NSHighResolutionCapable": True,
        "CFBundleName": "WALL-E",
        "CFBundleDisplayName": "WALL-E Desktop Pet",
        "CFBundleShortVersionString": _version,
        "CFBundleVersion": _version,
        "LSMinimumSystemVersion": "11.0",
    },
)
