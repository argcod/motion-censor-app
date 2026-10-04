import customtkinter as ctk
from PIL import Image
import cv2
from utils.constants import Theme
from components.status_indicator import StatusIndicator

class LiveMonitoringView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)
        
        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(20, 10))
        
        title = ctk.CTkLabel(header_frame, text="Live Monitoring", font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY)
        title.pack(side="left")
        
        self.sys_status = StatusIndicator(header_frame, text="System Live", status="online")
        self.sys_status.pack(side="left", padx=20)
        
        # Camera Feed Area
        self.feed_frame = ctk.CTkFrame(self, fg_color=Theme.BG_SECONDARY, corner_radius=10, border_width=1, border_color=Theme.BORDER)
        self.feed_frame.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=10)
        
        self.video_label = ctk.CTkLabel(self.feed_frame, text="No Camera Connected\n\nConfigure in Settings.", text_color=Theme.TEXT_MUTED)
        self.video_label.pack(expand=True, fill="both")
        
        # Live Events Sidebar
        self.events_frame = ctk.CTkFrame(self, fg_color=Theme.BG_SECONDARY, corner_radius=10, border_width=1, border_color=Theme.BORDER)
        self.events_frame.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=10)
        
        self.events_frame.grid_rowconfigure(1, weight=1)
        
        e_title = ctk.CTkLabel(self.events_frame, text="LIVE EVENTS", font=ctk.CTkFont(size=14, weight="bold"), text_color=Theme.TEXT_SECONDARY)
        e_title.grid(row=0, column=0, sticky="w", padx=20, pady=20)
        
        self.live_events_scroll = ctk.CTkScrollableFrame(self.events_frame, fg_color="transparent")
        self.live_events_scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        self.update_job = None
        
    def start_feed(self):
        self.update_video_frame()
        
    def stop_feed(self):
        if self.update_job:
            self.after_cancel(self.update_job)
            self.update_job = None
            
    def update_video_frame(self):
        if not self.winfo_ismapped():
            # Don't update if not visible
            self.update_job = self.after(100, self.update_video_frame)
            return
            
        if self.app.camera_manager and self.app.camera_manager.running:
            frame = self.app.camera_manager.get_frame()
            if frame is not None:
                # Resize keeping aspect ratio
                h, w, _ = frame.shape
                lbl_w = self.feed_frame.winfo_width()
                lbl_h = self.feed_frame.winfo_height()
                
                if lbl_w > 10 and lbl_h > 10:
                    scale = min(lbl_w/w, lbl_h/h)
                    new_w = int(w * scale)
                    new_h = int(h * scale)
                    
                    if new_w > 0 and new_h > 0:
                        frame_resized = cv2.resize(frame, (new_w, new_h))
                        img = Image.fromarray(frame_resized)
                        ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(new_w, new_h))
                        
                        self.video_label.configure(image=ctk_img, text="")
            else:
                self.video_label.configure(image="", text="Connecting to camera...")
        else:
            self.video_label.configure(image="", text="Camera Offline")
            
        self.update_job = self.after(33, self.update_video_frame) # ~30fps

    def add_live_event(self, text, is_alert=False):
        color = Theme.DANGER if is_alert else Theme.SUCCESS
        dot = "🔴" if is_alert else "🟢"
        
        event = ctk.CTkLabel(self.live_events_scroll, text=f"{dot} {text}", text_color=color, font=ctk.CTkFont(size=12), justify="left", anchor="w")
        event.pack(fill="x", pady=5)
        
        children = self.live_events_scroll.winfo_children()
        if len(children) > 20:
            children[0].destroy()
