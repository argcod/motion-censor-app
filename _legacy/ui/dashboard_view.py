import customtkinter as ctk

class DashboardView(ctk.CTkFrame):
    def __init__(self, parent):
        super().__init__(parent)
        
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)
        self.grid_rowconfigure(1, weight=1)
        
        # Status Card
        self.status_card = self.create_card("System Status", "Active", "green")
        self.status_card.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Sensor Card
        self.sensor_card = self.create_card("Sensor Status", "No Motion", "gray")
        self.sensor_card.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        # Last Motion Card
        self.last_motion_card = self.create_card("Last Motion", "N/A", "white")
        self.last_motion_card.grid(row=0, column=2, padx=10, pady=10, sticky="nsew")
        
        # Total Detections Card
        self.total_card = self.create_card("Today's Detections", "0", "white")
        self.total_card.grid(row=0, column=3, padx=10, pady=10, sticky="nsew")
        
        # Placeholder for main content (like a live feed or quick history)
        self.main_content = ctk.CTkFrame(self)
        self.main_content.grid(row=1, column=0, columnspan=4, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.main_content, text="Live Camera Feed Placeholder", text_color="gray").pack(expand=True)
        
        # References for updating values
        self.sensor_val_label = self.sensor_card.winfo_children()[1]
        self.last_val_label = self.last_motion_card.winfo_children()[1]
        self.total_val_label = self.total_card.winfo_children()[1]

    def create_card(self, title, initial_value, color):
        frame = ctk.CTkFrame(self, corner_radius=10)
        title_label = ctk.CTkLabel(frame, text=title, font=ctk.CTkFont(size=14))
        title_label.pack(padx=10, pady=(10, 5))
        
        value_label = ctk.CTkLabel(frame, text=initial_value, font=ctk.CTkFont(size=20, weight="bold"), text_color=color)
        value_label.pack(padx=10, pady=(0, 10))
        return frame

    def update_sensor_state(self, has_motion, last_time, total_count):
        if has_motion:
            self.sensor_val_label.configure(text="Motion Detected!", text_color="red")
        else:
            self.sensor_val_label.configure(text="No Motion", text_color="gray")
            
        self.last_val_label.configure(text=last_time)
        self.total_val_label.configure(text=str(total_count))
