import customtkinter as ctk
from utils.constants import Theme
from components.cards import KPICard


class DashboardView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=4, sticky="ew", padx=20, pady=(20, 10))

        title = ctk.CTkLabel(
            header_frame, text="Dashboard",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        )
        title.pack(side="left", anchor="w")

        self.subtitle = ctk.CTkLabel(
            header_frame, text="Security system overview",
            font=ctk.CTkFont(size=14), text_color=Theme.TEXT_SECONDARY,
        )
        self.subtitle.pack(side="left", padx=16)

        # Quick action — runs the full motion pipeline without ESP32 hardware
        self.btn_simulate = ctk.CTkButton(
            header_frame, text="Simulate Motion", width=140, height=32,
            fg_color=Theme.DANGER, hover_color=Theme.DANGER_LIGHT,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self._on_simulate,
        )
        self.btn_simulate.pack(side="right")

        # Phase 5 — Arm / Disarm mobile alerts from the Command Center
        self.btn_arm = ctk.CTkButton(
            header_frame, text="Arm Mobile", width=110, height=32,
            fg_color=Theme.WARNING, hover_color=Theme.PRIMARY,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._set_armed(True),
        )
        self.btn_arm.pack(side="right", padx=(0, 8))

        self.btn_disarm = ctk.CTkButton(
            header_frame, text="Disarm", width=90, height=32,
            fg_color=Theme.PANEL_LIGHT, hover_color=Theme.BG_CARD,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda: self._set_armed(False),
        )
        self.btn_disarm.pack(side="right", padx=(0, 8))

        self.armed_label = ctk.CTkLabel(
            header_frame, text="Mobile: Disarmed",
            font=ctk.CTkFont(size=12), text_color=Theme.TEXT_SECONDARY,
        )
        self.armed_label.pack(side="right", padx=(0, 12))
        self.refresh_armed_state()

        # KPI Cards
        self.motion_card = KPICard(self, "Today's Motion", "0")
        self.motion_card.grid(row=1, column=0, sticky="ew", padx=(20, 10), pady=10)

        self.sensors_card = KPICard(self, "Active Sensors", "0 / 0", subtitle="● Offline")
        self.sensors_card.grid(row=1, column=1, sticky="ew", padx=10, pady=10)

        self.cameras_card = KPICard(self, "Cameras", "0 / 0", subtitle="● Offline")
        self.cameras_card.grid(row=1, column=2, sticky="ew", padx=10, pady=10)

        self.status_card = KPICard(
            self, "Security Status", "SECURE",
            subtitle="No active threats", value_color=Theme.SUCCESS,
        )
        self.status_card.grid(row=1, column=3, sticky="ew", padx=(10, 20), pady=10)

        # Phase 6 — hardware health strip so operators see ESP32 / camera / DB at a glance
        health = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        health.grid(row=2, column=0, columnspan=4, sticky="ew", padx=20, pady=(0, 8))

        ctk.CTkLabel(
            health, text="Hardware Health",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left", padx=16, pady=12)

        self.health_esp = ctk.CTkLabel(
            health, text="ESP32: …", font=ctk.CTkFont(size=12), text_color=Theme.TEXT_MUTED,
        )
        self.health_esp.pack(side="left", padx=16)

        self.health_cam = ctk.CTkLabel(
            health, text="Camera: …", font=ctk.CTkFont(size=12), text_color=Theme.TEXT_MUTED,
        )
        self.health_cam.pack(side="left", padx=16)

        self.health_db = ctk.CTkLabel(
            health, text="Database: …", font=ctk.CTkFont(size=12), text_color=Theme.TEXT_MUTED,
        )
        self.health_db.pack(side="left", padx=16)

        ctk.CTkButton(
            health, text="Refresh", width=80, height=28, fg_color=Theme.PANEL_LIGHT,
            command=self.refresh_health,
        ).pack(side="right", padx=16)

        # Main Content area (Recent Events)
        self.main_content = ctk.CTkFrame(
            self, fg_color=Theme.BG_SECONDARY, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        self.main_content.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=20, pady=(0, 20))

        self.main_content.grid_rowconfigure(1, weight=1)
        self.main_content.grid_columnconfigure(0, weight=1)

        recent_title = ctk.CTkLabel(
            self.main_content, text="Recent Events",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        )
        recent_title.grid(row=0, column=0, sticky="w", padx=20, pady=20)

        self.events_frame = ctk.CTkScrollableFrame(self.main_content, fg_color="transparent")
        self.events_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

        self.after(200, self.refresh_health)

    def on_show(self):
        self.refresh_armed_state()
        self.refresh_health()

    def refresh_health(self):
        # Phase 6 — pull live status from serial / camera / MySQL
        serial_ok = False
        cam_ok = False
        db_ok = False
        sm = getattr(self.app, "serial_manager", None)
        if sm is not None and hasattr(sm, "is_connected"):
            serial_ok = bool(sm.is_connected)
        cm = getattr(self.app, "camera_manager", None)
        if cm is not None:
            cam_ok = bool(getattr(cm, "running", False))
        db = getattr(self.app, "db", None)
        if db is not None and hasattr(db, "ping"):
            db_ok = bool(db.ping())

        self.health_esp.configure(
            text=f"ESP32: {'Online' if serial_ok else 'Offline'}",
            text_color=Theme.SUCCESS if serial_ok else Theme.WARNING,
        )
        self.health_cam.configure(
            text=f"Camera: {'Online' if cam_ok else 'Offline'}",
            text_color=Theme.SUCCESS if cam_ok else Theme.WARNING,
        )
        self.health_db.configure(
            text=f"Database: {'Online' if db_ok else 'Offline'}",
            text_color=Theme.SUCCESS if db_ok else Theme.DANGER,
        )

    def _on_simulate(self):
        uid = "Sensor01"
        dm = getattr(self.app, "device_manager", None)
        if dm is not None:
            pirs = dm.list_all_devices(device_type="pir") or []
            if pirs:
                uid = pirs[0].get("device_uid") or uid
        if hasattr(self.app, "motion_manager"):
            self.app.motion_manager.simulate(uid)

    def _set_armed(self, armed: bool):
        if hasattr(self.app, "set_mobile_armed"):
            self.app.set_mobile_armed(armed)
            if armed and getattr(self.app, "notifier_manager", None):
                if not self.app.notifier_manager.has_any_configured_channel():
                    self.app.notifications.show(
                        "Mobile Alerts",
                        "Armed, but no channel has valid credentials yet.",
                        type="warning",
                    )
                    return
            self.app.notifications.show(
                "Mobile Alerts",
                "Armed (Away)." if armed else "Disarmed (Home).",
                type="success" if armed else "info",
            )
        self.refresh_armed_state()

    def refresh_armed_state(self):
        armed = False
        sm = getattr(self.app, "settings_manager", None)
        if sm is not None:
            armed = str(sm.get("mobile_alerts_armed", "false")).lower() == "true"
        if hasattr(self, "armed_label"):
            self.armed_label.configure(
                text="Mobile: Armed" if armed else "Mobile: Disarmed",
                text_color=Theme.WARNING if armed else Theme.TEXT_SECONDARY,
            )

    def update_kpis(self, today_count, sensors_active, sensors_total, cameras_active, cameras_total, system_secure):
        self.motion_card.update_values(value=str(today_count))

        s_subtitle = "● Online" if sensors_active > 0 else "● Offline"
        self.sensors_card.update_values(value=f"{sensors_active} / {sensors_total}", subtitle=s_subtitle)

        c_subtitle = "● Online" if cameras_active > 0 else "● Offline"
        self.cameras_card.update_values(value=f"{cameras_active} / {cameras_total}", subtitle=c_subtitle)

        if system_secure:
            self.status_card.update_values(
                value="SECURE", subtitle="No active threats", value_color=Theme.SUCCESS,
            )
        else:
            self.status_card.update_values(
                value="ALERT", subtitle="Recent motion detected", value_color=Theme.DANGER,
            )

    def add_recent_event(self, timestamp, location, sensor_id, risk=None):
        event_frame = ctk.CTkFrame(self.events_frame, fg_color=Theme.BG_CARD, corner_radius=6)
        event_frame.pack(fill="x", pady=2)

        time_lbl = ctk.CTkLabel(
            event_frame, text=timestamp, text_color=Theme.TEXT_SECONDARY,
            font=ctk.CTkFont(size=12), width=100,
        )
        time_lbl.pack(side="left", padx=10, pady=10)

        risk_bit = f" · {risk}" if risk else ""
        loc_lbl = ctk.CTkLabel(
            event_frame,
            text=f"Motion detected at {location} ({sensor_id}){risk_bit}",
            text_color=Theme.TEXT_PRIMARY, font=ctk.CTkFont(size=12),
        )
        loc_lbl.pack(side="left", padx=10, pady=10)

        # keep only last 10 events
        children = self.events_frame.winfo_children()
        if len(children) > 10:
            children[0].destroy()
