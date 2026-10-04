import customtkinter as ctk
from utils.constants import Theme

class KPICard(ctk.CTkFrame):
    def __init__(self, master, title, value, subtitle="", value_color=Theme.TEXT_PRIMARY):
        super().__init__(master, fg_color=Theme.BG_CARD, border_width=1, border_color=Theme.BORDER, corner_radius=10)
        
        self.title_label = ctk.CTkLabel(self, text=title.upper(), font=ctk.CTkFont(size=12, weight="bold"), text_color=Theme.TEXT_SECONDARY)
        self.title_label.pack(anchor="w", padx=20, pady=(20, 5))
        
        self.value_label = ctk.CTkLabel(self, text=value, font=ctk.CTkFont(size=32, weight="bold"), text_color=value_color)
        self.value_label.pack(anchor="w", padx=20, pady=5)
        
        self.subtitle_label = ctk.CTkLabel(self, text=subtitle, font=ctk.CTkFont(size=12), text_color=Theme.TEXT_MUTED)
        self.subtitle_label.pack(anchor="w", padx=20, pady=(5, 20))

    def update_values(self, value=None, subtitle=None, value_color=None):
        if value is not None:
            self.value_label.configure(text=str(value))
        if subtitle is not None:
            self.subtitle_label.configure(text=str(subtitle))
        if value_color is not None:
            self.value_label.configure(text_color=value_color)
