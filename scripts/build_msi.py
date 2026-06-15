"""从 dist/WALL-E.exe 生成带安装向导的 MSI（Windows msilib）。"""

from __future__ import annotations

import os
import shutil
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "WALL-E.exe"
MSI = ROOT / "dist" / "WALL-E.msi"
ICO = ROOT / "assets" / "walle.ico"

PRODUCT_NAME = "WALL-E 桌面宠物"
PRODUCT_VERSION = "1.2.0"
MANUFACTURER = "WALL-E"
UPGRADE_CODE = "{8B2E4F1A-9C3D-4E5F-A6B7-1D2E3F4A5B6C}"
ICON_ID = "WalleIcon"

# 固定组件 GUID，便于覆盖升级
GUID_EXE = "{7A1D3E2B-8F4C-4D5E-9A6B-0C1D2E3F4A5B}"
GUID_SHORTCUT = "{6B0C2D1A-7E3B-4C4D-8A5B-9F0E1D2C3B4A}"
GUID_STARTUP = "{A1B2C3D4-E5F6-4A5B-8C9D-0E1F2A3B4C5D}"


def _add_icon(db, icon_path: Path) -> None:
    from msilib import CreateRecord, MSIMODIFY_INSERT, add_data

    view = db.OpenView("SELECT * FROM `Icon`")
    record = CreateRecord(2)
    record.SetString(1, ICON_ID)
    record.SetStream(2, str(icon_path))
    view.Modify(MSIMODIFY_INSERT, record)
    view.Close()
    add_data(db, "Property", [("ARPPRODUCTICON", ICON_ID)])


def _add_wizard_ui(db) -> None:
    from msilib import add_data, sequence, text

    import msi_wizard_ui

    add_data(db, "InstallExecuteSequence", sequence.InstallExecuteSequence)
    add_data(db, "InstallUISequence", msi_wizard_ui.InstallUISequence)
    add_data(db, "ActionText", text.ActionText)
    add_data(db, "UIText", text.UIText)
    for table in msi_wizard_ui.UI_TABLES:
        add_data(db, table, getattr(msi_wizard_ui, table))


def _add_desktop_shortcut(db, feature, exe_file_id: str) -> None:
    from msilib import add_data

    add_data(
        db,
        "Component",
        [("DesktopShortcut", GUID_SHORTCUT, "DesktopFolder", 4, "INSTALLDESKTOPSHORTCUT", "DesktopShortcutKey")],
    )
    add_data(db, "FeatureComponents", [(feature.id, "DesktopShortcut")])
    add_data(
        db,
        "Registry",
        [
            (
                "DesktopShortcutKey",
                1,  # HKEY_CURRENT_USER
                r"Software\WALL-E",
                "DesktopShortcut",
                1,
                "DesktopShortcut",
            )
        ],
    )
    add_data(
        db,
        "Shortcut",
        [
            (
                "DesktopShortcutLnk",
                "DesktopFolder",
                "WALL-E Assistant",
                "DesktopShortcut",
                f"[#{exe_file_id}]",
                None,
                PRODUCT_NAME,
                None,
                ICON_ID,
                0,
                1,
                "INSTALLDIR",
            )
        ],
    )


def _add_startup_shortcut(db, feature, exe_file_id: str) -> None:
    from msilib import add_data

    add_data(
        db,
        "Component",
        [("StartupShortcut", GUID_STARTUP, "StartupFolder", 4, "INSTALLSTARTUPSHORTCUT", "StartupShortcutKey")],
    )
    add_data(db, "FeatureComponents", [(feature.id, "StartupShortcut")])
    add_data(
        db,
        "Registry",
        [
            (
                "StartupShortcutKey",
                1,  # HKEY_CURRENT_USER
                r"Software\WALL-E",
                "StartupShortcut",
                1,
                "StartupShortcut",
            )
        ],
    )
    add_data(
        db,
        "Shortcut",
        [
            (
                "StartupShortcutLnk",
                "StartupFolder",
                "WALL-E Assistant",
                "StartupShortcut",
                f"[#{exe_file_id}]",
                None,
                PRODUCT_NAME,
                None,
                ICON_ID,
                0,
                1,
                "INSTALLDIR",
            )
        ],
    )


