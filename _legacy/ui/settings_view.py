import customtkinter as ctk

class SettingsView(ctk.CTkFrame):
    def __init__(self, parent, app=None):
        super().__init__(parent)
        self.app = app
        
        self.grid_columnconfigure(0, weight=1)
        
        title = ctk.CTkLabel(self, text="Device & System Settings", font=ctk.CTkFont(size=20, weight="bold"))
        title.pack(pady=20, padx=20, anchor="w")
        
        # Sensor Override Settings
        override_frame = ctk.CTkFrame(self)
        override_frame.pack(pady=10, padx=20, anchor="w", fill="x")
        
        ctk.CTkLabel(override_frame, text="Sensor Location Override", font=ctk.CTkFont(weight="bold")).pack(pady=10, padx=10, anchor="w")
        
        self.location_entry = ctk.CTkEntry(override_frame, placeholder_text="e.g. Front Door")
        self.location_entry.pack(pady=5, padx=10, anchor="w", fill="x")
        
        # Alarm Setting
        self.alarm_var = ctk.StringVar(value="on")
        self.alarm_switch = ctk.CTkSwitch(self, text="Alarm ON/OFF", variable=self.alarm_var, onvalue="on", offvalue="off")
        self.alarm_switch.pack(pady=10, padx=20, anchor="w")
        
        # Notifications Setting
        self.notif_var = ctk.StringVar(value="on")
        self.notif_switch = ctk.CTkSwitch(self, text="Email/SMS Notifications", variable=self.notif_var, onvalue="on", offvalue="off")
        self.notif_switch.pack(pady=10, padx=20, anchor="w")
        
        # Sensitivity
        ctk.CTkLabel(self, text="Sensor Sensitivity").pack(pady=(10, 0), padx=20, anchor="w")
        self.sensitivity_slider = ctk.CTkSlider(self, from_=0, to=100)
        self.sensitivity_slider.set(50)
        self.sensitivity_slider.pack(pady=(0, 10), padx=20, anchor="w")
        
        # Serial Settings
        serial_frame = ctk.CTkFrame(self)
        serial_frame.pack(pady=20, padx=20, anchor="w", fill="x")
        
        ctk.CTkLabel(serial_frame, text="Serial Connection (Wired Mode)", font=ctk.CTkFont(weight="bold")).pack(pady=10, padx=10, anchor="w")
        
        self.com_entry = ctk.CTkEntry(serial_frame, placeholder_text="COM Port (e.g., COM3)")
        self.com_entry.pack(pady=5, padx=10, anchor="w", fill="x")
        self.com_entry.insert(0, "COM10")
        
        self.baud_entry = ctk.CTkEntry(serial_frame, placeholder_text="Baud Rate")
        self.baud_entry.pack(pady=5, padx=10, anchor="w", fill="x")
        self.baud_entry.insert(0, "115200")
        
        save_btn = ctk.CTkButton(serial_frame, text="Save Settings", command=self.save_settings)
        save_btn.pack(pady=10, padx=10, anchor="w")
        
    def save_settings(self):
        print(f"Settings saved: Port={self.com_entry.get()}, Loc={self.location_entry.get()}")
        if self.app and self.location_entry.get().strip():
            self.app.location_override = self.location_entry.get().strip()
        elif self.app:
            self.app.location_override = None
