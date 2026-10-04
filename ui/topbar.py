import customtkinter as ctk

from utils.constants import Theme





class TopBar(ctk.CTkFrame):

    def __init__(self, master, app):

        super().__init__(master, height=64, fg_color=Theme.BG_PRIMARY, corner_radius=0, border_width=0)

        self.app = app

        self._notif_count = 0

        self._notif_panel = None



        self.grid_columnconfigure(1, weight=1)

        self.pack_propagate(False)



        # Left: brand

        self.title_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.title_frame.grid(row=0, column=0, sticky="w", padx=20, pady=10)



        self.logo_label = ctk.CTkLabel(

            self.title_frame, text="🛡", font=ctk.CTkFont(size=24), text_color=Theme.PRIMARY,

        )

        self.logo_label.pack(side="left", padx=(0, 10))



        self.title_label = ctk.CTkLabel(

            self.title_frame,

            text="Smart Motion Detection\nAlarm System using IoT",

            font=ctk.CTkFont(size=12, weight="bold"),

            text_color=Theme.TEXT_PRIMARY,

            justify="left",

        )

        self.title_label.pack(side="left")



        # Middle: page context

        self.context_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.context_frame.grid(row=0, column=1, sticky="w", padx=40, pady=10)



        self.context_icon = ctk.CTkLabel(

            self.context_frame, text="📦", font=ctk.CTkFont(size=20), text_color=Theme.TEXT_SECONDARY,

        )

        self.context_icon.pack(side="left", padx=(0, 10))



        self.context_title = ctk.CTkLabel(

            self.context_frame,

            text="3D Environment\nLive Building View",

            font=ctk.CTkFont(size=12),

            text_color=Theme.TEXT_PRIMARY,

            justify="left",

        )

        self.context_title.pack(side="left")



        # Right: status / arm / notifications / user

        self.right_frame = ctk.CTkFrame(self, fg_color="transparent")

        self.right_frame.grid(row=0, column=2, sticky="e", padx=20, pady=10)



        self.status_pill = ctk.CTkFrame(

            self.right_frame, fg_color=Theme.BG_CARD, corner_radius=15,

            border_width=1, border_color=Theme.BORDER,

        )

        self.status_pill.pack(side="left", padx=12)



        self.status_dot = ctk.CTkLabel(

            self.status_pill, text="●", font=ctk.CTkFont(size=14), text_color=Theme.SUCCESS,

        )

        self.status_dot.pack(side="left", padx=(10, 5), pady=4)



        self.status_text = ctk.CTkLabel(

            self.status_pill, text="System Secure",

            font=ctk.CTkFont(size=12), text_color=Theme.TEXT_PRIMARY,

        )

        self.status_text.pack(side="left", padx=(0, 12), pady=4)



        # Phase 5 — quick Arm / Disarm for mobile alerts without opening Settings

        self.arm_btn = ctk.CTkButton(

            self.right_frame, text="Mobile: Disarmed", width=130, height=28,

            fg_color=Theme.BG_CARD, hover_color=Theme.PANEL_LIGHT,

            border_width=1, border_color=Theme.BORDER,

            font=ctk.CTkFont(size=11, weight="bold"),

            text_color=Theme.TEXT_SECONDARY,

            command=self._toggle_mobile_armed,

        )

        self.arm_btn.pack(side="left", padx=6)



        self.bell_btn = ctk.CTkButton(

            self.right_frame, text="🔔", width=40, height=32,

            fg_color="transparent", hover_color=Theme.PANEL_LIGHT,

            font=ctk.CTkFont(size=16),

            command=self._on_bell_click,

        )

        self.bell_btn.pack(side="left", padx=6)



        self.bell_badge = ctk.CTkLabel(

            self.right_frame, text="", width=18, height=18,

            fg_color=Theme.DANGER, corner_radius=9,

            font=ctk.CTkFont(size=9, weight="bold"),

            text_color=Theme.TEXT_PRIMARY,

        )

        # Placed only when count > 0



        self.user_icon = ctk.CTkLabel(

            self.right_frame, text="👤", font=ctk.CTkFont(size=18), text_color=Theme.PRIMARY,

        )

        self.user_icon.pack(side="left", padx=(12, 4))



        self.user_info = ctk.CTkLabel(

            self.right_frame, text="Admin\nAdministrator",

            font=ctk.CTkFont(size=11), text_color=Theme.TEXT_PRIMARY, justify="left",

        )

        self.user_info.pack(side="left")



        self.logout_btn = ctk.CTkButton(

            self.right_frame, text="↪", width=36, height=32,

            fg_color="transparent", hover_color=Theme.PANEL_LIGHT,

            font=ctk.CTkFont(size=16), text_color=Theme.TEXT_SECONDARY,

            command=self._on_logout,

        )

        self.logout_btn.pack(side="left", padx=(8, 0))



        self.refresh_armed_state()



    def set_context(self, icon, title, subtitle):

        self.context_icon.configure(text=icon)

        self.context_title.configure(text=f"{title}\n{subtitle}")



    def set_system_secure(self, secure: bool = True):

        if secure:

            self.status_dot.configure(text_color=Theme.SUCCESS)

            self.status_text.configure(text="System Secure")

            self.status_pill.configure(border_color=Theme.BORDER)

        else:

            self.status_dot.configure(text_color=Theme.DANGER)

            self.status_text.configure(text="Alert Active")

            self.status_pill.configure(border_color=Theme.DANGER)



    def refresh_armed_state(self):

        armed = False

        sm = getattr(self.app, "settings_manager", None)

        if sm is not None:

            armed = str(sm.get("mobile_alerts_armed", "false")).lower() == "true"

        if armed:

            self.arm_btn.configure(

                text="Mobile: Armed",

                text_color=Theme.WARNING,

                border_color=Theme.WARNING,

            )

        else:

            self.arm_btn.configure(

                text="Mobile: Disarmed",

                text_color=Theme.TEXT_SECONDARY,

                border_color=Theme.BORDER,

            )



    def _toggle_mobile_armed(self):

        if hasattr(self.app, "toggle_mobile_armed"):

            self.app.toggle_mobile_armed()

        else:

            sm = self.app.settings_manager

            cur = str(sm.get("mobile_alerts_armed", "false")).lower() == "true"

            sm.set("mobile_alerts_armed", "false" if cur else "true")

            self.refresh_armed_state()



    def set_notification_count(self, count: int):

        # Keeps the red badge in sync with unread motion_log rows

        self._notif_count = max(0, int(count))

        if self._notif_count > 0:

            self.bell_badge.configure(text=str(min(self._notif_count, 99)))

            self.bell_badge.pack(side="left", padx=(0, 4), before=self.user_icon)

        else:

            self.bell_badge.pack_forget()



    def _on_bell_click(self):

        # Toggle the unread notification center under the bell

        if self._notif_panel is not None:

            try:

                if self._notif_panel.winfo_exists():

                    self._notif_panel.close()

                    return

            except Exception:

                self._notif_panel = None



        from components.notification_center import NotificationCenter



        self._notif_panel = NotificationCenter(

            self.winfo_toplevel(),

            self.app,

            anchor_widget=self.bell_btn,

            on_close=self._on_panel_closed,

        )



    def _on_panel_closed(self):

        self._notif_panel = None



    def _on_logout(self):

        if hasattr(self.app, "logout"):

            self.app.logout()