def _add_upgrade_table(db) -> None:
    from msilib import add_data

    add_data(
        db,
        "Upgrade",
        [
            (
                UPGRADE_CODE,
                "0.0.0",
                PRODUCT_VERSION,
                "",
                1,
                "",
                "OLDPRODUCTS",
            )
        ],
    )


def main() -> int:
    if sys.platform != "win32":
        print("MSI 打包仅支持 Windows。")
        return 1
    if not EXE.is_file():
        print(f"未找到 {EXE}，请先运行 build.bat 生成 exe。")
        return 1

    icon_path = ICO if ICO.is_file() else EXE

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import msilib
        import msilib.schema

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from msi_wizard_ui import WIZARD_PROPERTIES as wizard_props  # noqa: WPS433

    msi_path = MSI
    temp_msi = ROOT / "dist" / "WALL-E-build-temp.msi"
    if temp_msi.exists():
        temp_msi.unlink(missing_ok=True)

    def _open_db(path: Path):
        return msilib.init_database(
            str(path),
            msilib.schema,
            PRODUCT_NAME,
            msilib.gen_uuid(),
            PRODUCT_VERSION,
            MANUFACTURER,
        )

    try:
        db = _open_db(msi_path)
    except Exception:
        if msi_path != MSI:
            raise
        msi_path = temp_msi
        db = _open_db(msi_path)

    reserved = {
        "ProductName",
        "ProductCode",
        "ProductVersion",
        "Manufacturer",
        "ProductLanguage",
    }
    extra_props: list[tuple[str, str]] = [("UpgradeCode", UPGRADE_CODE)]
    seen = set(reserved)
    for key, val in wizard_props:
        if key in seen:
            continue
        seen.add(key)
        extra_props.append((key, val))
    msilib.add_data(db, "Property", extra_props)

    cab = msilib.CAB("walle.cab")
    feature = msilib.Feature(db, "Main", PRODUCT_NAME, "WALL-E", "WALLE", 1)
    feature.set_current()

    root = msilib.Directory(db, cab, None, ".", "TARGETDIR", "SourceDir", 0)
    local = msilib.Directory(
        db,
        cab,
        root,
        os.environ.get("LOCALAPPDATA", ""),
        "LocalAppDataFolder",
        "LocalApp",
        0,
    )
    install = msilib.Directory(db, cab, local, r"Programs\WALL-E", "INSTALLDIR", "WALLE", 0)

    # 桌面与开机启动快捷方式组件引用标准目录，必须在 Directory 表中声明
    msilib.add_data(
        db,
        "Directory",
        [
            ("DesktopFolder", "TARGETDIR", "Desktop"),
            ("StartupFolder", "TARGETDIR", "Startup"),
        ],
    )

    install.start_component("WalleExe", feature, 0, "WALL-E.exe", uuid=GUID_EXE)
    exe_file_id = install.add_file("WALL-E.exe", src=str(EXE))

    for manual_name in ("操作手册.md", "USER_GUIDE.md", "sync_config.example.json"):
        manual = ROOT / manual_name
        if manual.is_file():
            install.add_file(manual_name, src=str(manual))

    cloudbase_guide = ROOT / "GUIDE" / "sync" / "CLOUDBASE_SETUP.md"
    if cloudbase_guide.is_file():
        install.add_file("CLOUDBASE_SETUP.md", src=str(cloudbase_guide))

    _add_desktop_shortcut(db, feature, exe_file_id)
    _add_startup_shortcut(db, feature, exe_file_id)
    _add_upgrade_table(db)
    _add_icon(db, icon_path)
    _add_wizard_ui(db)

    cab.commit(db)
    if msi_path != MSI:
        shutil.copy2(msi_path, MSI.with_name("WALL-E-new.msi"))
        print(f"原 MSI 被占用，已生成：{MSI.with_name('WALL-E-new.msi')}")
        msi_path = MSI.with_name("WALL-E-new.msi")
    size_mb = msi_path.stat().st_size / (1024 * 1024)
    print(f"已生成 MSI：{msi_path}（约 {size_mb:.1f} MB）")
    print("包含：安装向导、可选桌面快捷方式/开机启动、卸载项、操作手册。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
