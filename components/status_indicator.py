import customtkinter as ctk
from utils.constants import Theme

class StatusIndicator(ctk.CTkFrame):
    def __init__(self, master, text="Offline", status="offline"):
        super().__init__(master, fg_color="transparent")
        
        self.color_map = {
            "online": Theme.SUCCESS,
            "offline": Theme.TEXT_MUTED,
            "warning": Theme.WARNING,
            "danger": Theme.DANGER,
            "active": Theme.PRIMARY
        }
        
        color = self.color_map.get(status, Theme.TEXT_MUTED)
        
        self.dot = ctk.CTkLabel(self, text="●", text_color=color, font=ctk.CTkFont(size=16))
        self.dot.pack(side="left", padx=(0, 5))
        
        self.label = ctk.CTkLabel(self, text=text, text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=12))
        self.label.pack(side="left")

    def update_status(self, text=None, status=None):
        if text:
            self.label.configure(text=text)
        if status:
            color = self.color_map.get(status, Theme.TEXT_MUTED)
            self.dot.configure(text_color=color)
