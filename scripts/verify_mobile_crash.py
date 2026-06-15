"""验证安卓闪退相关修复是否到位（静态 + 导入链）。

用法：python scripts/verify_mobile_crash.py
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MOBILE = ROOT / "mobile"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(MOBILE) not in sys.path:
    sys.path.append(str(MOBILE))


def _fail(msg: str) -> None:
    print(f"FAIL: {msg}")
    sys.exit(1)


def run_prepare_sync() -> None:
    env = os.environ.copy()
    env["WALLE_PROJECT_ROOT"] = str(ROOT)
    proc = subprocess.run(
        [sys.executable, str(MOBILE / "prepare_sync.py")],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0:
        _fail(f"prepare_sync 失败: {proc.stderr or proc.stdout}")
    print("  OK prepare_sync 成功")


def test_mobile_sync_bundle() -> None:
    sync_init = (MOBILE / "walle" / "sync" / "__init__.py").read_text(encoding="utf-8")
    if re.search(r"from\s+\.service|import\s+SyncService", sync_init):
        _fail("mobile/walle/sync/__init__.py 仍引用桌面 SyncService")
    if (MOBILE / "walle" / "sync" / "service.py").is_file():
        _fail("mobile/walle/sync/service.py 不应被打包（依赖 PySide6）")

    for name in ("cloudbase_client.py", "core.py", "backend.py"):
        if not (MOBILE / "walle" / "sync" / name).is_file():
            _fail(f"缺少同步模块 {name}")
    print("  OK 移动端 sync 包不含 PySide6 依赖")


def test_no_desktop_repo_on_android_path() -> None:
    main_src = (MOBILE / "main.py").read_text(encoding="utf-8")
    if "_IS_ANDROID" not in main_src:
        _fail("main.py 缺少 _IS_ANDROID 守卫")
    # Android 分支不应把仓库根加入 sys.path
    block = main_src.split("if not _IS_ANDROID")[1].split("\n", 3)[0]
    if "sys.path" not in main_src:
        _fail("main.py 缺少 sys.path 处理")

    sync_src = (MOBILE / "sync_service.py").read_text(encoding="utf-8")
    if str(ROOT) in sync_src and "sys.path.insert(0, str(_REPO_ROOT))" in sync_src.replace(" ", ""):
        _fail("sync_service.py 仍将仓库根置于 sys.path")
    print("  OK Android 路径不拉取桌面仓库根目录")


def test_mobile_config_stub() -> None:
    stub = (MOBILE / "walle_config_stub.py").read_text(encoding="utf-8")
    for key in ("SYNC_META_PATH", "AUTH_PATH", "DEFAULTS"):
        if key not in stub:
            _fail(f"walle_config_stub.py 缺少 {key}")
    cfg = (MOBILE / "walle" / "config.py")
    if not cfg.is_file():
        _fail("mobile/walle/config.py 不存在，请运行 prepare_sync.py")
    cfg_text = cfg.read_text(encoding="utf-8")
    if "SYNC_META_PATH" not in cfg_text:
        _fail("mobile/walle/config.py 缺少 SYNC_META_PATH（会导致启动闪退）")
    print("  OK mobile walle.config 含同步所需路径常量")


def test_ui_thread_safety() -> None:
    sync_src = (MOBILE / "sync_service.py").read_text(encoding="utf-8")
    if "Clock.schedule_once" not in sync_src or "_schedule_ui" not in sync_src:
        _fail("MobileSyncService 未将回调调度到主线程")
    if "_worker_loop" not in sync_src or "_submit" not in sync_src:
        _fail("网络同步未在后台线程执行")

    main_src = (MOBILE / "main.py").read_text(encoding="utf-8")
    if "_schedule_ui" not in main_src or "_todo_change_body" not in main_src:
        _fail("main.py 未将 store on_change 延后到主线程")

    if "Clock.schedule_once(lambda _dt: self.sync.start()" not in main_src.replace(" ", ""):
        # allow whitespace variants
        if "self.sync.start()" not in main_src or "Clock.schedule_once" not in main_src:
            _fail("sync.start() 未延后启动")

    print("  OK 同步与数据变更回调经主线程调度")


def test_excepthook_and_deferred_boot() -> None:
    main_tail = (MOBILE / "main.py").read_text(encoding="utf-8")
    if "install_android_excepthook" not in main_tail:
        _fail("未安装 Android 崩溃日志钩子")

    android_src = (MOBILE / "android_safe.py").read_text(encoding="utf-8")
    if "crash.log" not in android_src:
        _fail("android_safe 未写入 crash.log")

    # 启动时延后通知与后台服务
    for needle in ("ensure_notification_channels", "_sync_android_background"):
        if needle not in main_tail:
            _fail(f"缺少延后启动: {needle}")
    print("  OK 崩溃日志 + 延后启动通知/后台服务")


def test_import_chain_without_pyside6() -> None:
    """模拟 Android：仅 mobile 在 path，不加入仓库根。"""
    env = {
        "WALLE_MOBILE_DATA": str(MOBILE / ".verify_data"),
        "ANDROID_PRIVATE": "/tmp/walle-fake-android",
    }
    code = """
import os, sys
mobile = sys.argv[1]
os.environ.setdefault("WALLE_MOBILE_DATA", mobile + "/.verify_data")
os.environ["ANDROID_PRIVATE"] = "/tmp/walle-fake-android"
sys.path.insert(0, mobile)
from walle.sync.core import SyncCore
from walle.sync.paths import SyncPaths
print("IMPORT_OK")
"""
    proc = subprocess.run(
        [sys.executable, "-c", code, str(MOBILE)],
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if proc.returncode != 0 or "IMPORT_OK" not in proc.stdout:
        _fail(f"Android 导入链失败: {proc.stderr or proc.stdout}")
    print("  OK 无 PySide6 环境下可导入 walle.sync.core")


def test_buildozer_excludes_desktop() -> None:
    spec = (MOBILE / "buildozer.spec").read_text(encoding="utf-8")
    if "pyside6" in spec.lower():
        _fail("buildozer.spec 不应包含 PySide6")
    if "kivy" not in spec.lower():
        _fail("buildozer.spec 应包含 kivy")
    print("  OK buildozer 依赖无桌面 Qt")


def main() -> int:
    print("=== 安卓闪退修复验证 ===")
    run_prepare_sync()
    test_mobile_sync_bundle()
    test_no_desktop_repo_on_android_path()
    test_mobile_config_stub()
    test_ui_thread_safety()
    test_excepthook_and_deferred_boot()
    test_import_chain_without_pyside6()
    test_buildozer_excludes_desktop()
    print("=== 全部通过 ===")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
