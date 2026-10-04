import customtkinter as ctk
from tkinter import ttk
from utils.constants import Theme

class DataTable(ctk.CTkFrame):
    def __init__(self, master, columns):
        super().__init__(master, fg_color="transparent")
        
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview", 
                        background=Theme.BG_SECONDARY,
                        foreground=Theme.TEXT_PRIMARY,
                        rowheight=35,
                        fieldbackground=Theme.BG_SECONDARY,
                        borderwidth=0,
                        font=("Helvetica", 11))
                        
        style.configure("Treeview.Heading", 
                        background=Theme.BG_CARD,
                        foreground=Theme.TEXT_SECONDARY,
                        font=("Helvetica", 11, "bold"),
                        borderwidth=0)
                        
        style.map('Treeview', background=[('selected', Theme.PRIMARY)])
        style.map('Treeview.Heading', background=[('active', Theme.BG_CARD)])
        
        self.tree = ttk.Treeview(self, columns=columns, show="headings", style="Treeview")
        
        for col in columns:
            self.tree.heading(col, text=col)
            self.tree.column(col, width=120, anchor="center")
            
        self.tree.grid(row=0, column=0, sticky="nsew")
        
        scrollbar = ctk.CTkScrollbar(self, command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

    def insert(self, values):
        self.tree.insert("", "end", values=values)
        
    def clear(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
            
    def get_selected(self):
        selected = self.tree.selection()
        if selected:
            return self.tree.item(selected[0])['values']
        return None
