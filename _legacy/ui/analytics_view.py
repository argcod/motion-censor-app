import customtkinter as ctk
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import datetime

class AnalyticsView(ctk.CTkFrame):
    def __init__(self, parent, db_handler):
        super().__init__(parent)
        self.db = db_handler
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        self.chart_frame = ctk.CTkFrame(self)
        self.chart_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.refresh_btn = ctk.CTkButton(self, text="Refresh Chart", command=self.draw_chart)
        self.refresh_btn.grid(row=1, column=0, pady=10)
        
        self.canvas = None
        self.draw_chart()

    def draw_chart(self):
        # Clear old canvas
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
            
        logs = self.db.get_motion_logs(limit=1000)
        
        # Simple hourly counting for today
        hourly_counts = {i: 0 for i in range(24)}
        today = datetime.datetime.now().date()
        
        for log in logs:
            if isinstance(log['timestamp'], str):
                dt = datetime.datetime.strptime(log['timestamp'], '%Y-%m-%d %H:%M:%S')
            else:
                dt = log['timestamp']
                
            if dt.date() == today:
                hourly_counts[dt.hour] += 1
                
        hours = list(hourly_counts.keys())
        counts = list(hourly_counts.values())

        # Setup matplotlib figure
        fig, ax = plt.subplots(figsize=(6, 4), facecolor='#2b2b2b')
        ax.bar(hours, counts, color='#1f6aa5')
        ax.set_title("Today's Motion Events by Hour", color='white')
        ax.set_xlabel("Hour of Day", color='white')
        ax.set_ylabel("Detections", color='white')
        ax.tick_params(colors='white')
        
        # Make background of plot match dark theme
        ax.set_facecolor('#2b2b2b')
        fig.patch.set_facecolor('#2b2b2b')

        self.canvas = FigureCanvasTkAgg(fig, master=self.chart_frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        plt.close(fig) # Prevent memory leaks
