import customtkinter as ctk
from utils.constants import Theme
from components.status_indicator import StatusIndicator

class LoginView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=Theme.BG_PRIMARY)
        self.app = app
        
        # Center content
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.card = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=15, border_width=1, border_color=Theme.BORDER)
        self.card.grid(row=0, column=0, padx=20, pady=20)
        
        # Logo/Title
        self.title_label = ctk.CTkLabel(self.card, text="SmartSecure\nSecurity Center", font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY)
        self.title_label.pack(padx=40, pady=(40, 30))
        
        # Inputs
        self.username_entry = ctk.CTkEntry(self.card, placeholder_text="Username", width=300, height=40, font=ctk.CTkFont(size=14))
        self.username_entry.pack(padx=40, pady=(0, 15))
        
        self.password_entry = ctk.CTkEntry(self.card, placeholder_text="Password", show="*", width=300, height=40, font=ctk.CTkFont(size=14))
        self.password_entry.pack(padx=40, pady=(0, 5))
        
        self.error_label = ctk.CTkLabel(self.card, text="", text_color=Theme.DANGER, font=ctk.CTkFont(size=12))
        self.error_label.pack(padx=40, pady=(0, 15))
        
        self.login_btn = ctk.CTkButton(self.card, text="SIGN IN", width=300, height=40, fg_color=Theme.PRIMARY, hover_color="#0099cc", font=ctk.CTkFont(size=14, weight="bold"), command=self.attempt_login)
        self.login_btn.pack(padx=40, pady=(0, 30))
        
        self.status = StatusIndicator(self.card, text="System Secure", status="online")
        self.status.pack(padx=40, pady=(0, 40), anchor="w")
        
        # Bind enter key
        self.username_entry.bind("<Return>", lambda e: self.attempt_login())
        self.password_entry.bind("<Return>", lambda e: self.attempt_login())

    def attempt_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if self.app.auth_manager.authenticate(username, password):
            self.error_label.configure(text="")
            self.app.on_login_success(username)
        else:
            self.error_label.configure(text="Invalid credentials")
