"""账号与 CloudBase 同步页。"""

from __future__ import annotations

from kivy.metrics import dp
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.screenmanager import Screen

from layout import Metrics, field_input, field_input_row, ghost_btn, primary_btn, scroll_screen, screen_root, sync_status_label
from sync_service import MobileSyncService
from sync_text import tr
from theme import ACCENT, ACCENT_TEXT, HINT, NAV_IDLE, PAGE_ACCOUNT_TINT, TEXT, TEXT_SECONDARY
from ui_widgets import Label
from walle_widgets import PAGE_ANIMS, walle_page_header, walle_section_title


class AccountScreen(Screen):
    def __init__(self, sync: MobileSyncService, **kwargs):
        super().__init__(**kwargs)
        self.sync = sync
        self._login_mode = "password"

        page = screen_root(page_tint=PAGE_ACCOUNT_TINT)
        scroll, root = scroll_screen()
        page.add_widget(scroll)
        self.add_widget(page)

        root.add_widget(
            walle_page_header(
                "账号同步",
                "登录后可跨设备同步待办与派发",
                anim=PAGE_ANIMS["account"],
            )
        )
        self.status_lbl = sync_status_label(text=sync.status_text())
        root.add_widget(self.status_lbl)

        root.add_widget(walle_section_title("授权码", anim="happy"))
        self.env_input = field_input(
            text=sync.cloudbase_env_id,
            hint_text="请输入授权码",
            size_hint_x=1,
        )
        save_env = primary_btn("保存授权码", size_hint_x=1)
        save_env.bind(on_release=self._save_env)
        self.setup_hint = Label(
            text="首次使用：向管理员获取授权码",
            color=HINT,
            font_size=Metrics.font_sm,
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="top",
        )
        self.setup_hint.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        root.add_widget(field_input_row(self.env_input, with_paste=True))
        root.add_widget(self.setup_hint)
        root.add_widget(save_env)

        self.login_section = walle_section_title("登录", anim=PAGE_ANIMS["login"])
        root.add_widget(self.login_section)

        mode_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(8))
        self.mode_row = mode_row
        self.mode_password_btn = ghost_btn("密码", size_hint_x=1)
        self.mode_password_btn.bind(on_release=lambda *_: self._set_login_mode("password"))
        self.mode_sms_btn = ghost_btn("验证码", size_hint_x=1)
        self.mode_sms_btn.bind(on_release=lambda *_: self._set_login_mode("sms"))
        self.mode_register_btn = ghost_btn("注册", size_hint_x=1)
        self.mode_register_btn.bind(on_release=lambda *_: self._set_login_mode("register"))
        mode_row.add_widget(self.mode_password_btn)
        mode_row.add_widget(self.mode_sms_btn)
        mode_row.add_widget(self.mode_register_btn)
        root.add_widget(mode_row)

        self.register_hint = Label(
            text="新用户：填写手机号与密码，获取验证码后注册",
            color=HINT,
            font_size=Metrics.font_sm,
            size_hint_y=None,
            height=dp(36),
            halign="left",
            valign="top",
        )
        self.register_hint.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        root.add_widget(self.register_hint)

        self.phone_input = field_input(hint_text="13800138000", size_hint_x=1)
        self.password_input = field_input(hint_text="密码", password=True, size_hint_x=1)
        self.sms_code_input = field_input(hint_text="短信验证码", size_hint_x=1)
        self.sms_send_btn = ghost_btn("获取验证码", size_hint_x=1)
        self.sms_send_btn.bind(on_release=self._send_sms)
        self.phone_row = field_input_row(self.phone_input, with_paste=True)
        self.password_row = field_input_row(self.password_input, with_paste=True)
        self.sms_code_row = field_input_row(self.sms_code_input, with_paste=True)
        self.sms_send_row = self._full_row(self.sms_send_btn)
        root.add_widget(self.phone_row)
        root.add_widget(self.password_row)
        root.add_widget(self.sms_code_row)
        root.add_widget(self.sms_send_row)

        self.login_btn = primary_btn("登录并同步", size_hint_x=1)
        self.login_btn.bind(on_release=self._login)
        self.login_row = self._full_row(self.login_btn)
        root.add_widget(self.login_row)

        btn_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        self.logout_btn = ghost_btn("退出登录", size_hint_x=1)
        self.logout_btn.bind(on_release=self._logout)
        self.sync_btn = ghost_btn("立即同步", size_hint_x=1)
        self.sync_btn.bind(on_release=self._sync_now)
        btn_row.add_widget(self.logout_btn)
        btn_row.add_widget(self.sync_btn)
        root.add_widget(btn_row)

        self.pause_btn = ghost_btn(tr("sync.pause"), size_hint_x=1)
        self.pause_btn.bind(on_release=self._toggle_pause)
        self.pause_row = self._full_row(self.pause_btn)
        root.add_widget(self.pause_row)

        root.add_widget(walle_section_title("通知与横幅", anim="talk"))
        self.notify_status_lbl = sync_status_label()
        root.add_widget(self.notify_status_lbl)
        notify_row = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
        self.test_notify_btn = ghost_btn("测试通知", size_hint_x=1)
        self.test_notify_btn.bind(on_release=self._test_notify)
        self.overlay_btn = ghost_btn("悬浮窗权限", size_hint_x=1)
        self.overlay_btn.bind(on_release=self._request_overlay)
        notify_row.add_widget(self.test_notify_btn)
        notify_row.add_widget(self.overlay_btn)
        root.add_widget(notify_row)

        root.add_widget(walle_section_title("联系人昵称", anim="love"))
        self.contact_hint = Label(
            text="派发时可输入昵称；收到任务时显示昵称",
            color=HINT,
            font_size=Metrics.font_sm,
            size_hint_y=None,
            height=dp(28),
            halign="left",
            valign="top",
        )
        self.contact_hint.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        root.add_widget(self.contact_hint)
        self.contact_phone_input = field_input(hint_text="对方手机号", size_hint_x=1)
        self.contact_nickname_input = field_input(hint_text="昵称", size_hint_x=1)
        self.contact_phone_row = field_input_row(self.contact_phone_input, with_paste=True)
        self.contact_nickname_row = field_input_row(self.contact_nickname_input, with_paste=True)
        root.add_widget(self.contact_phone_row)
        root.add_widget(self.contact_nickname_row)
        contact_btn_row = BoxLayout(size_hint_y=None, height=dp(46), spacing=dp(10))
        self.contact_save_btn = primary_btn("保存联系人", size_hint_x=1)
        self.contact_save_btn.bind(on_release=self._save_contact)
        self.contact_remove_btn = ghost_btn("删除所选", size_hint_x=1)
        self.contact_remove_btn.bind(on_release=self._remove_contact)
        contact_btn_row.add_widget(self.contact_save_btn)
        contact_btn_row.add_widget(self.contact_remove_btn)
        root.add_widget(contact_btn_row)
        self.contacts_list_lbl = Label(
            text="",
            color=TEXT_SECONDARY,
            font_size=Metrics.font_sm,
            size_hint_y=None,
            height=dp(80),
            halign="left",
            valign="top",
        )
        self.contacts_list_lbl.bind(size=lambda inst, val: setattr(inst, "text_size", (val[0], None)))
        self.contacts_list_lbl.bind(
            texture_size=lambda inst, val: setattr(inst, "height", max(dp(40), val[1] + dp(8)))
        )
        root.add_widget(self.contacts_list_lbl)

        self._set_login_mode("password")
        self.refresh()

    @staticmethod
    def _full_row(widget) -> BoxLayout:
        """全宽表单项行（与页面边距配合，不再左侧堆叠固定宽度控件）。"""
        row = BoxLayout(size_hint_y=None, height=Metrics.field_h, spacing=dp(8))
        if widget.size_hint_x is None:
            widget.size_hint_x = 1
        row.add_widget(widget)
        return row

    def _set_login_mode(self, mode: str) -> None:
        self._login_mode = mode
        sms = mode == "sms"
        reg = mode == "register"
        self.password_input.opacity = 0 if sms else 1
        self.password_input.disabled = sms
        self.password_row.opacity = 0 if sms else 1
        self.password_row.height = 0 if sms else Metrics.field_h
        show_code = sms or reg
        self.sms_code_input.opacity = 1 if show_code else 0
        self.sms_code_input.disabled = not show_code
        self.sms_code_row.opacity = 1 if show_code else 0
        self.sms_code_row.height = Metrics.field_h if show_code else 0
        self.sms_send_btn.opacity = 1 if show_code else 0
        self.sms_send_btn.disabled = not show_code
        self.sms_send_row.opacity = 1 if show_code else 0
        self.sms_send_row.height = Metrics.field_h if show_code else 0
        self.register_hint.opacity = 1 if reg else 0
        self.register_hint.height = dp(36) if reg else 0
        self.login_btn.text = "注册并登录" if reg else "登录并同步"
        for btn, key in (
            (self.mode_password_btn, "password"),
            (self.mode_sms_btn, "sms"),
            (self.mode_register_btn, "register"),
        ):
            active = mode == key
            btn.background_color = ACCENT if active else NAV_IDLE
            btn.color = ACCENT_TEXT if active else TEXT
            btn.bold = active

    def _login_widgets(self):
        return (
            self.login_section,
            self.mode_row,
            self.register_hint,
            self.phone_row,
            self.password_row,
            self.sms_code_row,
            self.sms_send_row,
            self.login_row,
        )

    def refresh(self) -> None:
        logged_in = self.sync.is_logged_in
        configured = self.sync.backend_configured
        if logged_in and self.sync.phone:
            self.status_lbl.text = f"已登录：{self.sync.phone}\n{self.sync.status_text()}"
            self.status_lbl.color = ACCENT
        else:
            self.status_lbl.text = self.sync.status_text()
            self.status_lbl.color = TEXT_SECONDARY
        self.env_input.disabled = logged_in
        show_login = not logged_in
        for widget in self._login_widgets():
            widget.opacity = 1 if show_login else 0
            widget.disabled = not show_login or not configured
            if widget is self.mode_row:
                widget.height = Metrics.field_h if show_login else 0
            elif widget is self.login_section:
                widget.height = dp(40) if show_login else 0
            elif widget in (self.password_row, self.sms_code_row, self.sms_send_row, self.phone_row, self.login_row):
                if not show_login:
                    widget.height = 0
                elif widget in (self.password_row, self.sms_code_row, self.sms_send_row):
                    pass
                else:
                    widget.height = Metrics.field_h
        if show_login:
            self.phone_input.disabled = not configured
            self.login_btn.disabled = not configured
            self.mode_password_btn.disabled = not configured
            self.mode_sms_btn.disabled = not configured
            self.mode_register_btn.disabled = not configured
            self._set_login_mode(self._login_mode)
        self.logout_btn.disabled = not logged_in
        self.sync_btn.disabled = not logged_in or not configured
        if logged_in:
            self.pause_btn.disabled = False
            self.pause_btn.text = tr("sync.resume") if self.sync.sync_paused else tr("sync.pause")
            self.pause_btn.opacity = 1
            self.pause_row.opacity = 1
            self.pause_row.height = Metrics.field_h
        else:
            self.pause_btn.disabled = True
            self.pause_btn.opacity = 0
            self.pause_row.opacity = 0
            self.pause_row.height = 0
        self.notify_status_lbl.text = self._notify_status_text()
        self._refresh_contacts_list()

    def _refresh_contacts_list(self) -> None:
        rows = self.sync.contacts.list_contacts()
        if not rows:
            self.contacts_list_lbl.text = "尚未添加联系人"
        else:
            self.contacts_list_lbl.text = "\n".join(f"{nickname} · {phone}" for phone, nickname in rows)

    def _save_contact(self, *_args) -> None:
        from walle.sync.backend import SyncBackendError

        try:
            self.sync.set_contact_nickname(
                self.contact_phone_input.text.strip(),
                self.contact_nickname_input.text.strip(),
            )
            self.contact_phone_input.text = ""
            self.contact_nickname_input.text = ""
            self.status_lbl.text = "联系人已保存"
            self.status_lbl.color = ACCENT
            self._refresh_contacts_list()
        except SyncBackendError as exc:
            self.status_lbl.text = self.sync.friendly_error(str(exc))
            self.status_lbl.color = TEXT_SECONDARY

    def _remove_contact(self, *_args) -> None:
        phone = self.contact_phone_input.text.strip()
        if not phone:
            self.status_lbl.text = "请在上方输入要删除的手机号"
            self.status_lbl.color = TEXT_SECONDARY
            return
        self.sync.remove_contact(phone)
        self.contact_phone_input.text = ""
        self.status_lbl.text = "联系人已删除"
        self.status_lbl.color = ACCENT
        self._refresh_contacts_list()

    def _save_env(self, *_args) -> None:
        self.sync.save_cloudbase_env_id(self.env_input.text.strip())
        self.refresh()

    def _send_sms(self, *_args) -> None:
        self.sms_send_btn.disabled = True
        phone = self.phone_input.text.strip()

        def done(pair: tuple[bool, str]) -> None:
            ok, msg = pair
            self.status_lbl.text = msg
            self.sms_send_btn.disabled = False
            if not ok:
                self.status_lbl.color = TEXT_SECONDARY

        if self._login_mode == "register":
            self.sync.send_register_sms(phone, on_done=done)
        else:
            self.sync.send_sms_code(phone, on_done=done)

    def _login(self, *_args) -> None:
        phone = self.phone_input.text.strip()
        if self._login_mode == "register":
            self.sync.register(phone, self.password_input.text, self.sms_code_input.text.strip())
            self.sms_code_input.text = ""
        elif self._login_mode == "sms":
            self.sync.login_with_sms_code(phone, self.sms_code_input.text.strip())
            self.sms_code_input.text = ""
        else:
            self.sync.login(phone, self.password_input.text)
            self.password_input.text = ""
        self.refresh()

    def _logout(self, *_args) -> None:
        self.sync.logout()
        self.refresh()

    def _sync_now(self, *_args) -> None:
        self.sync.sync_now()
        self.refresh()

    def _toggle_pause(self, *_args) -> None:
        self.sync.set_sync_paused(not self.sync.sync_paused)
        self.refresh()

    def _notify_status_text(self) -> str:
        from notify_util import notification_status_text

        return notification_status_text()

    def _test_notify(self, *_args) -> None:
        from notify_util import notify

        result = notify(
            "WALL-E",
            "这是一条测试通知；若应用在前台，顶部应出现横幅。",
            urgent=True,
        )
        parts = []
        if result.get("system"):
            parts.append("系统通知已发送")
        else:
            parts.append("系统通知未发出（请检查通知权限）")
        if result.get("banner"):
            parts.append("应用内横幅已显示")
        self.status_lbl.text = "；".join(parts)
        self.status_lbl.color = ACCENT if result.get("system") or result.get("banner") else TEXT_SECONDARY
        self.notify_status_lbl.text = self._notify_status_text()

    def _request_overlay(self, *_args) -> None:
        from android_platform import is_android, request_overlay_permission

        if not is_android():
            self.status_lbl.text = "本地预览无系统悬浮窗；应用内横幅已可用"
            self.status_lbl.color = TEXT_SECONDARY
            return
        if request_overlay_permission():
            self.status_lbl.text = "悬浮窗权限已开启"
            self.status_lbl.color = ACCENT
        else:
            self.status_lbl.text = "请在系统页开启「显示在其他应用上层」"
            self.status_lbl.color = TEXT_SECONDARY
        self.notify_status_lbl.text = self._notify_status_text()

    def on_status(self, text: str) -> None:
        if self.sync.is_logged_in and self.sync.phone:
            self.status_lbl.text = f"已登录：{self.sync.phone}\n{text}"
            self.status_lbl.color = ACCENT
        else:
            self.status_lbl.text = text
            self.status_lbl.color = TEXT_SECONDARY
        self.refresh()