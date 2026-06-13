"""验证 WALL-E.msi 安装包结构与安装结果。"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist" / "WALL-E.exe"
MSI = ROOT / "dist" / "WALL-E.msi"
ICON_ID = "WalleIcon"
EXPECTED_PRODUCT = "WALL-E 桌面宠物"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _query_msi(msi_path: Path) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        import msilib

    db = msilib.OpenDatabase(str(msi_path), msilib.MSIDBOPEN_READONLY)
    out: dict = {"properties": {}, "icons": [], "files": [], "directories": [], "features": []}

    def fetch(sql: str, cols: int) -> list:
        view = db.OpenView(sql)
        view.Execute(None)
        rows = []
        while True:
            rec = view.Fetch()
            if rec is None:
                break
            rows.append(tuple(rec.GetString(i + 1) for i in range(cols)))
        view.Close()
        return rows

    for key, val in fetch("SELECT Property, Value FROM Property", 2):
        out["properties"][key] = val

    out["icons"] = fetch("SELECT Name FROM Icon", 1)
    out["files"] = fetch("SELECT File, Component_, FileName, FileSize FROM File", 4)
    out["directories"] = fetch("SELECT Directory, Directory_Parent, DefaultDir FROM Directory", 3)
    out["features"] = fetch("SELECT Feature, Title, Level FROM Feature", 3)
    try:
        out["shortcuts"] = fetch("SELECT Shortcut, Directory_, Name FROM Shortcut", 3)
    except Exception:
        out["shortcuts"] = []
    try:
        out["ui_sequence"] = fetch("SELECT Action, Sequence FROM InstallUISequence", 2)
    except Exception:
        out["ui_sequence"] = []
    db.Close()
    return out


def _icon_ok(meta: dict) -> bool:
    """Icon 表与 ARPPRODUCTICON 一致。"""
    names = {n for (n,) in meta["icons"]}
    arp = meta["properties"].get("ARPPRODUCTICON", "")
    return arp in names or arp == ICON_ID or arp == f"{ICON_ID}.ico"


def _quiet_install(msi_path: Path) -> int:
    proc = subprocess.run(
        ["msiexec", "/i", str(msi_path), "/qn", "/norestart"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.returncode


def _installed_exe() -> Path:
    return Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "WALL-E" / "WALL-E.exe"


def main() -> int:
    if sys.platform != "win32":
        print("仅支持 Windows。")
        return 1

    failed: list[str] = []

    if not MSI.is_file():
        failed.append(f"未找到 {MSI}")
        print("FAILED")
        for line in failed:
            print(" ", line)
        return 1

    if not EXE.is_file():
        failed.append(f"未找到对照用 {EXE}")

    print(f"=== MSI 元数据：{MSI} ({MSI.stat().st_size // 1024} KB) ===")
    meta = _query_msi(MSI)

    product = meta["properties"].get("ProductName", "")
    arp_icon = meta["properties"].get("ARPPRODUCTICON", "")
    print(f"ProductName      = {product!r}")
    print(f"ARPPRODUCTICON   = {arp_icon!r}")
    print(f"ProductVersion   = {meta['properties'].get('ProductVersion', '')!r}")
    print(f"Icons            = {[n for (n,) in meta['icons']]}")
    print(f"Features         = {meta['features']}")
    print(f"Files            = {meta['files']}")

    if product != EXPECTED_PRODUCT:
        failed.append(f"ProductName 应为 {EXPECTED_PRODUCT!r}，实际 {product!r}")
    if arp_icon != ICON_ID:
        failed.append(f"ARPPRODUCTICON 应为 {ICON_ID!r}，实际 {arp_icon!r}")
    if not any(n == ICON_ID or n == f"{ICON_ID}.exe" for (n,) in meta["icons"]):
        failed.append(f"Icon 表缺少 {ICON_ID}")

    if not meta["shortcuts"]:
        failed.append("Shortcut 表为空（缺少桌面快捷方式）")
    else:
        print(f"Shortcuts         = {meta['shortcuts']}")

    welcome = [a for a, _ in meta["ui_sequence"] if a == "WelcomeDlg"]
    if not welcome:
        failed.append("InstallUISequence 缺少 WelcomeDlg（无安装向导）")
    else:
        print("InstallUISequence = 含 WelcomeDlg 安装向导")

    file_names = [row[2] for row in meta["files"]]
    if "WALL-E.exe" not in file_names and "WALL-E.EXE" not in file_names and not any(
        "WALL-E" in (n or "").upper() for n in file_names
    ):
        failed.append(f"File 表未包含 WALL-E.exe：{file_names}")

    exe_size = EXE.stat().st_size if EXE.is_file() else 0
    for _fid, _comp, fname, fsize in meta["files"]:
        if fname and "WALL-E" in fname.upper():
            if EXE.is_file() and str(fsize) != str(exe_size):
                failed.append(f"MSI 内记录的文件大小 {fsize} 与 dist exe {exe_size} 不一致")
            else:
                print(f"FileSize 校验     = OK ({fsize} bytes)")

    if _icon_ok(meta):
        print("Icon 配置校验     = OK（ARPPRODUCTICON → exe 内嵌图标）")
    else:
        failed.append("Icon / ARPPRODUCTICON 配置不正确")

    dir_ids = {d[0] for d in meta["directories"]}
    if "WALLE" not in dir_ids and "INSTALLDIR" not in dir_ids:
        failed.append(f"Directory 表缺少安装目录标识（WALLE/INSTALLDIR），实际 {sorted(dir_ids)}")
    else:
        print(f"安装目录标识     = OK（{dir_ids & {'WALLE', 'INSTALLDIR', 'LocalAppDataFolder'}}）")

    print("\n=== 静默安装 msiexec /i /qn ===")
    code = _quiet_install(MSI)
    if code != 0:
        failed.append(f"msiexec /i 返回码 {code}")
    else:
        installed = _installed_exe()
        print(f"安装路径         = {installed}")
        if not installed.is_file():
            failed.append(f"安装后未找到 {installed}")
        elif EXE.is_file():
            if _sha256(installed) != _sha256(EXE):
                failed.append("安装后的 exe 与 dist\\WALL-E.exe SHA256 不一致")
            else:
                print("安装 exe 校验    = OK（SHA256 与 dist 一致）")
        if installed.is_file() and installed.stat().st_size != exe_size:
            failed.append("安装后文件大小与 dist exe 不一致")

        desktop_lnk = Path(os.environ.get("USERPROFILE", "")) / "Desktop" / "WALL-E Assistant.lnk"
        if not desktop_lnk.is_file():
            failed.append(f"安装后未找到桌面快捷方式: {desktop_lnk}")
        else:
            print(f"桌面快捷方式     = OK ({desktop_lnk})")

    print()
    if failed:
        print("FAILED:")
        for line in failed:
            print(" ", line)
        return 1

    print("all MSI checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
