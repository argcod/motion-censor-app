import customtkinter as ctk
from utils.constants import Theme


class AISecurityView(ctk.CTkFrame):
    """Dedicated stub — AI person detection is intentionally out of scope for v1."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        card = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=12,
            border_width=1, border_color=Theme.BORDER,
        )
        card.grid(row=0, column=0, sticky="nsew", padx=24, pady=24)

        ctk.CTkLabel(
            card, text="AI Security",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", padx=28, pady=(28, 8))

        ctk.CTkLabel(
            card,
            text="AI person detection is planned for a later release and is disabled in v1.",
            font=ctk.CTkFont(size=14), text_color=Theme.TEXT_SECONDARY,
            wraplength=560, justify="left",
        ).pack(anchor="w", padx=28, pady=(0, 8))

        ctk.CTkLabel(
            card,
            text="This page is a placeholder so the sidebar route is real — not a Command Center clone.",
            font=ctk.CTkFont(size=13), text_color=Theme.TEXT_MUTED,
            wraplength=560, justify="left",
        ).pack(anchor="w", padx=28, pady=(0, 28))
