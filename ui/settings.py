import json
import customtkinter as ctk
from utils.constants import Theme


def _mask_secret(value: str, keep: int = 4) -> str:
    """Show only the last few chars so tokens are not readable on screen."""
    if not value:
        return ""
    if len(value) <= keep:
        return "•" * len(value)
    return "•" * max(8, len(value) - keep) + value[-keep:]


def _resolve_secret(entry_value: str, stored: str) -> str:
    # If the field still shows the masked form, keep the real stored secret
    if not entry_value:
        return ""
    if stored and entry_value == _mask_secret(stored):
        return stored
    return entry_value


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))
        title = ctk.CTkLabel(
            header_frame, text="Settings",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        )
        title.pack(side="left")

        self.scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 20))

        self._build_serial_settings()
        self._build_camera_settings()
        self._build_floor_plan_settings()
        self._build_mobile_alert_settings()
        self._build_password_settings()

    def on_show(self):
        # Refresh Armed toggle + channel warning when navigating back to Settings
        self._refresh_armed_ui()
        self._refresh_channel_warning()
        self._refresh_serial_status()
        self._refresh_floor_plan_path()

    def _create_section(self, title):
        frame = ctk.CTkFrame(
            self.scroll, fg_color=Theme.BG_CARD, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        frame.pack(fill="x", pady=10, padx=10)

        lbl = ctk.CTkLabel(
            frame, text=title, font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        )
        lbl.pack(anchor="w", padx=20, pady=(15, 10))
        return frame

    def _build_serial_settings(self):
        section = self._create_section("Serial Connection (ESP32)")

        # Phase 6 — show live COM status so Save → reconnect is easy to verify
        self.serial_status = ctk.CTkLabel(
            section, text="Status: …", font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT_MUTED,
        )
        self.serial_status.pack(anchor="w", padx=20, pady=(0, 8))

        row1 = ctk.CTkFrame(section, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=(0, 10))

        ctk.CTkLabel(row1, text="COM Port:", width=100, anchor="w").pack(side="left")
        ports = self.app.serial_manager.get_available_ports() or []
        current = self.app.settings_manager.get("com_port", "COM3")
        values = ports if ports else [current or "COM3"]
        if current and current not in values:
            values = [current] + values
        self.com_port_var = ctk.StringVar(value=current if current in values else values[0])
        self.com_port_menu = ctk.CTkOptionMenu(
            row1, values=values, variable=self.com_port_var, width=150,
        )
        self.com_port_menu.pack(side="left", padx=10)

        # Still allow typing a port that is not listed yet
        self.com_port = ctk.CTkEntry(row1, width=100, placeholder_text="or type")
        self.com_port.insert(0, current)
        self.com_port.pack(side="left", padx=6)

        ctk.CTkButton(
            row1, text="Refresh Ports", width=110, fg_color=Theme.PANEL_LIGHT,
            command=self._refresh_com_ports,
        ).pack(side="left", padx=6)

        row2 = ctk.CTkFrame(section, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(0, 15))

        ctk.CTkLabel(row2, text="Baud Rate:", width=100, anchor="w").pack(side="left")
        self.baud_rate = ctk.CTkEntry(row2, width=150)
        self.baud_rate.insert(0, self.app.settings_manager.get("baud_rate", "115200"))
        self.baud_rate.pack(side="left", padx=10)

        btn_row = ctk.CTkFrame(section, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(0, 20))
        ctk.CTkButton(
            btn_row, text="Save & Reconnect", fg_color=Theme.PRIMARY, command=self.save_serial,
        ).pack(side="left")
        ctk.CTkButton(
            btn_row, text="Reconnect Now", fg_color=Theme.PANEL_LIGHT, command=self._reconnect_serial,
        ).pack(side="left", padx=10)

        self._refresh_serial_status()

    def _build_camera_settings(self):
        section = self._create_section("Camera & Desktop Alerts")

        idx_row = ctk.CTkFrame(section, fg_color="transparent")
        idx_row.pack(fill="x", padx=20, pady=(0, 10))
        ctk.CTkLabel(idx_row, text="Camera Index:", width=110, anchor="w").pack(side="left")
        self.camera_index = ctk.CTkEntry(idx_row, width=80)
        self.camera_index.insert(0, self.app.settings_manager.get("camera_index", "0"))
        self.camera_index.pack(side="left", padx=10)

        self.capture_var = ctk.StringVar(
            value=self.app.settings_manager.get("camera_capture_enabled", "true"),
        )
        self.capture_switch = ctk.CTkSwitch(
            section, text="Enable Snapshots on Motion",
            variable=self.capture_var, onvalue="true", offvalue="false",
        )
        self.capture_switch.pack(anchor="w", padx=20, pady=(0, 10))

        self.notif_var = ctk.StringVar(
            value=self.app.settings_manager.get("notifications_enabled", "true"),
        )
        self.notif_switch = ctk.CTkSwitch(
            section, text="Enable Toast Notifications",
            variable=self.notif_var, onvalue="true", offvalue="false",
        )
        self.notif_switch.pack(anchor="w", padx=20, pady=(0, 20))

        save_btn = ctk.CTkButton(
            section, text="Save Camera Settings", fg_color=Theme.PRIMARY, command=self.save_camera,
        )
        save_btn.pack(anchor="w", padx=20, pady=(0, 20))

    def _build_floor_plan_settings(self):
        # Phase 6 — Settings path to replace the active floor-plan image
        section = self._create_section("Floor Plan Image")
        self.floor_path_label = ctk.CTkLabel(
            section, text="Active image: …",
            font=ctk.CTkFont(size=12), text_color=Theme.TEXT_SECONDARY, wraplength=700,
            justify="left",
        )
        self.floor_path_label.pack(anchor="w", padx=20, pady=(0, 10))
        ctk.CTkButton(
            section, text="Replace Floor Plan Image…", fg_color=Theme.PRIMARY,
            command=self._replace_floor_image_from_settings,
        ).pack(anchor="w", padx=20, pady=(0, 20))
        self._refresh_floor_plan_path()

    def _build_password_settings(self):
        # Phase 6 — change admin password from Settings (plan section F)
        section = self._create_section("Change Admin Password")
        row1 = ctk.CTkFrame(section, fg_color="transparent")
        row1.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(row1, text="New Password:", width=130, anchor="w").pack(side="left")
        self.new_password = ctk.CTkEntry(row1, width=220, show="*")
        self.new_password.pack(side="left", padx=8)

        row2 = ctk.CTkFrame(section, fg_color="transparent")
        row2.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(row2, text="Confirm Password:", width=130, anchor="w").pack(side="left")
        self.confirm_password = ctk.CTkEntry(row2, width=220, show="*")
        self.confirm_password.pack(side="left", padx=8)

        ctk.CTkButton(
            section, text="Update Password", fg_color=Theme.PRIMARY, command=self.save_password,
        ).pack(anchor="w", padx=20, pady=(0, 20))

    def _build_mobile_alert_settings(self):
        # Phase 5 — full Mobile Alert Hub config (Arm, schedule, channels, Test)
        section = self._create_section("Mobile Alerts (Telegram / Discord / WhatsApp)")
        sm = self.app.settings_manager

        self.armed_warning = ctk.CTkLabel(
            section, text="", text_color=Theme.WARNING,
            font=ctk.CTkFont(size=12), wraplength=700, justify="left",
        )
        self.armed_warning.pack(anchor="w", padx=20, pady=(0, 8))

        arm_row = ctk.CTkFrame(section, fg_color="transparent")
        arm_row.pack(fill="x", padx=20, pady=(0, 10))
        self.armed_var = ctk.StringVar(value=sm.get("mobile_alerts_armed", "false"))
        self.armed_switch = ctk.CTkSwitch(
            arm_row,
            text="Arm Mobile Alerts (Away) — Disarm = Home / desktop only",
            variable=self.armed_var, onvalue="true", offvalue="false",
            command=self._on_armed_toggle,
        )
        self.armed_switch.pack(side="left")

        self.sched_var = ctk.StringVar(value=sm.get("mobile_alerts_schedule_enabled", "false"))
        ctk.CTkSwitch(
            section, text="Enable alert schedule (overnight windows supported)",
            variable=self.sched_var, onvalue="true", offvalue="false",
        ).pack(anchor="w", padx=20, pady=(0, 8))

        sched_row = ctk.CTkFrame(section, fg_color="transparent")
        sched_row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(sched_row, text="Start (HH:MM):", width=110, anchor="w").pack(side="left")
        self.sched_start = ctk.CTkEntry(sched_row, width=80)
        self.sched_start.insert(0, sm.get("mobile_alerts_start", "22:00"))
        self.sched_start.pack(side="left", padx=(0, 16))
        ctk.CTkLabel(sched_row, text="End (HH:MM):", width=100, anchor="w").pack(side="left")
        self.sched_end = ctk.CTkEntry(sched_row, width=80)
        self.sched_end.insert(0, sm.get("mobile_alerts_end", "06:00"))
        self.sched_end.pack(side="left")

        cool_row = ctk.CTkFrame(section, fg_color="transparent")
        cool_row.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(cool_row, text="Cooldown (sec):", width=110, anchor="w").pack(side="left")
        self.cooldown_entry = ctk.CTkEntry(cool_row, width=80)
        self.cooldown_entry.insert(0, sm.get("mobile_alert_cooldown_sec", "180"))
        self.cooldown_entry.pack(side="left")

        ctk.CTkLabel(
            section, text="Telegram", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(8, 4))
        self.tg_enabled = ctk.StringVar(value=sm.get("alert_telegram_enabled", "false"))
        ctk.CTkSwitch(
            section, text="Enable Telegram", variable=self.tg_enabled,
            onvalue="true", offvalue="false",
        ).pack(anchor="w", padx=20, pady=(0, 6))

        tg_token_row = ctk.CTkFrame(section, fg_color="transparent")
        tg_token_row.pack(fill="x", padx=20, pady=(0, 6))
        ctk.CTkLabel(tg_token_row, text="Bot Token:", width=110, anchor="w").pack(side="left")
        self.tg_token = ctk.CTkEntry(tg_token_row, width=360, show="*")
        stored_tg = sm.get("alert_telegram_token", "") or ""
        self._tg_token_stored = stored_tg
        if stored_tg:
            self.tg_token.insert(0, _mask_secret(stored_tg))
        self.tg_token.pack(side="left", padx=8)

        tg_chat_row = ctk.CTkFrame(section, fg_color="transparent")
        tg_chat_row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(tg_chat_row, text="Chat ID:", width=110, anchor="w").pack(side="left")
        self.tg_chat = ctk.CTkEntry(tg_chat_row, width=200)
        self.tg_chat.insert(0, sm.get("alert_telegram_chat_id", "") or "")
        self.tg_chat.pack(side="left", padx=8)

        ctk.CTkLabel(
            section, text="Discord", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(8, 4))
        self.dc_enabled = ctk.StringVar(value=sm.get("alert_discord_enabled", "false"))
        ctk.CTkSwitch(
            section, text="Enable Discord", variable=self.dc_enabled,
            onvalue="true", offvalue="false",
        ).pack(anchor="w", padx=20, pady=(0, 6))

        dc_row = ctk.CTkFrame(section, fg_color="transparent")
        dc_row.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(dc_row, text="Webhook URL:", width=110, anchor="w").pack(side="left")
        self.dc_webhook = ctk.CTkEntry(dc_row, width=360, show="*")
        stored_dc = sm.get("alert_discord_webhook", "") or ""
        self._dc_webhook_stored = stored_dc
        if stored_dc:
            self.dc_webhook.insert(0, _mask_secret(stored_dc))
        self.dc_webhook.pack(side="left", padx=8)

        ctk.CTkLabel(
            section, text="WhatsApp (Twilio)", font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=20, pady=(8, 4))
        self.wa_enabled = ctk.StringVar(value=sm.get("alert_whatsapp_enabled", "false"))
        ctk.CTkSwitch(
            section, text="Enable WhatsApp via Twilio", variable=self.wa_enabled,
            onvalue="true", offvalue="false",
        ).pack(anchor="w", padx=20, pady=(0, 6))

        creds = self._load_wa_creds(sm.get("alert_whatsapp_credentials_json", ""))
        self._wa_sid_stored = creds.get("account_sid", "")
        self._wa_token_stored = creds.get("auth_token", "")

        wa_sid_row = ctk.CTkFrame(section, fg_color="transparent")
        wa_sid_row.pack(fill="x", padx=20, pady=(0, 6))
        ctk.CTkLabel(wa_sid_row, text="Account SID:", width=110, anchor="w").pack(side="left")
        self.wa_sid = ctk.CTkEntry(wa_sid_row, width=280, show="*")
        if self._wa_sid_stored:
            self.wa_sid.insert(0, _mask_secret(self._wa_sid_stored))
        self.wa_sid.pack(side="left", padx=8)

        wa_tok_row = ctk.CTkFrame(section, fg_color="transparent")
        wa_tok_row.pack(fill="x", padx=20, pady=(0, 6))
        ctk.CTkLabel(wa_tok_row, text="Auth Token:", width=110, anchor="w").pack(side="left")
        self.wa_token = ctk.CTkEntry(wa_tok_row, width=280, show="*")
        if self._wa_token_stored:
            self.wa_token.insert(0, _mask_secret(self._wa_token_stored))
        self.wa_token.pack(side="left", padx=8)

        wa_from_row = ctk.CTkFrame(section, fg_color="transparent")
        wa_from_row.pack(fill="x", padx=20, pady=(0, 6))
        ctk.CTkLabel(wa_from_row, text="From (WA):", width=110, anchor="w").pack(side="left")
        self.wa_from = ctk.CTkEntry(wa_from_row, width=220)
        self.wa_from.insert(0, creds.get("from", "") or "")
        self.wa_from.pack(side="left", padx=8)

        wa_to_row = ctk.CTkFrame(section, fg_color="transparent")
        wa_to_row.pack(fill="x", padx=20, pady=(0, 12))
        ctk.CTkLabel(wa_to_row, text="To (E.164):", width=110, anchor="w").pack(side="left")
        self.wa_to = ctk.CTkEntry(wa_to_row, width=220)
        self.wa_to.insert(0, sm.get("alert_whatsapp_to", "") or "")
        self.wa_to.pack(side="left", padx=8)

        btn_row = ctk.CTkFrame(section, fg_color="transparent")
        btn_row.pack(fill="x", padx=20, pady=(4, 20))
        ctk.CTkButton(
            btn_row, text="Save Mobile Alerts", fg_color=Theme.PRIMARY,
            command=self.save_mobile_alerts, width=160,
        ).pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            btn_row, text="Test Telegram", fg_color=Theme.PANEL_LIGHT,
            command=lambda: self._test_alert(["telegram"]), width=120,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btn_row, text="Test Discord", fg_color=Theme.PANEL_LIGHT,
            command=lambda: self._test_alert(["discord"]), width=120,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btn_row, text="Test WhatsApp", fg_color=Theme.PANEL_LIGHT,
            command=lambda: self._test_alert(["whatsapp"]), width=120,
        ).pack(side="left", padx=4)
        ctk.CTkButton(
            btn_row, text="Test All Enabled", fg_color=Theme.PRIMARY_LIGHT,
            command=lambda: self._test_alert(None), width=140,
        ).pack(side="left", padx=4)

        self._refresh_channel_warning()

    @staticmethod
    def _load_wa_creds(raw) -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}

    def _on_armed_toggle(self):
        self.app.settings_manager.set("mobile_alerts_armed", self.armed_var.get())
        if hasattr(self.app, "sync_mobile_armed_ui"):
            self.app.sync_mobile_armed_ui()
        self._refresh_channel_warning()
        armed = self.armed_var.get() == "true"
        self.app.notifications.show(
            "Mobile Alerts",
            "Armed (Away) — external channels may send." if armed else "Disarmed (Home) — desktop only.",
            type="success" if armed else "info",
        )

    def _refresh_armed_ui(self):
        val = self.app.settings_manager.get("mobile_alerts_armed", "false")
        self.armed_var.set(val)

    def _refresh_channel_warning(self):
        armed = self.app.settings_manager.get("mobile_alerts_armed", "false").lower() == "true"
        notifier = getattr(self.app, "notifier_manager", None)
        has_channels = False
        if notifier is not None:
            has_channels = notifier.has_any_configured_channel()
        if armed and not has_channels:
            self.armed_warning.configure(
                text="Warning: Mobile Alerts are Armed but no channel has valid credentials. "
                     "Enable and configure Telegram, Discord, or WhatsApp below.",
            )
        else:
            self.armed_warning.configure(text="")

    def save_serial(self):
        typed = self.com_port.get().strip()
        port = typed or self.com_port_var.get().strip()
        baud = self.baud_rate.get().strip()
        self.app.settings_manager.set("com_port", port)
        self.app.settings_manager.set("baud_rate", baud)
        # Apply COM/baud immediately so the operator does not need to restart the app
        ok = self.app.serial_manager.restart(port=port, baudrate=baud)
        self._refresh_serial_status()
        if ok:
            self.app.notifications.show(
                "Settings Saved", f"Serial reconnected on {port}.", type="success",
            )
        else:
            self.app.notifications.show(
                "Settings Saved",
                f"Saved {port}, but serial is offline (missing COM is OK).",
                type="warning",
            )

    def _reconnect_serial(self):
        # Phase 6 — one-click reconnect using whatever is already saved/typed
        typed = self.com_port.get().strip()
        port = typed or self.com_port_var.get().strip()
        baud = self.baud_rate.get().strip() or "115200"
        ok = self.app.serial_manager.restart(port=port, baudrate=baud)
        self._refresh_serial_status()
        self.app.notifications.show(
            "Serial",
            f"Connected on {port}." if ok else f"Could not open {port}.",
            type="success" if ok else "warning",
        )

    def _refresh_com_ports(self):
        ports = self.app.serial_manager.get_available_ports() or []
        current = self.com_port_var.get() if hasattr(self, "com_port_var") else ""
        values = ports if ports else [current or "COM3"]
        if current and current not in values:
            values = [current] + list(values)
        self.com_port_menu.configure(values=values)
        if current in values:
            self.com_port_var.set(current)
        elif values:
            self.com_port_var.set(values[0])
        self.app.notifications.show(
            "Serial",
            f"Found {len(ports)} port(s)." if ports else "No COM ports detected.",
            type="info",
        )

    def _refresh_serial_status(self):
        if not hasattr(self, "serial_status"):
            return
        sm = self.app.serial_manager
        online = bool(getattr(sm, "is_connected", False))
        port = getattr(sm, "port", None) or "—"
        if online:
            self.serial_status.configure(
                text=f"Status: Connected on {port}",
                text_color=Theme.SUCCESS,
            )
        else:
            self.serial_status.configure(
                text=f"Status: Disconnected (last port {port})",
                text_color=Theme.WARNING,
            )

    def save_camera(self):
        self.app.settings_manager.set("camera_capture_enabled", self.capture_var.get())
        self.app.settings_manager.set("notifications_enabled", self.notif_var.get())
        idx = self.camera_index.get().strip() or "0"
        self.app.settings_manager.set("camera_index", idx)
        # Restart the camera so a new index takes effect without logging out
        try:
            cam_index = int(idx)
        except ValueError:
            cam_index = 0
            self.app.settings_manager.set("camera_index", "0")
        self.app.camera_manager.stop()
        ok = self.app.camera_manager.start(camera_index=cam_index)
        self.app.notifications.show(
            "Settings Saved",
            "Camera and alert configuration updated." + ("" if ok else " Camera offline."),
            type="success" if ok else "warning",
        )

    def _refresh_floor_plan_path(self):
        if not hasattr(self, "floor_path_label"):
            return
        dm = getattr(self.app, "device_manager", None)
        plan = dm.get_active_floor_plan() if dm else None
        path = (plan or {}).get("image_path") or "assets/isometric_base.jpg"
        name = (plan or {}).get("name") or "Default"
        self.floor_path_label.configure(text=f"Active image ({name}): {path}")

    def _replace_floor_image_from_settings(self):
        from tkinter import filedialog

        dm = getattr(self.app, "device_manager", None)
        plan = dm.get_active_floor_plan() if dm else None
        if not plan or not dm:
            self.app.notifications.show(
                "Floor Plan", "No active floor plan to update.", type="warning",
            )
            return
        path = filedialog.askopenfilename(
            title="Choose floor plan image",
            filetypes=[
                ("Images", "*.jpg;*.jpeg;*.png;*.webp;*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        updated = dm.replace_floor_plan_image(plan["id"], path)
        if not updated:
            self.app.notifications.show(
                "Floor Plan", "Could not copy or save the new image.", type="danger",
            )
            return
        self._refresh_floor_plan_path()
        # Reload open floor-plan pages so the new image shows immediately
        for key in ("Floor Plan", "3D Environment"):
            view = self.app.views.get(key)
            if view is not None and hasattr(view, "_load_floor_plan_chrome"):
                view._load_floor_plan_chrome()
            elif view is not None and hasattr(view, "on_show"):
                view.on_show()
        self.app.notifications.show("Floor Plan", "Floor plan image updated.", type="success")

    def save_password(self):
        new_pw = self.new_password.get()
        confirm = self.confirm_password.get()
        if not new_pw or len(new_pw) < 6:
            self.app.notifications.show(
                "Password", "Use at least 6 characters.", type="warning",
            )
            return
        if new_pw != confirm:
            self.app.notifications.show(
                "Password", "New password and confirm do not match.", type="warning",
            )
            return
        self.app.auth_manager.update_password("admin", new_pw)
        self.new_password.delete(0, "end")
        self.confirm_password.delete(0, "end")
        self.app.notifications.show(
            "Password", "Admin password updated.", type="success",
        )

    def save_mobile_alerts(self):
        sm = self.app.settings_manager
        sm.set("mobile_alerts_armed", self.armed_var.get())
        sm.set("mobile_alerts_schedule_enabled", self.sched_var.get())
        sm.set("mobile_alerts_start", self.sched_start.get().strip() or "22:00")
        sm.set("mobile_alerts_end", self.sched_end.get().strip() or "06:00")
        sm.set("mobile_alert_cooldown_sec", self.cooldown_entry.get().strip() or "180")

        sm.set("alert_telegram_enabled", self.tg_enabled.get())
        tg_token = _resolve_secret(self.tg_token.get().strip(), self._tg_token_stored)
        sm.set("alert_telegram_token", tg_token)
        self._tg_token_stored = tg_token
        sm.set("alert_telegram_chat_id", self.tg_chat.get().strip())

        sm.set("alert_discord_enabled", self.dc_enabled.get())
        dc = _resolve_secret(self.dc_webhook.get().strip(), self._dc_webhook_stored)
        sm.set("alert_discord_webhook", dc)
        self._dc_webhook_stored = dc

        sm.set("alert_whatsapp_enabled", self.wa_enabled.get())
        sm.set("alert_whatsapp_provider", "twilio")
        sid = _resolve_secret(self.wa_sid.get().strip(), self._wa_sid_stored)
        token = _resolve_secret(self.wa_token.get().strip(), self._wa_token_stored)
        self._wa_sid_stored = sid
        self._wa_token_stored = token
        creds = {
            "account_sid": sid,
            "auth_token": token,
            "from": self.wa_from.get().strip(),
        }
        sm.set("alert_whatsapp_credentials_json", json.dumps(creds))
        sm.set("alert_whatsapp_to", self.wa_to.get().strip())

        # Re-mask secret fields after save
        self.tg_token.delete(0, "end")
        if tg_token:
            self.tg_token.insert(0, _mask_secret(tg_token))
        self.dc_webhook.delete(0, "end")
        if dc:
            self.dc_webhook.insert(0, _mask_secret(dc))
        self.wa_sid.delete(0, "end")
        if sid:
            self.wa_sid.insert(0, _mask_secret(sid))
        self.wa_token.delete(0, "end")
        if token:
            self.wa_token.insert(0, _mask_secret(token))

        if hasattr(self.app, "sync_mobile_armed_ui"):
            self.app.sync_mobile_armed_ui()
        self._refresh_channel_warning()
        self.app.notifications.show(
            "Settings Saved", "Mobile alert configuration updated.", type="success",
        )

    def _test_alert(self, channels):
        notifier = getattr(self.app, "notifier_manager", None)
        if notifier is None:
            self.app.notifications.show("Test Alert", "Notifier is not available.", type="danger")
            return

        # Save first so Test uses the values currently on screen
        self.save_mobile_alerts()

        # Test buttons only need credentials; enable switch is not required
        if channels:
            missing = [c for c in channels if not notifier.channel_credentials_ok(c)]
            if missing:
                self.app.notifications.show(
                    "Test Alert",
                    f"Missing credentials for: {', '.join(missing)}",
                    type="warning",
                )
                return
        elif not notifier.has_any_configured_channel():
            self.app.notifications.show(
                "Test Alert", "No enabled channel has valid credentials.", type="warning",
            )
            return

        disarmed = self.app.settings_manager.get("mobile_alerts_armed", "false").lower() != "true"

        def _done(results):
            def _ui():
                if results.get("ok"):
                    ch = ", ".join(results.get("channels") or []) or "channels"
                    msg = f"Sent via {ch}."
                    if disarmed:
                        msg = f"Test sent while Disarmed. {msg}"
                        self.app.notifications.show("Test Alert", msg, type="warning")
                    else:
                        self.app.notifications.show("Test Alert", msg, type="success")
                else:
                    err = "; ".join(results.get("errors") or []) or "send failed"
                    self.app.notifications.show("Test Alert", err, type="danger")

            self.app.after(0, _ui)

        notifier.enqueue_test(channels=channels, on_done=_done)
