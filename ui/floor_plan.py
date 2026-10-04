"""Floor Plan page — shared viewport with Place Mode and room editing."""
from __future__ import annotations

from tkinter import filedialog

import customtkinter as ctk

from components.floorplan_canvas import FloorPlanCanvas
from components.placement_controller import PlacementController
from utils.constants import Theme
from utils.paths import asset_path, resolve_asset_file


class FloorPlanView(ctk.CTkFrame):
    """Same FloorPlanCanvas + Place Mode as 3D Environment — focus on layout editing."""

    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._floor_plans = []
        self._floor_label_to_plan = {}
        self.placement = None

        self.grid_rowconfigure(2, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self._build_title()
        self._build_toolbar()
        self._build_canvas()

        self.placement = PlacementController(
            self.app, self.floorplan, self.place_toolbar_host, status_label=self.hint_label,
        )
        self.after(80, self._load_floor_plan_chrome)

    def _build_title(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 6))

        ctk.CTkLabel(
            header, text="Floor Plan",
            font=ctk.CTkFont(size=24, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Place PIR sensors and cameras, draw rooms, and keep markers synced with Sensors / Cameras.",
            font=ctk.CTkFont(size=13), text_color=Theme.TEXT_SECONDARY,
        ).pack(anchor="w", pady=(4, 0))

    def _build_toolbar(self):
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))

        controls = ctk.CTkFrame(bar, fg_color="transparent")
        controls.pack(side="left")

        self.property_menu = ctk.CTkOptionMenu(
            controls, values=["Home"], width=120, height=32,
            fg_color=Theme.BG_CARD, button_color=Theme.PANEL_LIGHT,
            button_hover_color=Theme.PRIMARY, dropdown_fg_color=Theme.BG_CARD,
            font=ctk.CTkFont(size=12), corner_radius=8,
            command=self._on_property_changed,
        )
        self.property_menu.pack(side="left", padx=(0, 6))

        self.floor_menu = ctk.CTkOptionMenu(
            controls, values=["Floor 1"], width=160, height=32,
            fg_color=Theme.BG_CARD, button_color=Theme.PANEL_LIGHT,
            button_hover_color=Theme.PRIMARY, dropdown_fg_color=Theme.BG_CARD,
            font=ctk.CTkFont(size=12), corner_radius=8,
            command=self._on_floor_changed,
        )
        self.floor_menu.pack(side="left", padx=6)

        self.place_toolbar_host = ctk.CTkFrame(controls, fg_color="transparent")
        self.place_toolbar_host.pack(side="left")

        # Phase 6 — swap the isometric image without leaving this page
        ctk.CTkButton(
            controls, text="Replace Image", width=120, height=32,
            fg_color=Theme.PANEL_LIGHT, hover_color=Theme.PRIMARY,
            font=ctk.CTkFont(size=12), corner_radius=8,
            command=self._replace_floor_image,
        ).pack(side="left", padx=(8, 0))

        legend = ctk.CTkFrame(bar, fg_color="transparent")
        legend.pack(side="left", padx=(16, 0))
        for text, color in (
            ("●  Camera", Theme.PRIMARY),
            ("●  PIR Sensor", Theme.SUCCESS),
        ):
            ctk.CTkLabel(
                legend, text=text, text_color=color,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(side="left", padx=8)

        self.hint_label = ctk.CTkLabel(
            bar,
            text="Drag plan to pan · Drag marker to move · Click marker to edit",
            text_color=Theme.TEXT_MUTED,
            font=ctk.CTkFont(size=10),
        )
        self.hint_label.pack(side="right")

    def _build_canvas(self):
        self.floorplan = FloorPlanCanvas(
            self,
            image_path=asset_path("isometric_base.jpg"),
        )
        self.floorplan.grid(row=2, column=0, sticky="nsew", padx=16, pady=(0, 16))

    def _load_floor_plan_chrome(self):
        dm = getattr(self.app, "device_manager", None)
        if dm is None:
            return

        self._floor_plans = dm.list_floor_plans() or []
        active = dm.get_active_floor_plan()

        props = sorted({(p.get("property_name") or "Home") for p in self._floor_plans}) or ["Home"]
        self.property_menu.configure(values=props)
        active_prop = (active or {}).get("property_name") or props[0]
        if active_prop not in props:
            active_prop = props[0]
        self.property_menu.set(active_prop)
        self._refresh_floor_menu(active_prop, select_plan=active)

        image_path = (active or {}).get("image_path") if active else None
        self.floorplan.load_image(resolve_asset_file(image_path))
        if self.placement:
            self.placement.refresh_from_db()

    def _refresh_floor_menu(self, property_name: str, select_plan=None):
        floors = [
            p for p in self._floor_plans
            if (p.get("property_name") or "Home") == property_name
        ]
        if not floors:
            self.floor_menu.configure(values=["Floor 1"])
            self.floor_menu.set("Floor 1")
            self._floor_label_to_plan = {}
            return

        labels = []
        self._floor_label_to_plan = {}
        for plan in floors:
            label = f"Floor {plan.get('floor_number', 1)}"
            name = plan.get("name")
            if name and name not in label:
                label = f"{label} — {name}"
            base = label
            n = 2
            while label in self._floor_label_to_plan:
                label = f"{base} ({n})"
                n += 1
            labels.append(label)
            self._floor_label_to_plan[label] = plan

        self.floor_menu.configure(values=labels)
        chosen = None
        if select_plan is not None:
            for label, plan in self._floor_label_to_plan.items():
                if plan.get("id") == select_plan.get("id"):
                    chosen = label
                    break
        self.floor_menu.set(chosen or labels[0])

    def _on_property_changed(self, property_name: str):
        self._refresh_floor_menu(property_name)
        self._apply_selected_floor()

    def _on_floor_changed(self, _label: str):
        self._apply_selected_floor()

    def _apply_selected_floor(self):
        plan = self._floor_label_to_plan.get(self.floor_menu.get())
        if not plan:
            return
        dm = getattr(self.app, "device_manager", None)
        if dm is not None:
            dm.set_active_floor_plan(plan["id"])
        self.floorplan.load_image(resolve_asset_file(plan.get("image_path")))
        if self.placement:
            self.placement.refresh_from_db()

    def _replace_floor_image(self):
        # Phase 6 — let the operator pick a new floor-plan picture for the active floor
        plan = self._floor_label_to_plan.get(self.floor_menu.get())
        dm = getattr(self.app, "device_manager", None)
        if plan is None and dm is not None:
            plan = dm.get_active_floor_plan()
        if plan is None or dm is None:
            self.app.notifications.show(
                "Floor Plan", "No active floor plan to update.", type="warning",
            )
            return

        path = filedialog.askopenfilename(
            title="Choose floor plan image",
            filetypes=[
                ("Images", "*.jpg;*.jpeg;*.png;*.webp;*.bmp"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return

        updated = dm.replace_floor_plan_image(plan["id"], path)
        if not updated:
            self.app.notifications.show(
                "Floor Plan", "Could not copy or save the new image.", type="danger",
            )
            return

        # Keep local cache in sync so the next floor switch still has the new path
        for i, p in enumerate(self._floor_plans):
            if p.get("id") == updated.get("id"):
                self._floor_plans[i] = updated
                break
        label = self.floor_menu.get()
        if label in self._floor_label_to_plan:
            self._floor_label_to_plan[label] = updated

        self.floorplan.load_image(resolve_asset_file(updated.get("image_path")))
        if self.placement:
            self.placement.refresh_from_db()
        # Keep 3D Environment in sync when image is swapped here
        env = self.app.views.get("3D Environment")
        if env is not None and hasattr(env, "_load_floor_plan_chrome"):
            env._load_floor_plan_chrome()
        self.app.notifications.show(
            "Floor Plan", "Floor plan image updated.", type="success",
        )

    def on_show(self):
        if self.placement:
            self.placement.refresh_from_db()
