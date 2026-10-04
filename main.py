import customtkinter as ctk
import time
from utils.constants import Theme, WindowConfig
from utils.logger import logger
from utils.paths import ensure_runtime_dirs

from core.database import DatabaseManager
from core.settings_manager import SettingsManager
from core.auth import AuthManager
from core.camera_manager import CameraManager
from core.serial_manager import SerialManager
from core.motion_manager import MotionManager
from core.device_manager import DeviceManager
from core.notifiers import NotifierManager

from components.notifications import NotificationManager

from ui.login import LoginView
from ui.sidebar import Sidebar
from ui.topbar import TopBar
from ui.dashboard import DashboardView
from ui.live_monitoring import LiveMonitoringView
from ui.ai_security import AISecurityView
from ui.cameras import CamerasView
from ui.sensors import SensorsView
from ui.history import HistoryView
from ui.analytics import AnalyticsView
from ui.reports import ReportsView
from ui.settings import SettingsView
from ui.floor_plan import FloorPlanView
from ui.pages.environment_3d import Environment3DView


class SmartSecureApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # Snapshots/logs/assets always resolve from the project root
        ensure_runtime_dirs()

        # Configure Window
        self.title(WindowConfig.TITLE)
        self.geometry(f"{WindowConfig.DEFAULT_WIDTH}x{WindowConfig.DEFAULT_HEIGHT}")
        self.minsize(WindowConfig.MIN_WIDTH, WindowConfig.MIN_HEIGHT)
        self.configure(fg_color=Theme.BG_PRIMARY)

        ctk.set_appearance_mode("dark")

        # Initialize Core Services
        logger.info("Initializing Core Services...")
        self.db = DatabaseManager()
        self.settings_manager = SettingsManager(self.db)
        self.settings_manager.ensure_persisted_defaults()
        self.auth_manager = AuthManager(self.db)
        self.device_manager = DeviceManager(self.db, self.settings_manager)

        try:
            cam_index = int(self.settings_manager.get('camera_index', 0))
        except (TypeError, ValueError):
            cam_index = 0
        self.camera_manager = CameraManager(camera_index=cam_index)
        self.serial_manager = SerialManager(
            port=self.settings_manager.get('com_port'),
            baudrate=int(self.settings_manager.get('baud_rate', 115200)),
        )

        self.motion_manager = MotionManager(
            self.db, self.camera_manager, self.settings_manager, self.device_manager
        )
        # Phase 5 — mobile fan-out runs on a worker queue, never on the Tk thread
        self.notifier_manager = NotifierManager(self.settings_manager, self.db)
        self.motion_manager.set_notifier(self.notifier_manager)

        # Bind Serial callbacks
        self.serial_manager.register_callback(self.motion_manager.on_motion_detected)
        self.serial_manager.register_connection_callback(self.on_serial_connection_changed)

        # Bind Motion callback for UI updates (run in main thread via after)
        self.motion_manager.register_ui_callback(
            lambda event: self.after(0, self.on_motion_ui_update, event)
        )

        # UI Components
        self.notifications = NotificationManager(self)
        self.views = {}
        self.current_view = None
        self.sidebar = None
        self.topbar = None
        self.main_container = None

        self.show_login()

    def show_login(self):
        # Clear screen
        for w in self.winfo_children():
            w.destroy()

        self.views = {}
        self.current_view = None
        self.sidebar = None
        self.topbar = None
        self.main_container = None

        # Re-initialize notifications container on top of login
        self.notifications = NotificationManager(self)

        self.login_view = LoginView(self, self)
        self.login_view.pack(fill="both", expand=True)

    def on_login_success(self, username):
        logger.info(f"User '{username}' logged in successfully.")
        self.login_view.pack_forget()
        self.setup_main_ui(username)

        # Start background services after login — missing COM must not crash the app
        try:
            cam_index = int(self.settings_manager.get('camera_index', 0))
        except (TypeError, ValueError):
            cam_index = 0
        self.camera_manager.start(camera_index=cam_index)
        self.serial_manager.start()

        self.notifications.show("System Secure", f"Welcome back, {username}.", type="success")

    def setup_main_ui(self, username):
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        # Sidebar
        self.sidebar = Sidebar(self, self)
        self.sidebar.grid(row=0, column=0, rowspan=2, sticky="nsew")

        # Topbar
        self.topbar = TopBar(self, self)
        self.topbar.grid(row=0, column=1, sticky="new")
        self.topbar.user_info.configure(text=f"{username.capitalize()}\nAdministrator ⌄")

        # Main Content Container
        self.main_container = ctk.CTkFrame(self, fg_color=Theme.BG_SECONDARY, corner_radius=15)
        self.main_container.grid(row=1, column=1, sticky="nsew", padx=20, pady=(0, 20))
        self.main_container.grid_rowconfigure(0, weight=1)
        self.main_container.grid_columnconfigure(0, weight=1)
        self.main_container.pack_propagate(False)
        self.main_container.grid_propagate(False)

        # Every sidebar label maps to its own page (no Dashboard clones)
        self.views = {
            "Command Center": DashboardView(self.main_container, self),
            "Live Surveillance": LiveMonitoringView(self.main_container, self),
            "AI Security": AISecurityView(self.main_container, self),
            "3D Environment": Environment3DView(self.main_container, self),
            "Floor Plan": FloorPlanView(self.main_container, self),
            "Cameras": CamerasView(self.main_container, self),
            "Sensors": SensorsView(self.main_container, self),
            "Security Events": HistoryView(self.main_container, self),
            "Analytics": AnalyticsView(self.main_container, self),
            "Reports": ReportsView(self.main_container, self),
            "Settings": SettingsView(self.main_container, self),
        }

        self.show_view("3D Environment", "3D Environment", "📦")
        self.update_dashboard_kpis()
        self.refresh_unread_badges()
        self.sync_mobile_armed_ui()

    def show_view(self, name, label_text="View", icon="■"):
        if self.current_view:
            self.current_view.grid_forget()

            # Stop feed if leaving Live Monitoring
            if hasattr(self.current_view, 'stop_feed'):
                self.current_view.stop_feed()

        self.sidebar.set_active(name)
        subtitle = "Live Building View" if name == "3D Environment" else "Live System View"
        self.topbar.set_context(icon, name, subtitle)
        self.current_view = self.views.get(name)
        if self.current_view:
            self.current_view.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)

        if name == "Live Surveillance" and hasattr(self.current_view, 'start_feed'):
            self.current_view.start_feed()
        elif name == "Security Events" and hasattr(self.current_view, 'load_data'):
            self.current_view.load_data()
        elif name == "Analytics" and hasattr(self.current_view, 'draw_charts'):
            self.current_view.draw_charts()

        # Let placement / device list pages reload so they stay in sync
        if self.current_view is not None and hasattr(self.current_view, "on_show"):
            self.current_view.on_show()

    def update_dashboard_kpis(self, secure=True):
        if "Command Center" in self.views and hasattr(self.views["Command Center"], 'update_kpis'):
            today_count = self.db.get_today_count()
            # Phase 6 — KPI totals come from devices table; online flags from live hardware
            dm = getattr(self, "device_manager", None)
            pirs = dm.list_all_devices(device_type="pir") if dm else []
            cams = dm.list_all_devices(device_type="camera") if dm else []
            sensors_total = len(pirs or [])
            cameras_total = len(cams or [])
            sensors_enabled = sum(1 for d in (pirs or []) if d.get("enabled") in (True, 1, "1"))
            cameras_enabled = sum(1 for d in (cams or []) if d.get("enabled") in (True, 1, "1"))
            s_active = sensors_enabled if self.serial_manager.is_connected else 0
            c_active = cameras_enabled if self.camera_manager.running else 0
            if sensors_total == 0:
                sensors_total = 1
                s_active = 1 if self.serial_manager.is_connected else 0
            if cameras_total == 0:
                cameras_total = 1
                c_active = 1 if self.camera_manager.running else 0
            self.views["Command Center"].update_kpis(
                today_count, s_active, sensors_total, c_active, cameras_total, secure,
            )
            if hasattr(self.views["Command Center"], "refresh_health"):
                self.views["Command Center"].refresh_health()
        if self.sidebar and hasattr(self.sidebar, "set_system_secure"):
            self.sidebar.set_system_secure(secure)
        if self.topbar and hasattr(self.topbar, "set_system_secure"):
            self.topbar.set_system_secure(secure)

    def on_serial_connection_changed(self, is_connected):
        def _apply():
            if self.sidebar and hasattr(self.sidebar, "update_esp32_status"):
                self.sidebar.update_esp32_status(is_connected)
            # Phase 6 — keep Command Center health strip in sync with COM status
            dash = self.views.get("Command Center")
            if dash is not None and hasattr(dash, "refresh_health"):
                dash.refresh_health()
            settings = self.views.get("Settings")
            if settings is not None and hasattr(settings, "_refresh_serial_status"):
                settings._refresh_serial_status()
        self.after(0, _apply)

    def on_motion_ui_update(self, event):
        # Rich event dict from MotionManager (location, sensor, risk, coords, …)
        location = event.get("location") or "Unknown"
        sensor_id = event.get("sensor_id") or "?"
        risk = event.get("risk_level") or ""
        timestamp = time.strftime("%H:%M:%S")

        # Update Dashboard KPIs + Secure → Alert
        self.update_dashboard_kpis(secure=False)
        if "Command Center" in self.views and hasattr(self.views["Command Center"], "add_recent_event"):
            self.views["Command Center"].add_recent_event(timestamp, location, sensor_id, risk=risk)

        # Update Live Monitoring
        if "Live Surveillance" in self.views and hasattr(self.views["Live Surveillance"], "add_live_event"):
            risk_bit = f" [{risk}]" if risk else ""
            self.views["Live Surveillance"].add_live_event(
                f"Motion at {location} ({sensor_id}){risk_bit}", is_alert=True
            )

        # Trigger 5-step floor-plan animation + Active Alert
        env = self.views.get("3D Environment")
        if env is not None and hasattr(env, "trigger_motion_animation"):
            env.trigger_motion_animation(event)

        # Desktop toast
        if self.settings_manager.get("notifications_enabled", "true").lower() == "true":
            self.notifications.show(
                "Motion Detected",
                f"{location} - {sensor_id}" + (f" · {risk}" if risk else ""),
                type="danger",
            )

        # Unknown serial UID — toast (and Place Mode prompt if Phase 2 wiring is present)
        if event.get("sensor_known") is False:
            self.notifications.show(
                "Unknown Sensor",
                f"{sensor_id} is not placed — add it on the floor plan.",
                type="warning",
            )
            if env is not None and getattr(env, "placement", None) is not None:
                env.placement.prompt_place_unknown_sensor(sensor_id, location)

        # Unread badge on sidebar + topbar bell
        self.refresh_unread_badges()

        # Restore Secure after ~6s (desktop UI cooldown, independent of mobile)
        self.after(6000, lambda: self.update_dashboard_kpis(secure=True))

    def refresh_unread_badges(self):
        try:
            count = int(self.db.get_unread_count() or 0)
        except Exception:
            count = 0
        if self.sidebar and hasattr(self.sidebar, "set_unread_events"):
            self.sidebar.set_unread_events(count)
        if self.topbar and hasattr(self.topbar, "set_notification_count"):
            self.topbar.set_notification_count(count)

    def sync_mobile_armed_ui(self):
        # Keep topbar + dashboard Arm widgets in sync with settings
        if self.topbar and hasattr(self.topbar, "refresh_armed_state"):
            self.topbar.refresh_armed_state()
        dash = self.views.get("Command Center") if self.views else None
        if dash is not None and hasattr(dash, "refresh_armed_state"):
            dash.refresh_armed_state()
        settings = self.views.get("Settings") if self.views else None
        if settings is not None and hasattr(settings, "_refresh_channel_warning"):
            settings._refresh_channel_warning()
            if hasattr(settings, "_refresh_armed_ui"):
                settings._refresh_armed_ui()

    def toggle_mobile_armed(self):
        cur = str(self.settings_manager.get("mobile_alerts_armed", "false")).lower() == "true"
        new_val = "false" if cur else "true"
        self.settings_manager.set("mobile_alerts_armed", new_val)
        self.sync_mobile_armed_ui()
        armed = new_val == "true"
        # Warn when Armed with no usable channel credentials
        if armed and self.notifier_manager and not self.notifier_manager.has_any_configured_channel():
            self.notifications.show(
                "Mobile Alerts Armed",
                "Armed, but no channel has valid credentials yet.",
                type="warning",
            )
        else:
            self.notifications.show(
                "Mobile Alerts",
                "Armed (Away)." if armed else "Disarmed (Home).",
                type="success" if armed else "info",
            )

    def set_mobile_armed(self, armed: bool):
        self.settings_manager.set("mobile_alerts_armed", "true" if armed else "false")
        self.sync_mobile_armed_ui()

    def open_event_details(self, event, on_changed=None):
        # Shared entry point so Active Alert, bell, and History open the same modal
        if not event:
            return
        event_id = event.get("id") or event.get("event_id")
        # Prefer a fresh DB row so mobile_* fields are current even before Phase 5
        if event_id and getattr(self, "db", None):
            fresh = self.db.get_motion_log(event_id)
            if fresh:
                event = fresh

        def _after_change():
            self.refresh_unread_badges()
            if callable(on_changed):
                on_changed()
            # Keep the Security Events table in sync when it is already on screen
            history = self.views.get("Security Events") if self.views else None
            if (
                history is not None
                and self.current_view is history
                and hasattr(history, "load_data")
                and on_changed != history.load_data
            ):
                history.load_data()

        from components.event_details_modal import EventDetailsModal
        EventDetailsModal(self, event, app=self, on_changed=_after_change)

    def _stop_services(self, stop_notifier: bool = False):
        # Shared cleanup for logout and window close
        try:
            self.serial_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping serial: {e}")
        try:
            self.camera_manager.stop()
        except Exception as e:
            logger.error(f"Error stopping camera: {e}")
        if stop_notifier:
            try:
                # Only drain on full app exit — logout should keep the worker for the next login
                if getattr(self, "notifier_manager", None):
                    self.notifier_manager.shutdown(timeout=2.0)
            except Exception as e:
                logger.error(f"Error stopping notifier: {e}")

    def logout(self):
        logger.info("User logged out — stopping camera and serial.")
        self._stop_services(stop_notifier=False)
        self.show_login()

    def on_closing(self):
        logger.info("Shutting down...")
        self._stop_services(stop_notifier=True)
        self.destroy()


if __name__ == "__main__":
    app = SmartSecureApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()
