# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 打包配置：生成单文件无控制台的 WALL-E.exe。"""

try:
    import certifi

    _certifi_data = [(certifi.where(), "certifi")]
except ImportError:
    _certifi_data = []

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('assets/walle.ico', 'assets'),
        ('walle/assets/frames', 'walle/assets/frames'),
        ('walle/assets/animations.json', 'walle/assets'),
        *_certifi_data,
    ],
    hiddenimports=['certifi'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # 排除用不到的大型 Qt 模块，减小体积
        'PySide6.QtWebEngineCore',
        'PySide6.QtWebEngineWidgets',
        'PySide6.Qt3DCore',
        'PySide6.QtCharts',
        'PySide6.QtDataVisualization',
        'PySide6.QtMultimedia',
        'PySide6.QtQuick3D',
        'PySide6.QtPdf',
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='WALL-E',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # 不显示控制台黑窗
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/walle.ico',
)
