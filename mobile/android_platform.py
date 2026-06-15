"""Android 权限、WakeLock、前台 Service 控制。"""

from __future__ import annotations

from kivy.utils import platform as kv_platform

_wake_lock = None
_service_running = False

# 与 buildozer.spec 一致：暂不启用独立前台 Service（1.0.1 无 Service；Android 14+ 需声明类型）
_BACKGROUND_SERVICE_ENABLED = False


def is_android() -> bool:
    return kv_platform == "android"


def request_runtime_permissions() -> None:
    if not is_android():
        return
    try:
        from android.permissions import Permission, check_permission, request_permissions

        needed = []
        if not check_permission(Permission.WAKE_LOCK):
            needed.append(Permission.WAKE_LOCK)
        try:
            if not check_permission(Permission.POST_NOTIFICATIONS):
                needed.append(Permission.POST_NOTIFICATIONS)
        except Exception:
            pass
        if needed:
            request_permissions(needed)
    except Exception:
        pass


def acquire_wake_lock() -> None:
    global _wake_lock
    if not is_android() or _wake_lock is not None:
        return
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        PowerManager = autoclass("android.os.PowerManager")
        activity = PythonActivity.mActivity
        pm = activity.getSystemService(Context.POWER_SERVICE)
        _wake_lock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "walle:pomodoro")
        _wake_lock.setReferenceCounted(False)
        _wake_lock.acquire()
    except Exception:
        _wake_lock = None


def release_wake_lock() -> None:
    global _wake_lock
    if _wake_lock is None:
        return
    try:
        if _wake_lock.isHeld():
            _wake_lock.release()
    except Exception:
        pass
    _wake_lock = None


def _service_intent():
    from jnius import autoclass

    Intent = autoclass("android.content.Intent")
    PythonActivity = autoclass("org.kivy.android.PythonActivity")
    activity = PythonActivity.mActivity
    pkg = activity.getPackageName()
    intent = Intent()
    intent.setClassName(pkg, f"{pkg}.WalleBg")
    return intent, activity


def start_background_service() -> None:
    global _service_running
    if not _BACKGROUND_SERVICE_ENABLED or not is_android() or _service_running:
        return
    try:
        from jnius import autoclass

        intent, activity = _service_intent()
        BuildVersion = autoclass("android.os.Build$VERSION")
        if BuildVersion.SDK_INT >= 26:
            activity.startForegroundService(intent)
        else:
            activity.startService(intent)
        _service_running = True
    except Exception:
        _service_running = False


def stop_background_service() -> None:
    global _service_running
    if not is_android() or not _service_running:
        return
    try:
        intent, activity = _service_intent()
        activity.stopService(intent)
    except Exception:
        pass
    _service_running = False


def request_overlay_permission() -> bool:
    """打开系统设置页申请悬浮窗权限（需用户手动开启）。"""
    if not is_android():
        return False
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Intent = autoclass("android.content.Intent")
        Settings = autoclass("android.provider.Settings")
        Uri = autoclass("android.net.Uri")
        BuildVersion = autoclass("android.os.Build$VERSION")
        activity = PythonActivity.mActivity
        if BuildVersion.SDK_INT < 23:
            return True
        if Settings.canDrawOverlays(activity):
            return True
        intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
        intent.setData(Uri.parse(f"package:{activity.getPackageName()}"))
        activity.startActivity(intent)
        return False
    except Exception:
        return False


def notification_diagnostics() -> dict:
    from notify_util import verify_notification_capabilities

    return verify_notification_capabilities()


def sync_background_service(pomodoro_active: bool, has_reminders: bool) -> None:
    """番茄钟运行中或存在提醒时保持前台 Service + WakeLock。"""
    if not is_android():
        return
    if pomodoro_active or has_reminders:
        start_background_service()
        if pomodoro_active:
            acquire_wake_lock()
        else:
            release_wake_lock()
    else:
        release_wake_lock()
        stop_background_service()
