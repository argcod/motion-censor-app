import customtkinter as ctk
import pandas as pd
from fpdf import FPDF
from tkinter import filedialog
from components.tables import DataTable
from utils.constants import Theme
from utils.logger import logger


class HistoryView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # Header
        header_frame = ctk.CTkFrame(self, fg_color="transparent")
        header_frame.grid(row=0, column=0, sticky="ew", padx=20, pady=(20, 10))

        title = ctk.CTkLabel(
            header_frame, text="Security Events",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        )
        title.pack(side="left")

        # Toolbar
        toolbar = ctk.CTkFrame(self, fg_color=Theme.BG_CARD, corner_radius=8, height=50)
        toolbar.grid(row=1, column=0, sticky="ew", padx=20, pady=10)

        self.refresh_btn = ctk.CTkButton(
            toolbar, text="Refresh Data", fg_color=Theme.PRIMARY,
            text_color=Theme.BG_PRIMARY, command=self.load_data,
        )
        self.refresh_btn.pack(side="left", padx=10, pady=10)

        self.pdf_btn = ctk.CTkButton(toolbar, text="Export PDF", fg_color=Theme.BORDER, command=self.export_pdf)
        self.pdf_btn.pack(side="right", padx=10, pady=10)

        self.csv_btn = ctk.CTkButton(toolbar, text="Export CSV", fg_color=Theme.BORDER, command=self.export_csv)
        self.csv_btn.pack(side="right", padx=10, pady=10)

        self.mark_unread_btn = ctk.CTkButton(
            toolbar, text="Mark Unread", fg_color=Theme.BORDER, command=self.mark_unread,
        )
        self.mark_unread_btn.pack(side="right", padx=10, pady=10)

        self.mark_read_btn = ctk.CTkButton(
            toolbar, text="Mark Read", fg_color=Theme.BORDER, command=self.mark_read,
        )
        self.mark_read_btn.pack(side="right", padx=10, pady=10)

        self.view_btn = ctk.CTkButton(
            toolbar, text="View Details", fg_color=Theme.BORDER, command=self.view_details,
        )
        self.view_btn.pack(side="right", padx=10, pady=10)

        # Table — Read column drives the sidebar/bell badge workflow
        columns = ("ID", "Date/Time", "Location", "Sensor ID", "Camera", "Risk", "Read", "Status")
        self.table = DataTable(self, columns=columns)
        self.table.grid(row=2, column=0, sticky="nsew", padx=20, pady=(0, 20))

        self.logs = []

    def _is_read(self, log) -> bool:
        value = log.get("is_read")
        if isinstance(value, (bytes, bytearray)):
            return bool(value and value[0])
        return value in (True, 1, "1", "true", "True")

    def load_data(self):
        self.table.clear()
        self.logs = self.app.db.get_motion_logs(limit=500) or []
        for log in self.logs:
            cam_id = log.get("camera_uid") or "N/A"
            read_label = "Yes" if self._is_read(log) else "No"
            self.table.insert((
                log["id"],
                log["detected_at"],
                log["location"],
                log["sensor_id"],
                cam_id,
                log.get("risk_level") or "—",
                read_label,
                log["status"],
            ))

    def _selected_log(self):
        selected = self.table.get_selected()
        if not selected:
            self.app.notifications.show(
                "Selection Required", "Please select an event first.", type="warning",
            )
            return None
        log_id = selected[0]
        return next((l for l in self.logs if l["id"] == log_id), None)

    def _set_read_state(self, is_read: bool):
        full_log = self._selected_log()
        if not full_log:
            return
        self.app.db.mark_motion_read(full_log["id"], is_read)
        if hasattr(self.app, "refresh_unread_badges"):
            self.app.refresh_unread_badges()
        self.load_data()

    def mark_read(self):
        self._set_read_state(True)

    def mark_unread(self):
        self._set_read_state(False)

    def export_csv(self):
        if not self.logs:
            self.app.notifications.show("Export Error", "No data to export.", type="warning")
            return

        filepath = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV Files", "*.csv")])
        if filepath:
            try:
                df = pd.DataFrame(self.logs)
                df.to_csv(filepath, index=False)
                self.app.notifications.show(
                    "Export Success", f"Saved {len(self.logs)} records to CSV.", type="success",
                )
            except Exception as e:
                logger.error(f"CSV Export error: {e}")
                self.app.notifications.show("Export Error", "Failed to save CSV file.", type="danger")

    def export_pdf(self):
        if not self.logs:
            self.app.notifications.show("Export Error", "No data to export.", type="warning")
            return

        filepath = filedialog.asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Files", "*.pdf")])
        if filepath:
            try:
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font("Arial", size=12)
                pdf.cell(200, 10, txt="Smart Motion Detection Alarm System using IoT — Event Logs", ln=True, align="C")
                pdf.ln(10)

                for log in self.logs[:100]:
                    cam_id = log.get("camera_uid") or "N/A"
                    pdf.cell(
                        200, 10,
                        txt=f"[{log['detected_at']}] {log['location']} (Sensor: {log['sensor_id']}, Cam: {cam_id})",
                        ln=True,
                    )

                pdf.output(filepath)
                self.app.notifications.show("Export Success", "Saved PDF report.", type="success")
            except Exception as e:
                logger.error(f"PDF Export error: {e}")
                self.app.notifications.show("Export Error", "Failed to save PDF file.", type="danger")

    def view_details(self):
        full_log = self._selected_log()
        if not full_log:
            return
        if hasattr(self.app, "open_event_details"):
            self.app.open_event_details(full_log, on_changed=self.load_data)
        else:
            from components.event_details_modal import EventDetailsModal
            EventDetailsModal(self, full_log, app=self.app, on_changed=self.load_data)
