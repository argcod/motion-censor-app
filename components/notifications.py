import customtkinter as ctk
import datetime
from utils.constants import Theme

class ToastNotification(ctk.CTkFrame):
    def __init__(self, master, title, message, duration=3000, type="info"):
        super().__init__(master, fg_color=Theme.BG_CARD, border_width=1, border_color=Theme.BORDER, corner_radius=8)
        self.master = master
        
        color_map = {
            "info": Theme.PRIMARY,
            "success": Theme.SUCCESS,
            "warning": Theme.WARNING,
            "danger": Theme.DANGER
        }
        accent_color = color_map.get(type, Theme.PRIMARY)
        
        # Accent bar on the left
        self.accent = ctk.CTkFrame(self, fg_color=accent_color, width=4, corner_radius=0)
        self.accent.pack(side="left", fill="y", pady=5, padx=(5, 10))
        
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(side="left", fill="both", expand=True, padx=(0, 15), pady=15)
        
        header = ctk.CTkFrame(content, fg_color="transparent")
        header.pack(fill="x")
        
        ctk.CTkLabel(header, text=title, font=ctk.CTkFont(weight="bold", size=14), text_color=Theme.TEXT_PRIMARY).pack(side="left")
        
        ctk.CTkLabel(content, text=message, font=ctk.CTkFont(size=12), text_color=Theme.TEXT_SECONDARY, justify="left").pack(anchor="w", pady=(5, 0))
        
        # Self-destruct after duration
        if duration > 0:
            self.after(duration, self.destroy)

class NotificationManager:
    def __init__(self, root):
        self.root = root
        
        self.container = ctk.CTkFrame(self.root, fg_color="transparent")
        self.container.place(relx=1.0, rely=1.0, anchor="se", x=-20, y=-20)
        
    def show(self, title, message, duration=4000, type="info"):
        toast = ToastNotification(self.container, title, message, duration, type)
        toast.pack(side="bottom", pady=(10, 0), anchor="e")
