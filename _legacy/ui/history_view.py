import customtkinter as ctk
from tkinter import ttk
import pandas as pd
from tkinter import filedialog
from fpdf import FPDF

class HistoryView(ctk.CTkFrame):
    def __init__(self, parent, db_handler):
        super().__init__(parent)
        self.db = db_handler
        
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Toolbar
        self.toolbar = ctk.CTkFrame(self, height=50)
        self.toolbar.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        
        self.refresh_btn = ctk.CTkButton(self.toolbar, text="Refresh", command=self.load_data)
        self.refresh_btn.pack(side="left", padx=10)
        
        self.export_csv_btn = ctk.CTkButton(self.toolbar, text="Export CSV", command=self.export_csv)
        self.export_csv_btn.pack(side="right", padx=10)
        
        self.export_pdf_btn = ctk.CTkButton(self.toolbar, text="Export PDF", command=self.export_pdf)
        self.export_pdf_btn.pack(side="right", padx=10)
        
        # Table (Treeview)
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b",
                        foreground="white",
                        rowheight=25,
                        fieldbackground="#2b2b2b")
        style.map('Treeview', background=[('selected', '#1f6aa5')])
        
        self.tree_frame = ctk.CTkFrame(self)
        self.tree_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))
        
        self.tree_frame.grid_rowconfigure(0, weight=1)
        self.tree_frame.grid_columnconfigure(0, weight=1)
        
        self.tree = ttk.Treeview(self.tree_frame, columns=("ID", "Timestamp", "Location", "Sensor ID"), show="headings")
        self.tree.heading("ID", text="ID")
        self.tree.heading("Timestamp", text="Timestamp")
        self.tree.heading("Location", text="Location")
        self.tree.heading("Sensor ID", text="Sensor ID")
        
        self.tree.column("ID", width=50)
        self.tree.column("Timestamp", width=200)
        self.tree.column("Location", width=200)
        self.tree.column("Sensor ID", width=150)
        
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ttk.Scrollbar(self.tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        scrollbar.grid(row=0, column=1, sticky="ns")
        
        self.logs = []
        self.load_data()

    def load_data(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        self.logs = self.db.get_motion_logs(limit=100)
        for log in self.logs:
            self.tree.insert("", "end", values=(log['id'], log['timestamp'], log['location'], log['sensor_id']))

    def export_csv(self):
        if not self.logs:
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if filepath:
            df = pd.DataFrame(self.logs)
            df.to_csv(filepath, index=False)

    def export_pdf(self):
        if not self.logs:
            return
        filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if filepath:
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            pdf.cell(200, 10, txt="Motion Detection Logs", ln=True, align="C")
            pdf.ln(10)
            
            for log in self.logs:
                pdf.cell(200, 10, txt=f"ID: {log['id']} - Time: {log['timestamp']} - Loc: {log['location']} - Sensor: {log['sensor_id']}", ln=True)
            
            pdf.output(filepath)
