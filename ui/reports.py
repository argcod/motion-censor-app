"""Reports — date-range summary counts and PDF export (Phase 6)."""
from __future__ import annotations

import datetime
from tkinter import filedialog

import customtkinter as ctk
from fpdf import FPDF

from components.cards import KPICard
from components.tables import DataTable
from utils.constants import Theme
from utils.logger import logger


class ReportsView(ctk.CTkFrame):
    """Pick a date range, review totals, and export a PDF summary."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self.logs = []

        self.grid_rowconfigure(3, weight=1)
        self.grid_columnconfigure((0, 1, 2, 3), weight=1)

        self._build_header()
        self._build_filters()
        self._build_summary_cards()
        self._build_table()

        # Default to the last 7 days so the page is useful on first open
        today = datetime.date.today()
        self.start_entry.insert(0, (today - datetime.timedelta(days=6)).isoformat())
        self.end_entry.insert(0, today.isoformat())
        self.after(100, self.refresh)

    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=4, sticky="ew", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            header, text="Reports",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="Date-range summaries and PDF export",
            font=ctk.CTkFont(size=14), text_color=Theme.TEXT_SECONDARY,
        ).pack(side="left", padx=16)

    def _build_filters(self):
        bar = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        bar.grid(row=1, column=0, columnspan=4, sticky="ew", padx=20, pady=(0, 10))

        ctk.CTkLabel(bar, text="From:", text_color=Theme.TEXT_SECONDARY).pack(
            side="left", padx=(16, 4), pady=12,
        )
        self.start_entry = ctk.CTkEntry(bar, width=120, placeholder_text="YYYY-MM-DD")
        self.start_entry.pack(side="left", padx=4)

        ctk.CTkLabel(bar, text="To:", text_color=Theme.TEXT_SECONDARY).pack(
            side="left", padx=(12, 4),
        )
        self.end_entry = ctk.CTkEntry(bar, width=120, placeholder_text="YYYY-MM-DD")
        self.end_entry.pack(side="left", padx=4)

        ctk.CTkButton(
            bar, text="Apply", width=90, fg_color=Theme.PRIMARY, command=self.refresh,
        ).pack(side="left", padx=12)

        ctk.CTkButton(
            bar, text="Last 7 Days", width=100, fg_color=Theme.PANEL_LIGHT,
            command=lambda: self._preset_days(7),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            bar, text="Last 30 Days", width=110, fg_color=Theme.PANEL_LIGHT,
            command=lambda: self._preset_days(30),
        ).pack(side="left", padx=4)

        ctk.CTkButton(
            bar, text="Export PDF", width=120, fg_color=Theme.BORDER, command=self.export_pdf,
        ).pack(side="right", padx=16)

    def _build_summary_cards(self):
        self.total_card = KPICard(self, "Total Events", "0")
        self.total_card.grid(row=2, column=0, sticky="ew", padx=(20, 8), pady=8)

        self.high_card = KPICard(self, "High Risk", "0", value_color=Theme.DANGER)
        self.high_card.grid(row=2, column=1, sticky="ew", padx=8, pady=8)

        self.sensor_card = KPICard(self, "Sensors Hit", "0")
        self.sensor_card.grid(row=2, column=2, sticky="ew", padx=8, pady=8)

        self.loc_card = KPICard(self, "Locations", "0")
        self.loc_card.grid(row=2, column=3, sticky="ew", padx=(8, 20), pady=8)

    def _build_table(self):
        wrap = ctk.CTkFrame(
            self, fg_color=Theme.BG_SECONDARY, corner_radius=10,
            border_width=1, border_color=Theme.BORDER,
        )
        wrap.grid(row=3, column=0, columnspan=4, sticky="nsew", padx=20, pady=(0, 20))
        wrap.grid_rowconfigure(1, weight=1)
        wrap.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            wrap, text="Events in Range",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).grid(row=0, column=0, sticky="w", padx=16, pady=(12, 4))

        columns = ("ID", "Date/Time", "Location", "Sensor", "Risk", "Mobile", "Status")
        self.table = DataTable(wrap, columns=columns)
        self.table.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    def _preset_days(self, days: int):
        today = datetime.date.today()
        self.start_entry.delete(0, "end")
        self.end_entry.delete(0, "end")
        self.start_entry.insert(0, (today - datetime.timedelta(days=days - 1)).isoformat())
        self.end_entry.insert(0, today.isoformat())
        self.refresh()

    def _parse_range(self):
        try:
            start = datetime.date.fromisoformat(self.start_entry.get().strip())
            end = datetime.date.fromisoformat(self.end_entry.get().strip())
        except ValueError:
            self.app.notifications.show(
                "Reports", "Use YYYY-MM-DD dates for From and To.", type="warning",
            )
            return None, None
        if start > end:
            self.app.notifications.show(
                "Reports", "From date must be on or before To date.", type="warning",
            )
            return None, None
        return start.isoformat(), end.isoformat()

    def refresh(self):
        start, end = self._parse_range()
        if start is None:
            return

        summary = self.app.db.get_motion_summary(start, end)
        self.total_card.update_values(value=str(summary["total"]))
        self.high_card.update_values(
            value=str(summary["high_risk"]),
            subtitle=f"Med {summary['medium_risk']} · Low {summary['low_risk']}",
        )
        self.sensor_card.update_values(value=str(summary["sensors"]))
        self.loc_card.update_values(value=str(summary["locations"]))

        self.logs = self.app.db.get_motion_logs_in_range(start, end) or []
        self.table.clear()
        for log in self.logs:
            mobile = "Sent" if log.get("mobile_alert_sent") else "—"
            if log.get("mobile_alert_error"):
                mobile = "Error"
            self.table.insert((
                log.get("id"),
                log.get("detected_at"),
                log.get("location"),
                log.get("sensor_id"),
                log.get("risk_level") or "—",
                mobile,
                log.get("status") or "—",
            ))

    def on_show(self):
        # Reload when the user navigates back so counts stay fresh
        self.refresh()

    def export_pdf(self):
        start, end = self._parse_range()
        if start is None:
            return
        if not self.logs:
            self.app.notifications.show("Reports", "No events in this range to export.", type="warning")
            return

        filepath = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            initialfile=f"smartsecure_report_{start}_to_{end}.pdf",
        )
        if not filepath:
            return

        try:
            summary = self.app.db.get_motion_summary(start, end)
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 16)
            pdf.cell(0, 10, "Smart Motion Detection Alarm System using IoT — Security Report", ln=True, align="C")
            pdf.set_font("Helvetica", size=11)
            pdf.cell(0, 8, f"Range: {start}  to  {end}", ln=True, align="C")
            pdf.ln(6)

            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Summary", ln=True)
            pdf.set_font("Helvetica", size=11)
            pdf.cell(0, 7, f"Total events: {summary['total']}", ln=True)
            pdf.cell(
                0, 7,
                f"Risk — High: {summary['high_risk']}  Medium: {summary['medium_risk']}  Low: {summary['low_risk']}",
                ln=True,
            )
            pdf.cell(
                0, 7,
                f"Distinct sensors: {summary['sensors']}  Locations: {summary['locations']}",
                ln=True,
            )
            pdf.ln(6)

            pdf.set_font("Helvetica", "B", 12)
            pdf.cell(0, 8, "Events", ln=True)
            pdf.set_font("Helvetica", size=9)

            for log in self.logs[:200]:
                line = (
                    f"[{log.get('detected_at')}] {log.get('location')} "
                    f"(Sensor: {log.get('sensor_id')}, Risk: {log.get('risk_level') or '—'})"
                )
                # FPDF latin-1 only — strip characters that would crash export
                safe = line.encode("latin-1", errors="replace").decode("latin-1")
                pdf.multi_cell(0, 5, safe)

            if len(self.logs) > 200:
                pdf.ln(2)
                pdf.cell(0, 6, f"...and {len(self.logs) - 200} more events not listed.", ln=True)

            pdf.output(filepath)
            self.app.notifications.show(
                "Reports", f"PDF saved ({len(self.logs)} events).", type="success",
            )
        except Exception as e:
            logger.error(f"Reports PDF export failed: {e}")
            self.app.notifications.show("Reports", "Failed to save PDF.", type="danger")
