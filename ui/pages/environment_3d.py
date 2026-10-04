"""3D Environment page — Place Mode + live 5-step motion animation."""
from __future__ import annotations

import customtkinter as ctk

from components.active_alert_card import ActiveAlertCard
from components.floorplan_canvas import FloorPlanCanvas
from components.motion_animator import MotionAnimator
from components.placement_controller import PlacementController
from utils.constants import Theme
from utils.paths import asset_path, resolve_asset_file


class Environment3DView(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color="transparent")
        self.app = app
        self._floor_plans = []
        self._property_names = []
        self.placement = None
        self._animator = None
        self._recent_empty = None
        self._wave_job = None

        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=3)
        self.grid_columnconfigure(1, weight=1)

        self.left_container = ctk.CTkFrame(self, fg_color="transparent")
        self.left_container.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        self.left_container.grid_rowconfigure(1, weight=1)
        self.left_container.grid_columnconfigure(0, weight=1)

        self.right_container = ctk.CTkFrame(self, fg_color="transparent", width=320)
        self.right_container.grid(row=0, column=1, sticky="nsew")
        self.right_container.grid_rowconfigure(1, weight=1)
        self.right_container.grid_propagate(False)

        self._build_viewport_header()
        self._build_canvas()
        self._build_timeline()
        self._build_right_panel()

        # Shared Place Mode toolbar (+ PIR / + Camera / Draw Room)
        self.placement = PlacementController(
            self.app, self.floorplan, self.place_toolbar_host, status_label=self.hint_label,
        )
        # Keep animation rings glued to the sensor after pan/zoom
        self.floorplan.bind("<<FloorPlanChanged>>", lambda e: self._on_floorplan_changed())
        self.after(80, self._load_floor_plan_chrome)

    # ── left: header / canvas / timeline ────────────────────────
    def _build_viewport_header(self):
        header = ctk.CTkFrame(self.left_container, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        controls = ctk.CTkFrame(header, fg_color="transparent")
        controls.pack(side="left")

        self.btn_3d = ctk.CTkButton(
            controls, text="◇  3D View", width=110, height=32,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_LIGHT,
            font=ctk.CTkFont(size=12, weight="bold"), corner_radius=8,
        )
        self.btn_3d.pack(side="left", padx=(0, 6))

        # Property / floor menus — single-property data is fine for v1
        self.property_menu = ctk.CTkOptionMenu(
            controls, values=["Home"], width=110, height=32,
            fg_color=Theme.BG_CARD, button_color=Theme.PANEL_LIGHT,
            button_hover_color=Theme.PRIMARY, dropdown_fg_color=Theme.BG_CARD,
            font=ctk.CTkFont(size=12), corner_radius=8,
            command=self._on_property_changed,
        )
        self.property_menu.pack(side="left", padx=6)

        self.floor_menu = ctk.CTkOptionMenu(
            controls, values=["Floor 1"], width=110, height=32,
            fg_color=Theme.BG_CARD, button_color=Theme.PANEL_LIGHT,
            button_hover_color=Theme.PRIMARY, dropdown_fg_color=Theme.BG_CARD,
            font=ctk.CTkFont(size=12), corner_radius=8,
            command=self._on_floor_changed,
        )
        self.floor_menu.pack(side="left", padx=6)

        # Place Mode buttons live here so they sit next to floor selectors
        self.place_toolbar_host = ctk.CTkFrame(controls, fg_color="transparent")
        self.place_toolbar_host.pack(side="left")

        # Simulate runs the same motion pipeline as a real ESP32 hit
        self.btn_simulate = ctk.CTkButton(
            controls, text="Simulate Motion", width=130, height=32,
            fg_color=Theme.DANGER, hover_color=Theme.DANGER_LIGHT,
            font=ctk.CTkFont(size=12, weight="bold"), corner_radius=8,
            command=self._on_simulate_clicked,
        )
        self.btn_simulate.pack(side="left", padx=8)

        # Legend (matches mockup)
        legend = ctk.CTkFrame(header, fg_color="transparent")
        legend.pack(side="left", padx=(12, 0))

        for text, color in (
            ("●  Camera", Theme.PRIMARY),
            ("●  PIR Sensor", Theme.SUCCESS),
            ("●  Motion Zone", Theme.DANGER_LIGHT),
            ("●  Active Event", Theme.DANGER),
        ):
            ctk.CTkLabel(
                legend, text=text, text_color=color,
                font=ctk.CTkFont(size=11, weight="bold"),
            ).pack(side="left", padx=6)

        self.hint_label = ctk.CTkLabel(
            header,
            text="Drag plan to pan · Drag marker to move · Click marker to edit",
            text_color=Theme.TEXT_MUTED,
            font=ctk.CTkFont(size=10),
        )
        self.hint_label.pack(side="right")

    def _build_canvas(self):
        self.floorplan = FloorPlanCanvas(
            self.left_container,
            image_path=asset_path("isometric_base.jpg"),
        )
        self.floorplan.grid(row=1, column=0, sticky="nsew")

        self._animator = MotionAnimator(
            self.floorplan,
            self,
            on_stage=self.set_timeline_stage,
            on_complete=self._on_animation_complete,
        )

    def _load_floor_plan_chrome(self):
        """Fill property/floor menus from DB and show the active plan image."""
        dm = getattr(self.app, "device_manager", None)
        if dm is None:
            return

        self._floor_plans = dm.list_floor_plans() or []
        active = dm.get_active_floor_plan()

        props = sorted({(p.get("property_name") or "Home") for p in self._floor_plans}) or ["Home"]
        self._property_names = props
        self.property_menu.configure(values=props)

        active_prop = (active or {}).get("property_name") or props[0]
        if active_prop not in props:
            active_prop = props[0]
        self.property_menu.set(active_prop)
        self._refresh_floor_menu(active_prop, select_plan=active)

        image_path = (active or {}).get("image_path") if active else None
        # Phase 6 — resolve relative assets/ paths after image replace
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
            return

        labels = []
        self._floor_label_to_plan = {}
        for plan in floors:
            label = f"Floor {plan.get('floor_number', 1)}"
            name = plan.get("name")
            if name and name not in label:
                label = f"{label} — {name}"
            # Keep labels unique if two floors share a number
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
        plan = getattr(self, "_floor_label_to_plan", {}).get(self.floor_menu.get())
        if not plan:
            return
        dm = getattr(self.app, "device_manager", None)
        if dm is not None:
            dm.set_active_floor_plan(plan["id"])
        self.floorplan.load_image(resolve_asset_file(plan.get("image_path")))
        if self.placement:
            self.placement.refresh_from_db()

    def on_show(self):
        # Refresh markers when navigating back so Sensors/Cameras edits show up
        if self.placement:
            self.placement.refresh_from_db()

    def _on_floorplan_changed(self):
        if self._animator and self._animator.active:
            self._animator.refresh()

    def _build_timeline(self):
        self.timeline_frame = ctk.CTkFrame(
            self.left_container, height=148,
            fg_color=Theme.BG_CARD, corner_radius=12,
            border_width=1, border_color=Theme.BORDER,
        )
        self.timeline_frame.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.timeline_frame.pack_propagate(False)

        title_row = ctk.CTkFrame(self.timeline_frame, fg_color="transparent")
        title_row.pack(fill="x", padx=16, pady=(10, 4))

        ctk.CTkLabel(
            title_row,
            text="Motion Detection Animation",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(side="left")

        self.timeline_subtitle = ctk.CTkLabel(
            title_row,
            text="— Idle · waiting for motion",
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_MUTED,
        )
        self.timeline_subtitle.pack(side="left", padx=8)

        stages_row = ctk.CTkFrame(self.timeline_frame, fg_color="transparent")
        stages_row.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        stages = [
            ("1", "Sensor Triggered", "PIR detects motion"),
            ("2", "Motion Pulse", "Sensor node activates"),
            ("3", "Expanding Wave", "Detection zone grows"),
            ("4", "Room Highlight", "Affected zone identified"),
            ("5", "Event Complete", "3D animation finished"),
        ]

        self.stage_frames = []
        self.stage_labels = []
        for i, (num, title, sub) in enumerate(stages):
            card = ctk.CTkFrame(
                stages_row, fg_color=Theme.BG_PRIMARY, corner_radius=8,
                border_width=1, border_color=Theme.BORDER,
            )
            card.pack(side="left", fill="both", expand=True, padx=4)

            ctk.CTkLabel(
                card, text=num, font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Theme.PRIMARY,
            ).pack(anchor="w", padx=10, pady=(8, 0))
            title_lbl = ctk.CTkLabel(
                card, text=title, font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Theme.TEXT_PRIMARY,
            )
            title_lbl.pack(anchor="w", padx=10)
            ctk.CTkLabel(
                card, text=sub, font=ctk.CTkFont(size=10),
                text_color=Theme.TEXT_MUTED,
            ).pack(anchor="w", padx=10, pady=(0, 8))

            self.stage_frames.append(card)
            self.stage_labels.append(title_lbl)

            if i < len(stages) - 1:
                ctk.CTkLabel(
                    stages_row, text="→", text_color=Theme.PRIMARY,
                    font=ctk.CTkFont(size=16, weight="bold"),
                ).pack(side="left", padx=2)

    def set_timeline_stage(self, stage_idx: int):
        """Highlight timeline stage (−1 clears). Driven by MotionAnimator."""
        for i, frame in enumerate(self.stage_frames):
            active = i == stage_idx
            frame.configure(
                border_color=Theme.CYAN_GLOW if active else Theme.BORDER,
                fg_color=Theme.PANEL_LIGHT if active else Theme.BG_PRIMARY,
            )
            if i < len(self.stage_labels):
                self.stage_labels[i].configure(
                    text_color=Theme.CYAN_GLOW if active else Theme.TEXT_PRIMARY
                )
        if stage_idx >= 0:
            self.timeline_subtitle.configure(
                text="— 3D Motion Visualization in Progress...",
                text_color=Theme.DANGER_LIGHT,
            )
            self._set_waveform_active(True)
        else:
            self.timeline_subtitle.configure(
                text="— Idle · waiting for motion",
                text_color=Theme.TEXT_MUTED,
            )

    # ── right panel ─────────────────────────────────────────────
    def _build_right_panel(self):
        # Pass app so the card can show snapshot/live thumbs and open details
        self.alert_card = ActiveAlertCard(
            self.right_container,
            app=self.app,
            on_details=self._open_alert_details,
        )
        self.alert_card.grid(row=0, column=0, sticky="ew", pady=(0, 12))

        recent_wrap = ctk.CTkFrame(self.right_container, fg_color="transparent")
        recent_wrap.grid(row=1, column=0, sticky="nsew")
        recent_wrap.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            recent_wrap, text="Recent Events",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 8))

        self.recent_list = ctk.CTkScrollableFrame(
            recent_wrap, fg_color="transparent", height=180,
        )
        self.recent_list.pack(fill="both", expand=True)

        self._recent_empty = ctk.CTkFrame(
            self.recent_list, fg_color=Theme.BG_CARD, corner_radius=8, height=56,
        )
        self._recent_empty.pack(fill="x", pady=3)
        self._recent_empty.pack_propagate(False)
        ctk.CTkLabel(
            self._recent_empty, text="No recent events yet",
            text_color=Theme.TEXT_MUTED, font=ctk.CTkFont(size=11),
        ).pack(expand=True)

        self.wave_card = ctk.CTkFrame(
            self.right_container, height=64, fg_color=Theme.PANEL,
            corner_radius=10, border_width=1, border_color=Theme.BORDER,
        )
        self.wave_card.grid(row=2, column=0, sticky="ew", pady=(10, 0))
        self.wave_card.pack_propagate(False)

        self.wave_label = ctk.CTkLabel(
            self.wave_card,
            text="◐  System idle — monitoring for motion…",
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT_SECONDARY,
        )
        self.wave_label.pack(anchor="w", padx=14, pady=(12, 2))

        self.wave_bar = ctk.CTkProgressBar(
            self.wave_card, height=4, progress_color=Theme.PRIMARY,
            fg_color=Theme.BG_PRIMARY,
        )
        self.wave_bar.pack(fill="x", padx=14, pady=(0, 12))
        self.wave_bar.set(0.08)

    def _open_alert_details(self, event):
        if not event:
            self.app.notifications.show(
                "No Event", "Wait for a motion event first.", type="info",
            )
            return
        if hasattr(self.app, "open_event_details"):
            self.app.open_event_details(event)

    def _on_simulate_clicked(self):
        # Default to first PIR / Sensor01 so demos work without picking a card
        uid = "Sensor01"
        dm = getattr(self.app, "device_manager", None)
        if dm is not None:
            pirs = dm.list_all_devices(device_type="pir") or []
            if pirs:
                uid = pirs[0].get("device_uid") or uid
        if hasattr(self.app, "motion_manager"):
            self.app.motion_manager.simulate(uid)

    def trigger_motion_animation(self, event_or_location, sensor_id=None, event=None):
        """Start the 5-step canvas animation + Active Alert update.

        Accepts either a rich event dict (Phase 3) or legacy (location, sensor_id).
        """
        if isinstance(event_or_location, dict):
            event = event_or_location
        elif event is None:
            event = {
                "location": event_or_location,
                "sensor_id": sensor_id,
                "x_norm": 0.35,
                "y_norm": 0.45,
                "risk_level": "—",
                "camera_uid": None,
                "detected_at": "Just now",
                "room_points": [],
            }

        # Resolve coords from DeviceManager if the event did not include them
        x_norm = event.get("x_norm")
        y_norm = event.get("y_norm")
        room_points = list(event.get("room_points") or [])
        sensor_id = event.get("sensor_id")
        if (x_norm is None or y_norm is None) and sensor_id:
            dm = getattr(self.app, "device_manager", None)
            device = dm.get_device(sensor_id) if dm else None
            if device:
                x_norm = device.get("x_norm", 0.5)
                y_norm = device.get("y_norm", 0.5)
                if not room_points and device.get("room_id"):
                    room = dm.get_room(device["room_id"])
                    room_points = dm.parse_room_polygon(room) if room else []
        x_norm = 0.5 if x_norm is None else float(x_norm)
        y_norm = 0.5 if y_norm is None else float(y_norm)

        location = event.get("location") or "Unknown"
        label = f"Motion Detected: {location} - {sensor_id or '?'}"

        self.alert_card.update_event(event)
        self.add_recent_event(event)
        self._set_waveform_active(True)
        self.wave_label.configure(text=label, text_color=Theme.DANGER_LIGHT)

        if self._animator:
            self._animator.play(
                x_norm, y_norm, label=label, room_points=room_points,
            )

    def add_recent_event(self, event: dict):
        if self._recent_empty is not None:
            self._recent_empty.destroy()
            self._recent_empty = None

        when = event.get("detected_at") or ""
        if " " in str(when):
            when = str(when).split(" ")[-1]
        loc = event.get("location") or "—"
        sid = event.get("sensor_id") or "—"
        risk = event.get("risk_level") or ""

        row = ctk.CTkFrame(self.recent_list, fg_color=Theme.BG_CARD, corner_radius=8)
        row.pack(fill="x", pady=3)
        ctk.CTkLabel(
            row, text=str(when), width=70, anchor="w",
            text_color=Theme.TEXT_MUTED, font=ctk.CTkFont(size=10),
        ).pack(side="left", padx=(10, 4), pady=8)
        ctk.CTkLabel(
            row, text=f"{loc} · {sid}", anchor="w",
            text_color=Theme.TEXT_PRIMARY, font=ctk.CTkFont(size=11, weight="bold"),
        ).pack(side="left", padx=4, pady=8)
        if risk:
            ctk.CTkLabel(
                row, text=str(risk), anchor="e",
                text_color=Theme.DANGER_LIGHT, font=ctk.CTkFont(size=10, weight="bold"),
            ).pack(side="right", padx=10, pady=8)

        children = self.recent_list.winfo_children()
        if len(children) > 12:
            children[0].destroy()

    def _set_waveform_active(self, active: bool):
        if self._wave_job is not None:
            try:
                self.after_cancel(self._wave_job)
            except Exception:
                pass
            self._wave_job = None

        if not active:
            self.wave_bar.configure(progress_color=Theme.PRIMARY)
            self.wave_bar.set(0.08)
            self.wave_label.configure(
                text="◐  System idle — monitoring for motion…",
                text_color=Theme.TEXT_SECONDARY,
            )
            return

        self.wave_bar.configure(progress_color=Theme.DANGER)
        self._pulse_wave(0.2)

    def _pulse_wave(self, value: float):
        # Simple bouncing progress bar while an event is animating
        if self._animator is None or not self._animator.active:
            return
        nxt = value + 0.12
        if nxt > 0.95:
            nxt = 0.2
        self.wave_bar.set(nxt)
        self._wave_job = self.after(120, lambda: self._pulse_wave(nxt))

    def _on_animation_complete(self):
        self._set_waveform_active(False)
