import customtkinter as ctk
from PIL import Image

class LoginView(ctk.CTkFrame):
    def __init__(self, parent, auth_manager, on_login_success):
        super().__init__(parent)
        self.auth_manager = auth_manager
        self.on_login_success = on_login_success
        
        self.pack(fill="both", expand=True)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.login_frame = ctk.CTkFrame(self, corner_radius=15)
        self.login_frame.grid(row=0, column=0, padx=20, pady=20)
        
        self.title_label = ctk.CTkLabel(self.login_frame, text="Security Dashboard", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(padx=30, pady=(30, 20))
        
        self.username_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Username", width=250)
        self.username_entry.pack(padx=30, pady=(10, 10))
        
        self.password_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Password", show="*", width=250)
        self.password_entry.pack(padx=30, pady=(10, 20))
        
        self.error_label = ctk.CTkLabel(self.login_frame, text="", text_color="red")
        self.error_label.pack(padx=30, pady=(0, 10))
        
        self.login_btn = ctk.CTkButton(self.login_frame, text="Login", command=self.attempt_login, width=250)
        self.login_btn.pack(padx=30, pady=(0, 30))
        
    def attempt_login(self):
        username = self.username_entry.get()
        password = self.password_entry.get()
        
        if self.auth_manager.authenticate(username, password):
            self.error_label.configure(text="")
            self.on_login_success()
        else:
            self.error_label.configure(text="Invalid credentials")
