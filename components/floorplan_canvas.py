"""Interactive isometric floor-plan canvas with zoom, pan, Place Mode, and room edit."""
from __future__ import annotations

import tkinter as tk
from pathlib import Path
from typing import Callable, Optional

import customtkinter as ctk
from PIL import Image, ImageTk

from utils.constants import Theme
from utils.logger import logger
from utils.paths import PROJECT_ROOT, asset_path, path_str


class FloorPlanCanvas(ctk.CTkFrame):
    """Tk Canvas wrapper that letterboxes a floor-plan image and supports zoom/pan."""

    MIN_ZOOM = 0.4
    MAX_ZOOM = 4.0
    ZOOM_STEP = 1.15
    HIT_RADIUS = 14

    MODE_VIEW = "view"
    MODE_PLACE_PIR = "place_pir"
    MODE_PLACE_CAMERA = "place_camera"
    MODE_EDIT_ROOM = "edit_room"

    def __init__(
        self,
        master,
        image_path: Optional[Path] = None,
        on_click: Optional[Callable[[float, float], None]] = None,
        show_controls: bool = True,
        **kwargs,
    ):
        super().__init__(
            master,
            fg_color=Theme.BG_PRIMARY,
            corner_radius=15,
            border_width=1,
            border_color=Theme.BORDER,
            **kwargs,
        )
        self.on_click = on_click
        self.image_path = Path(image_path) if image_path else asset_path("isometric_base.jpg")
        self.show_controls = show_controls

        # Place Mode callbacks — pages wire these to DeviceManager
        self.on_place: Optional[Callable[[str, float, float], None]] = None
        self.on_device_moved: Optional[Callable[[str, float, float], None]] = None
        self.on_device_selected: Optional[Callable[[str], None]] = None
        self.on_room_complete: Optional[Callable[[list], None]] = None
        self.on_mode_changed: Optional[Callable[[str], None]] = None

        self._mode = self.MODE_VIEW
        self._devices: list[dict] = []
        self._rooms: list[dict] = []
        self._selected_uid: Optional[str] = None
        self._room_draft: list[tuple[float, float]] = []

        self._pil_image: Optional[Image.Image] = None
        self._photo: Optional[ImageTk.PhotoImage] = None
        self._bg_id: Optional[int] = None
        self._placeholder_id: Optional[int] = None

        # Image placement in canvas coords (letterboxed base fit * zoom + pan)
        self._base_scale = 1.0
        self._zoom = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._img_w = 0
        self._img_h = 0
        self._display_w = 0
        self._display_h = 0

        self._drag_last = None
        self._drag_moved = False
        self._dragging_uid: Optional[str] = None
        self._fullscreen_win: Optional[tk.Toplevel] = None
        self._missing_overlay: Optional[ctk.CTkFrame] = None
        self._compass_ids: list[int] = []

        self.canvas = tk.Canvas(self, bg=Theme.BG_PRIMARY, highlightthickness=0, cursor="fleur")
        self.canvas.pack(fill="both", expand=True, padx=2, pady=2)

        self._build_overlays()
        self._bind_events()
        self.load_image(self.image_path)
        # First paint after layout so letterbox uses real widget size
        self.after(50, self._on_resize)

    # ── public API ──────────────────────────────────────────────
    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str):
        # Switch place/edit tools; Escape from the page usually returns to view
        if mode not in (
            self.MODE_VIEW,
            self.MODE_PLACE_PIR,
            self.MODE_PLACE_CAMERA,
            self.MODE_EDIT_ROOM,
        ):
            mode = self.MODE_VIEW
        self._mode = mode
        if mode != self.MODE_EDIT_ROOM:
            self._room_draft = []
        self._update_cursor()
        self._redraw_overlays()
        if self.on_mode_changed:
            self.on_mode_changed(mode)

    def set_devices(self, devices: list[dict]):
        # Markers come from DeviceManager — no more hardcoded demo pins
        self._devices = list(devices or [])
        self._redraw_overlays()

    def set_rooms(self, rooms: list[dict]):
        self._rooms = list(rooms or [])
        self._redraw_overlays()

    def set_selected_uid(self, device_uid: Optional[str]):
        self._selected_uid = device_uid
        self._redraw_overlays()

    def clear_room_draft(self):
        self._room_draft = []
        self._redraw_overlays()

    def finish_room_draft(self):
        # Close the polygon when the user is done clicking points
        if len(self._room_draft) < 3:
            return False
        points = list(self._room_draft)
        self._room_draft = []
        self._redraw_overlays()
        if self.on_room_complete:
            self.on_room_complete(points)
        return True

    @staticmethod
    def resolve_image_path(raw: Path | str | None) -> Path:
        """Turn a DB or relative path into an absolute file path under the project when needed."""
        if raw is None or str(raw).strip() == "":
            return asset_path("isometric_base.jpg")
        path = Path(str(raw))
        if path.is_file():
            return path
        # Seeded paths may be absolute from another machine — fall back to filename under assets/
        candidate = asset_path(path.name)
        if candidate.is_file():
            return candidate
        under_root = PROJECT_ROOT / path
        if under_root.is_file():
            return under_root
        return path

    def has_image(self) -> bool:
        return self._pil_image is not None

    def load_image(self, path: Path | str | None) -> bool:
        path = self.resolve_image_path(path)
        self.image_path = path
        self._pil_image = None
        self._photo = None
        self._hide_missing_overlay()

        if not path.exists():
            logger.warning(f"Floor plan image missing: {path}")
            self._show_placeholder()
            return False

        try:
            self._pil_image = Image.open(path).convert("RGB")
            self._img_w, self._img_h = self._pil_image.size
            self._zoom = 1.0
            self._offset_x = 0.0
            self._offset_y = 0.0
            self._fit_and_center(keep_pan=False)
            self._redraw_image()
            self._redraw_fixed_overlays()
            self._redraw_overlays()
            self._update_zoom_label()
            logger.info(f"Loaded floor plan: {path} ({self._img_w}x{self._img_h})")
            return True
        except Exception as e:
            logger.error(f"Failed to load floor plan: {e}")
            self._show_placeholder()
            return False

    def reload(self) -> bool:
        # Retry after user drops isometric_base.jpg into assets/
        return self.load_image(self.image_path)

    def set_zoom(self, zoom: float, anchor_canvas=None):
        if self._pil_image is None:
            return
        zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, zoom))
        if abs(zoom - self._zoom) < 1e-6:
            return

        if anchor_canvas is None:
            cw = max(self.canvas.winfo_width(), 1)
            ch = max(self.canvas.winfo_height(), 1)
            ax, ay = cw / 2, ch / 2
        else:
            ax, ay = anchor_canvas

        # Keep world point under cursor stable while zooming
        wx = (ax - self._offset_x) / max(self._zoom, 1e-6)
        wy = (ay - self._offset_y) / max(self._zoom, 1e-6)
        self._zoom = zoom
        self._offset_x = ax - wx * self._zoom
        self._offset_y = ay - wy * self._zoom
        self._clamp_pan()
        self._redraw_image()
        self._redraw_fixed_overlays()
        self._redraw_overlays()
        self._update_zoom_label()

    def zoom_in(self):
        self.set_zoom(self._zoom * self.ZOOM_STEP)

    def zoom_out(self):
        self.set_zoom(self._zoom / self.ZOOM_STEP)

    def reset_view(self):
        self._zoom = 1.0
        self._offset_x = 0.0
        self._offset_y = 0.0
        self._fit_and_center(keep_pan=False)
        self._redraw_image()
        self._redraw_fixed_overlays()
        self._redraw_overlays()
        self._update_zoom_label()

    def canvas_to_norm(self, canvas_x: float, canvas_y: float) -> tuple[float, float]:
        """Convert canvas pixel → normalized 0..1 image coords."""
        if self._display_w <= 0 or self._display_h <= 0:
            return 0.5, 0.5
        ix = (canvas_x - self._offset_x) / self._display_w
        iy = (canvas_y - self._offset_y) / self._display_h
        return max(0.0, min(1.0, ix)), max(0.0, min(1.0, iy))

    def norm_to_canvas(self, nx: float, ny: float) -> tuple[float, float]:
        """Convert normalized 0..1 image coords → canvas pixel."""
        return (
            self._offset_x + nx * self._display_w,
            self._offset_y + ny * self._display_h,
        )

    def toggle_fullscreen(self):
        if self._fullscreen_win and self._fullscreen_win.winfo_exists():
            self._exit_fullscreen()
            return
        self._enter_fullscreen()

    def get_canvas(self) -> tk.Canvas:
        return self.canvas

    def center_on_norm(self, nx: float, ny: float, target_zoom: float | None = None):
        """Pan (and optionally zoom) so a normalized point sits near the viewport center."""
        if self._pil_image is None:
            return
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        if target_zoom is not None:
            self._zoom = max(self.MIN_ZOOM, min(self.MAX_ZOOM, float(target_zoom)))
        # Keep current zoom unless the sensor is tiny / far off-screen
        self._display_w = max(1, int(self._img_w * self._base_scale * self._zoom))
        self._display_h = max(1, int(self._img_h * self._base_scale * self._zoom))
        self._offset_x = cw / 2 - float(nx) * self._display_w
        self._offset_y = ch / 2 - float(ny) * self._display_h
        self._clamp_pan()
        self._redraw_image()
        self._redraw_fixed_overlays()
        self._redraw_overlays()
        self._update_zoom_label()

    def clear_motion_fx(self):
        # MotionAnimator draws under this tag; pan/zoom redraw leaves it alone
        self.canvas.delete("motion_fx")

    # ── internals ───────────────────────────────────────────────
    def _update_cursor(self):
        if self._mode in (self.MODE_PLACE_PIR, self.MODE_PLACE_CAMERA, self.MODE_EDIT_ROOM):
            self.canvas.configure(cursor="crosshair")
        else:
            self.canvas.configure(cursor="fleur")

    def _build_overlays(self):
        if not self.show_controls:
            self.zoom_label = None
            return

        # Zoom / reset / fullscreen stack (bottom-right)
        controls = ctk.CTkFrame(
            self, fg_color=Theme.PANEL_LIGHT, corner_radius=12,
            border_width=1, border_color=Theme.BORDER,
        )
        controls.place(relx=0.98, rely=0.94, anchor="se")

        self.zoom_label = ctk.CTkLabel(
            controls, text="100%", width=42, height=22,
            text_color=Theme.TEXT_SECONDARY, font=ctk.CTkFont(size=10, weight="bold"),
        )
        self.zoom_label.pack(padx=6, pady=(6, 2))

        self.btn_plus = ctk.CTkButton(
            controls, text="+", width=34, height=34, corner_radius=8,
            fg_color=Theme.BG_CARD, hover_color=Theme.PRIMARY,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.zoom_in,
        )
        self.btn_plus.pack(padx=6, pady=3)

        self.btn_minus = ctk.CTkButton(
            controls, text="−", width=34, height=34, corner_radius=8,
            fg_color=Theme.BG_CARD, hover_color=Theme.PRIMARY,
            font=ctk.CTkFont(size=16, weight="bold"),
            command=self.zoom_out,
        )
        self.btn_minus.pack(padx=6, pady=3)

        self.btn_reset = ctk.CTkButton(
            controls, text="⌂", width=34, height=34, corner_radius=8,
            fg_color=Theme.BG_CARD, hover_color=Theme.PRIMARY,
            font=ctk.CTkFont(size=14),
            command=self.reset_view,
        )
        self.btn_reset.pack(padx=6, pady=3)

        self.btn_fs = ctk.CTkButton(
            controls, text="⛶", width=34, height=34, corner_radius=8,
            fg_color=Theme.BG_CARD, hover_color=Theme.PRIMARY,
            font=ctk.CTkFont(size=14),
            command=self.toggle_fullscreen,
        )
        self.btn_fs.pack(padx=6, pady=(3, 6))

    def _update_zoom_label(self):
        if self.zoom_label is None:
            return
        pct = int(round(self._zoom * 100))
        self.zoom_label.configure(text=f"{pct}%")

    def _bind_events(self):
        self.canvas.bind("<Configure>", self._on_resize)
        self.canvas.bind("<ButtonPress-1>", self._on_press)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_release)
        self.canvas.bind("<MouseWheel>", self._on_wheel)  # Windows
        self.canvas.bind("<Button-4>", lambda e: self._on_wheel_linux(e, 1))
        self.canvas.bind("<Button-5>", lambda e: self._on_wheel_linux(e, -1))
        self.canvas.bind("<Double-Button-1>", self._on_double_click)
        self.canvas.bind("<Button-3>", self._on_right_click)
        # Escape drops Place Mode so users are not stuck in crosshair cursor
        self.canvas.bind("<Escape>", lambda e: self.set_mode(self.MODE_VIEW))
        self.canvas.focus_set()

    def _on_resize(self, event=None):
        if self._pil_image is None:
            self._show_placeholder()
            return
        self._fit_and_center(keep_pan=True)
        self._clamp_pan()
        self._redraw_image()
        self._redraw_fixed_overlays()
        self._redraw_overlays()

    def _fit_and_center(self, keep_pan: bool = False):
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        if self._img_w <= 0 or self._img_h <= 0:
            return
        if cw < 10 or ch < 10:
            return

        # Letterbox so the full image fits at zoom=1 with a small margin
        self._base_scale = min(cw / self._img_w, ch / self._img_h) * 0.96
        fit_w = self._img_w * self._base_scale
        fit_h = self._img_h * self._base_scale

        # Re-center when fit-zoom so resize keeps the plan framed; keep pan when zoomed in
        if not keep_pan or abs(self._zoom - 1.0) < 1e-6:
            self._offset_x = (cw - fit_w * self._zoom) / 2
            self._offset_y = (ch - fit_h * self._zoom) / 2

    def _clamp_pan(self):
        """Keep at least part of the plan visible after drag/zoom."""
        if self._pil_image is None:
            return
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        dw = max(1, int(self._img_w * self._base_scale * self._zoom))
        dh = max(1, int(self._img_h * self._base_scale * self._zoom))
        margin = 80
        self._offset_x = max(margin - dw, min(cw - margin, self._offset_x))
        self._offset_y = max(margin - dh, min(ch - margin, self._offset_y))

    def _redraw_image(self):
        if self._pil_image is None:
            return

        self._display_w = max(1, int(self._img_w * self._base_scale * self._zoom))
        self._display_h = max(1, int(self._img_h * self._base_scale * self._zoom))

        # Cap render size for performance while zoomed far in
        max_dim = 3500
        render_w, render_h = self._display_w, self._display_h
        if render_w > max_dim or render_h > max_dim:
            ratio = min(max_dim / render_w, max_dim / render_h)
            render_w = max(1, int(render_w * ratio))
            render_h = max(1, int(render_h * ratio))

        resized = self._pil_image.resize((render_w, render_h), Image.Resampling.LANCZOS)
        if (render_w, render_h) != (self._display_w, self._display_h):
            resized = resized.resize((self._display_w, self._display_h), Image.Resampling.BILINEAR)

        self._photo = ImageTk.PhotoImage(resized)
        if self._bg_id is None:
            self._bg_id = self.canvas.create_image(
                self._offset_x, self._offset_y, image=self._photo, anchor="nw", tags=("floorplan",)
            )
        else:
            self.canvas.itemconfigure(self._bg_id, image=self._photo)
            self.canvas.coords(self._bg_id, self._offset_x, self._offset_y)

        if self._placeholder_id:
            self.canvas.delete(self._placeholder_id)
            self._placeholder_id = None

        self.canvas.tag_lower("floorplan")
        # Tell parent pages to redraw any extra chrome after pan/zoom/resize
        self.event_generate("<<FloorPlanChanged>>", when="tail")

    def _hide_missing_overlay(self):
        if self._missing_overlay is not None:
            self._missing_overlay.destroy()
            self._missing_overlay = None

    def _show_placeholder(self):
        self.canvas.delete("all")
        self._bg_id = None
        self._compass_ids = []
        self._pil_image = None
        self._display_w = 0
        self._display_h = 0

        expected = path_str(asset_path("isometric_base.jpg"))
        tried = path_str(self.image_path)

        self._hide_missing_overlay()
        overlay = ctk.CTkFrame(
            self, fg_color=Theme.BG_CARD, corner_radius=14,
            border_width=1, border_color=Theme.BORDER,
        )
        overlay.place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            overlay, text="Floor plan image not found",
            font=ctk.CTkFont(size=16, weight="bold"), text_color=Theme.TEXT_PRIMARY,
        ).pack(padx=28, pady=(22, 6))

        ctk.CTkLabel(
            overlay,
            text=(
                "Add an isometric floor-plan JPG so the viewport can load.\n"
                "Put the file here (or fix the path in Settings later):"
            ),
            font=ctk.CTkFont(size=12), text_color=Theme.TEXT_SECONDARY,
            justify="center",
        ).pack(padx=28, pady=(0, 8))

        ctk.CTkLabel(
            overlay, text=expected,
            font=ctk.CTkFont(size=11), text_color=Theme.CYAN_GLOW,
            justify="center", wraplength=520,
        ).pack(padx=28, pady=(0, 4))

        if tried != expected:
            ctk.CTkLabel(
                overlay, text=f"Last tried: {tried}",
                font=ctk.CTkFont(size=10), text_color=Theme.TEXT_MUTED,
                justify="center", wraplength=520,
            ).pack(padx=28, pady=(0, 8))

        ctk.CTkButton(
            overlay, text="Retry Load", width=120, height=32,
            fg_color=Theme.PRIMARY, hover_color=Theme.PRIMARY_LIGHT,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=self.reload,
        ).pack(padx=28, pady=(8, 22))

        self._missing_overlay = overlay
        self._redraw_fixed_overlays()
        self._update_zoom_label()

    def _redraw_fixed_overlays(self):
        for item in self._compass_ids:
            self.canvas.delete(item)
        self._compass_ids = []

        ch = max(self.canvas.winfo_height(), 1)
        cw = max(self.canvas.winfo_width(), 1)
        if cw < 40 or ch < 40:
            return

        cx, cy, r = 70, ch - 70, 36

        oval = self.canvas.create_oval(
            cx - r, cy - r, cx + r, cy + r,
            outline=Theme.BORDER, width=2, fill=Theme.BG_CARD, tags=("overlay",),
        )
        ring = self.canvas.create_oval(
            cx - r + 6, cy - r + 6, cx + r - 6, cy + r - 6,
            outline=Theme.PRIMARY, width=1, tags=("overlay",),
        )
        n = self.canvas.create_text(
            cx, cy - r + 12, text="N", fill=Theme.PRIMARY,
            font=("Segoe UI", 10, "bold"), tags=("overlay",),
        )
        s = self.canvas.create_text(
            cx, cy + r - 12, text="S", fill=Theme.TEXT_SECONDARY,
            font=("Segoe UI", 9), tags=("overlay",),
        )
        e = self.canvas.create_text(
            cx + r - 12, cy, text="E", fill=Theme.TEXT_SECONDARY,
            font=("Segoe UI", 9), tags=("overlay",),
        )
        w = self.canvas.create_text(
            cx - r + 12, cy, text="W", fill=Theme.TEXT_SECONDARY,
            font=("Segoe UI", 9), tags=("overlay",),
        )
        needle = self.canvas.create_polygon(
            cx, cy - 18, cx - 7, cy + 4, cx + 7, cy + 4,
            fill=Theme.PRIMARY, outline="", tags=("overlay",),
        )
        self._compass_ids = [oval, ring, n, s, e, w, needle]
        self.canvas.tag_raise("overlay")

    def _redraw_overlays(self):
        # Rooms + markers redraw together so pan/zoom never leaves them behind
        canvas = self.canvas
        canvas.delete("room_poly")
        canvas.delete("room_draft")
        canvas.delete("device_marker")

        if not self.has_image():
            return

        for room in self._rooms:
            pts = room.get("_points") or []
            if len(pts) < 3:
                continue
            flat = []
            for nx, ny in pts:
                cx, cy = self.norm_to_canvas(nx, ny)
                flat.extend([cx, cy])
            canvas.create_polygon(
                *flat,
                fill="#FF3B3B22",
                outline=Theme.DANGER_LIGHT,
                width=1,
                tags=("room_poly",),
            )
            # Room name at centroid so operators can tell zones apart
            mid_x = sum(p[0] for p in pts) / len(pts)
            mid_y = sum(p[1] for p in pts) / len(pts)
            tx, ty = self.norm_to_canvas(mid_x, mid_y)
            canvas.create_text(
                tx, ty, text=room.get("name") or "Room",
                fill=Theme.TEXT_SECONDARY, font=("Segoe UI", 9),
                tags=("room_poly",),
            )

        if self._room_draft:
            flat = []
            for nx, ny in self._room_draft:
                cx, cy = self.norm_to_canvas(nx, ny)
                flat.extend([cx, cy])
                canvas.create_oval(
                    cx - 4, cy - 4, cx + 4, cy + 4,
                    fill=Theme.WARNING, outline="", tags=("room_draft",),
                )
            if len(self._room_draft) >= 2:
                canvas.create_line(
                    *flat, fill=Theme.WARNING, width=2, dash=(4, 3), tags=("room_draft",),
                )

        for d in self._devices:
            if not d.get("enabled", True):
                continue
            x_norm, y_norm = d.get("x_norm"), d.get("y_norm")
            if x_norm is None or y_norm is None:
                continue
            uid = d.get("device_uid") or d.get("name") or "Device"
            dtype = "camera" if d.get("device_type") == "camera" else "pir"
            x, y = self.norm_to_canvas(float(x_norm), float(y_norm))
            selected = uid == self._selected_uid
            outline = Theme.CYAN_GLOW if selected else Theme.TEXT_PRIMARY
            width = 2 if selected else 1

            tag = ("device_marker", f"dev:{uid}")
            if dtype == "camera":
                canvas.create_rectangle(
                    x - 10, y - 8, x + 10, y + 8,
                    fill=Theme.PRIMARY, outline=outline, width=width, tags=tag,
                )
                canvas.create_oval(
                    x - 3, y - 3, x + 3, y + 3,
                    fill=Theme.TEXT_PRIMARY, outline="", tags=tag,
                )
            else:
                canvas.create_oval(
                    x - 8, y - 8, x + 8, y + 8,
                    fill=Theme.SUCCESS, outline=outline, width=width, tags=tag,
                )
            canvas.create_text(
                x, y + 16, text=uid, fill=Theme.TEXT_PRIMARY,
                font=("Segoe UI", 8), tags=tag,
            )

        canvas.tag_raise("room_poly")
        canvas.tag_raise("room_draft")
        canvas.tag_raise("device_marker")
        # Keep live motion rings above markers while an animation is playing
        canvas.tag_raise("motion_fx")
        canvas.tag_raise("overlay")

    def _hit_test_device(self, canvas_x: float, canvas_y: float) -> Optional[str]:
        best_uid = None
        best_dist = self.HIT_RADIUS
        for d in self._devices:
            if not d.get("enabled", True):
                continue
            x_norm, y_norm = d.get("x_norm"), d.get("y_norm")
            if x_norm is None or y_norm is None:
                continue
            mx, my = self.norm_to_canvas(float(x_norm), float(y_norm))
            dist = ((canvas_x - mx) ** 2 + (canvas_y - my) ** 2) ** 0.5
            if dist <= best_dist:
                best_dist = dist
                best_uid = d.get("device_uid")
        return best_uid

    def _on_press(self, event):
        self._drag_last = (event.x, event.y)
        self._drag_moved = False
        self._dragging_uid = None

        if self._pil_image is None:
            return

        # In view mode, grab a marker to drag-move it without leaving Place Mode
        if self._mode == self.MODE_VIEW:
            hit = self._hit_test_device(event.x, event.y)
            if hit:
                self._dragging_uid = hit
                self.set_selected_uid(hit)

    def _on_drag(self, event):
        if self._drag_last is None or self._pil_image is None:
            return

        dx = event.x - self._drag_last[0]
        dy = event.y - self._drag_last[1]
        if abs(dx) > 2 or abs(dy) > 2:
            self._drag_moved = True

        # Dragging a device updates live preview; DB save happens on release
        if self._dragging_uid and self._mode == self.MODE_VIEW:
            nx, ny = self.canvas_to_norm(event.x, event.y)
            for d in self._devices:
                if d.get("device_uid") == self._dragging_uid:
                    d["x_norm"] = nx
                    d["y_norm"] = ny
                    break
            self._drag_last = (event.x, event.y)
            self._redraw_overlays()
            return

        if self._mode != self.MODE_VIEW:
            self._drag_last = (event.x, event.y)
            return

        self._offset_x += dx
        self._offset_y += dy
        self._drag_last = (event.x, event.y)
        self._clamp_pan()
        if self._bg_id is not None:
            self.canvas.coords(self._bg_id, self._offset_x, self._offset_y)
        self._redraw_overlays()
        self.event_generate("<<FloorPlanChanged>>", when="tail")

    def _on_release(self, event):
        was_drag = getattr(self, "_drag_moved", False)
        dragging = self._dragging_uid
        self._drag_last = None
        self._dragging_uid = None

        if self._pil_image is None:
            return

        if dragging and was_drag and self.on_device_moved:
            nx, ny = self.canvas_to_norm(event.x, event.y)
            self.on_device_moved(dragging, nx, ny)
            return

        if was_drag:
            return

        nx, ny = self.canvas_to_norm(event.x, event.y)

        if self._mode == self.MODE_PLACE_PIR:
            if self.on_place:
                self.on_place("pir", nx, ny)
            return
        if self._mode == self.MODE_PLACE_CAMERA:
            if self.on_place:
                self.on_place("camera", nx, ny)
            return
        if self._mode == self.MODE_EDIT_ROOM:
            self._room_draft.append((nx, ny))
            self._redraw_overlays()
            return

        # View mode click: select device or fire legacy on_click
        hit = self._hit_test_device(event.x, event.y)
        if hit:
            self.set_selected_uid(hit)
            if self.on_device_selected:
                self.on_device_selected(hit)
            return

        if self.on_click:
            self.on_click(nx, ny)

    def _on_double_click(self, event):
        if self._mode == self.MODE_EDIT_ROOM:
            # Double-click finishes the room outline
            self.finish_room_draft()
            return
        if self._mode == self.MODE_VIEW and not self._hit_test_device(event.x, event.y):
            self.reset_view()

    def _on_right_click(self, event):
        # Right-click cancels place/room draft without leaving the page
        if self._mode == self.MODE_EDIT_ROOM and self._room_draft:
            self.clear_room_draft()
            return
        if self._mode in (self.MODE_PLACE_PIR, self.MODE_PLACE_CAMERA, self.MODE_EDIT_ROOM):
            self.set_mode(self.MODE_VIEW)

    def _on_wheel(self, event):
        factor = self.ZOOM_STEP if event.delta > 0 else 1 / self.ZOOM_STEP
        self.set_zoom(self._zoom * factor, anchor_canvas=(event.x, event.y))

    def _on_wheel_linux(self, event, direction):
        factor = self.ZOOM_STEP if direction > 0 else 1 / self.ZOOM_STEP
        self.set_zoom(self._zoom * factor, anchor_canvas=(event.x, event.y))

    def _enter_fullscreen(self):
        win = tk.Toplevel(self)
        win.title("Floor Plan — Fullscreen")
        win.configure(bg=Theme.BG_PRIMARY)
        win.attributes("-fullscreen", True)
        win.bind("<Escape>", lambda e: self._exit_fullscreen())

        fs_canvas = FloorPlanCanvas(win, image_path=self.image_path)
        fs_canvas.pack(fill="both", expand=True)
        fs_canvas.set_devices(self._devices)
        fs_canvas.set_rooms(self._rooms)
        # Match the parent zoom after the fullscreen canvas finishes its first layout
        saved_zoom = self._zoom
        fs_canvas.after(120, lambda: fs_canvas.set_zoom(saved_zoom))

        hint = ctk.CTkLabel(
            win, text="Press Esc to exit fullscreen",
            text_color=Theme.TEXT_MUTED, font=ctk.CTkFont(size=12),
        )
        hint.place(relx=0.5, rely=0.02, anchor="n")

        self._fullscreen_win = win

    def _exit_fullscreen(self):
        if self._fullscreen_win and self._fullscreen_win.winfo_exists():
            self._fullscreen_win.destroy()
        self._fullscreen_win = None
