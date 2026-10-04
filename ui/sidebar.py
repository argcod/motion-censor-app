import customtkinter as ctk
from utils.constants import Theme


class Sidebar(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, width=220, fg_color=Theme.BG_PRIMARY, corner_radius=0, border_width=0)
        self.app = app
        self._esp32_connected = False
        self._unread_events = 0

        self.grid_rowconfigure(20, weight=1)
        self.pack_propagate(False)

        self.buttons = {}
        self._badge_labels = {}

        nav_items = [
            ("Command Center", "Command Center", "📊"),
            ("Live Surveillance", "Live Surveillance", "🖥"),
            ("AI Security", "AI Security", "🛡"),
            ("3D Environment", "3D Environment", "📦"),
            ("Floor Plan", "Floor Plan", "📐"),
            ("Cameras", "Cameras", "📷"),
            ("Sensors", "Sensors", "📡"),
            ("Security Events", "Security Events", "❗"),
            ("Analytics", "Analytics", "📈"),
            ("Reports", "Reports", "📄"),
            ("Settings", "Settings", "⚙"),
        ]

        for i, (label_text, view_name, icon) in enumerate(nav_items):
            row = ctk.CTkFrame(self, fg_color="transparent")
            row.grid(row=i, column=0, sticky="ew", padx=10, pady=3)
            row.grid_columnconfigure(0, weight=1)

            btn = ctk.CTkButton(
                row,
                text=f"  {icon}   {label_text}",
                anchor="w",
                fg_color="transparent",
                text_color=Theme.TEXT_SECONDARY,
                hover_color=Theme.PANEL_LIGHT,
                font=ctk.CTkFont(size=13),
                corner_radius=8,
                height=36,
                command=lambda v=view_name, l=label_text, ic=icon: self._nav_clicked(v, l, ic),
            )
            btn.grid(row=0, column=0, sticky="ew")
            self.buttons[view_name] = btn

            if view_name == "Security Events":
                badge = ctk.CTkLabel(
                    row, text="", width=22, height=22,
                    fg_color=Theme.DANGER, corner_radius=11,
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=Theme.TEXT_PRIMARY,
                )
                # Hidden until count > 0
                self._badge_labels[view_name] = badge

        # Bottom status card
        self.status_frame = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        self.status_frame.grid(row=21, column=0, sticky="ew", padx=15, pady=20)

        self.shield_label = ctk.CTkLabel(
            self.status_frame, text="🛡", font=ctk.CTkFont(size=22), text_color=Theme.SUCCESS,
        )
        self.shield_label.pack(anchor="w", padx=15, pady=(10, 0))

        self.status_title = ctk.CTkLabel(
            self.status_frame, text="System Secure",
            font=ctk.CTkFont(size=13, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        )
        self.status_title.pack(anchor="w", padx=15, pady=(5, 0))

        self.status_subtitle = ctk.CTkLabel(
            self.status_frame, text="All systems operational",
            font=ctk.CTkFont(size=11), text_color=Theme.TEXT_MUTED,
        )
        self.status_subtitle.pack(anchor="w", padx=15, pady=(0, 4))

        self.esp32_label = ctk.CTkLabel(
            self.status_frame, text="ESP32: Connecting…",
            font=ctk.CTkFont(size=10), text_color=Theme.TEXT_MUTED,
        )
        self.esp32_label.pack(anchor="w", padx=15, pady=(0, 10))

    def _nav_clicked(self, view_name, label_text, icon):
        self.app.show_view(view_name, label_text, icon)

    def set_active(self, view_name):
        for name, btn in self.buttons.items():
            if name == view_name:
                btn.configure(fg_color=Theme.PRIMARY, text_color=Theme.TEXT_PRIMARY)
            else:
                btn.configure(fg_color="transparent", text_color=Theme.TEXT_SECONDARY)

    def update_esp32_status(self, is_connected: bool):
        """Called from main thread when serial connect/disconnect changes."""
        self._esp32_connected = bool(is_connected)
        if is_connected:
            self.esp32_label.configure(text="ESP32: Connected", text_color=Theme.SUCCESS)
        else:
            self.esp32_label.configure(text="ESP32: Disconnected", text_color=Theme.WARNING)

    def set_system_secure(self, secure: bool = True):
        if secure:
            self.shield_label.configure(text_color=Theme.SUCCESS)
            self.status_title.configure(text="System Secure", text_color=Theme.TEXT_PRIMARY)
            self.status_subtitle.configure(text="All systems operational")
            self.status_frame.configure(border_color=Theme.BORDER)
        else:
            self.shield_label.configure(text_color=Theme.DANGER)
            self.status_title.configure(text="Motion Alert", text_color=Theme.DANGER_LIGHT)
            self.status_subtitle.configure(text="Activity detected")
            self.status_frame.configure(border_color=Theme.DANGER)

    def set_unread_events(self, count: int):
        self._unread_events = max(0, int(count))
        badge = self._badge_labels.get("Security Events")
        if not badge:
            return
        if self._unread_events > 0:
            badge.configure(text=str(min(self._unread_events, 99)))
            badge.grid(row=0, column=1, padx=(4, 0))
        else:
            badge.grid_forget()
