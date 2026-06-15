"""系统通知、振动与应用内横幅。"""

from __future__ import annotations

from kivy.utils import platform as kv_platform

_channels_ready = False
_notification_id = 1000


def _is_android() -> bool:
    return kv_platform == "android"


def vibrate(pattern=(0, 0.2, 0.1, 0.2)) -> None:
    try:
        from plyer import vibrator

        vibrator.vibrate(pattern)
    except Exception:
        pass


def notification_permission_granted() -> bool:
    if not _is_android():
        return True
    try:
        from android.permissions import Permission, check_permission

        return check_permission(Permission.POST_NOTIFICATIONS)
    except Exception:
        return True


def overlay_permission_granted() -> bool:
    """系统级悬浮窗（类似桌面瓦力）是否已授权。"""
    if not _is_android():
        return False
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        BuildVersion = autoclass("android.os.Build$VERSION")
        Settings = autoclass("android.provider.Settings")
        activity = PythonActivity.mActivity
        if BuildVersion.SDK_INT < 23:
            return True
        return Settings.canDrawOverlays(activity)
    except Exception:
        return False


def ensure_notification_channels() -> None:
    global _channels_ready
    if _channels_ready or not _is_android():
        return
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        NotificationManager = autoclass("android.app.NotificationManager")
        NotificationChannel = autoclass("android.app.NotificationChannel")
        activity = PythonActivity.mActivity
        nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
        for ch_id, name, desc, importance in (
            ("walle_default", "常规通知", "提醒、同步与操作反馈", 3),
            ("walle_urgent", "重要通知", "派发任务与番茄钟（可横幅弹出）", 4),
        ):
            channel = NotificationChannel(ch_id, name, importance)
            channel.setDescription(desc)
            channel.enableVibration(True)
            nm.createNotificationChannel(channel)
        _channels_ready = True
    except Exception:
        pass


def _android_notify(title: str, message: str, *, urgent: bool) -> bool:
    if not notification_permission_granted():
        return False
    ensure_notification_channels()
    try:
        from jnius import autoclass

        PythonActivity = autoclass("org.kivy.android.PythonActivity")
        Context = autoclass("android.content.Context")
        NotificationManager = autoclass("android.app.NotificationManager")
        NotificationBuilder = autoclass("android.app.Notification$Builder")
        activity = PythonActivity.mActivity
        nm = activity.getSystemService(Context.NOTIFICATION_SERVICE)
        channel_id = "walle_urgent" if urgent else "walle_default"
        builder = NotificationBuilder(activity, channel_id)
        builder.setContentTitle(title)
        builder.setContentText(message)
        builder.setAutoCancel(True)
        icon_id = activity.getApplicationInfo().icon
        builder.setSmallIcon(icon_id)
        global _notification_id
        _notification_id = (_notification_id + 1) % 900000 + 1000
        nm.notify(_notification_id, builder.build())
        return True
    except Exception:
        return False


def _plyer_notify(title: str, message: str, *, ticker: str | None) -> bool:
    try:
        from plyer import notification

        notification.notify(
            title=title,
            message=message,
            app_name="WALL-E",
            ticker=ticker or title,
            timeout=10,
        )
        return True
    except Exception:
        return False


def notify(
    title: str,
    message: str,
    *,
    ticker: str | None = None,
    urgent: bool = False,
    vibrate_on: bool = True,
    show_banner: bool = True,
) -> dict[str, bool]:
    """
    发送通知。返回各通道是否成功：
    system（系统通知栏）、banner（应用内横幅）。
    """
    result = {"system": False, "banner": False}
    if _is_android():
        result["system"] = _android_notify(title, message, urgent=urgent)
        if not result["system"]:
            result["system"] = _plyer_notify(title, message, ticker=ticker)
    else:
        result["system"] = _plyer_notify(title, message, ticker=ticker)
    if show_banner:
        try:
            from floating_banner import show_in_app_banner

            result["banner"] = show_in_app_banner(title, message)
        except Exception:
            pass
    if vibrate_on and (result["system"] or result["banner"]):
        vibrate()
    return result


def notification_status_text() -> str:
    """账号页展示：通知与悬浮窗能力说明。"""
    if not _is_android():
        return "本地预览：系统通知可能不可用；应用内顶部横幅可正常预览。"
    lines = []
    if notification_permission_granted():
        lines.append("系统通知：已开启（锁屏/通知栏；重要消息可走横幅弹出）")
    else:
        lines.append("系统通知：未开启 — 请在系统设置中为 WALL-E 允许通知")
    if overlay_permission_granted():
        lines.append("系统悬浮窗：已授权（当前版本仍使用应用内横幅，未启用桌面悬浮瓦力）")
    else:
        lines.append(
            "系统悬浮窗：未授权 — 桌面级悬浮瓦力需「显示在其他应用上层」；"
            "前台时应用内横幅已自动显示"
        )
    return "\n".join(lines)


def verify_notification_capabilities() -> dict[str, bool | str]:
    """诊断用：返回当前平台通知能力。"""
    return {
        "platform": kv_platform,
        "notification_permission": notification_permission_granted(),
        "overlay_permission": overlay_permission_granted(),
        "channels_ready": _channels_ready,
        "status_text": notification_status_text(),
    }
