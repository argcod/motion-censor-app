"""5-step motion animation drawn on the floor-plan canvas (trigger → glow → rings → room → done)."""
from __future__ import annotations

from typing import Callable, Optional

from utils.constants import Theme


class MotionAnimator:
    """Timed stage chain; cancel/restart when a new motion event arrives."""

    STAGE_DELAY_MS = 650  # ~0.4–0.8s per stage as in the plan
    TAG = "motion_fx"

    def __init__(
        self,
        floorplan,
        scheduler,
        on_stage: Optional[Callable[[int], None]] = None,
        on_complete: Optional[Callable[[], None]] = None,
    ):
        self.floorplan = floorplan
        self.scheduler = scheduler  # any widget with after / after_cancel
        self.on_stage = on_stage
        self.on_complete = on_complete

        self._jobs: list = []
        self._active = False
        self._x_norm = 0.5
        self._y_norm = 0.5
        self._room_points: list = []
        self._label = ""
        self._stage = -1

    @property
    def active(self) -> bool:
        return self._active

    def cancel(self):
        # Stop any pending after() ticks before starting a new event
        for job in self._jobs:
            try:
                self.scheduler.after_cancel(job)
            except Exception:
                pass
        self._jobs.clear()
        self._active = False
        self._stage = -1
        self.clear_fx()

    def clear_fx(self):
        try:
            self.floorplan.get_canvas().delete(self.TAG)
        except Exception:
            pass

    def refresh(self):
        # Redraw FX after pan/zoom so rings stay glued to the sensor
        if self._active and self._stage >= 0:
            self._draw_stage(self._stage)

    def play(
        self,
        x_norm: float,
        y_norm: float,
        label: str = "",
        room_points: Optional[list] = None,
    ):
        self.cancel()
        self._active = True
        self._x_norm = float(x_norm)
        self._y_norm = float(y_norm)
        self._label = label or "Motion Detected"
        self._room_points = list(room_points or [])

        # Nudge the viewport toward the sensor if it is off-screen
        if hasattr(self.floorplan, "center_on_norm"):
            self.floorplan.center_on_norm(self._x_norm, self._y_norm)

        # Stage 0 fires immediately; 1–4 follow on a timer chain
        self._run_stage(0)
        for i in range(1, 5):
            delay = self.STAGE_DELAY_MS * i
            job = self.scheduler.after(delay, lambda s=i: self._run_stage(s))
            self._jobs.append(job)

        # Clear FX shortly after the last stage so the plan stays readable
        done_delay = self.STAGE_DELAY_MS * 5 + 400
        job = self.scheduler.after(done_delay, self._finish)
        self._jobs.append(job)

    def _run_stage(self, stage: int):
        if not self._active:
            return
        self._stage = stage
        self._draw_stage(stage)
        if self.on_stage:
            self.on_stage(stage)

    def _finish(self):
        if not self._active:
            return
        self._active = False
        self._stage = -1
        self.clear_fx()
        if self.on_stage:
            self.on_stage(-1)
        if self.on_complete:
            self.on_complete()

    def _draw_stage(self, stage: int):
        canvas = self.floorplan.get_canvas()
        canvas.delete(self.TAG)
        if not self.floorplan.has_image():
            return

        x, y = self.floorplan.norm_to_canvas(self._x_norm, self._y_norm)
        tag = self.TAG

        # 1 Sensor Triggered — small flash at the PIR
        if stage >= 0:
            canvas.create_oval(
                x - 6, y - 6, x + 6, y + 6,
                fill=Theme.DANGER, outline=Theme.TEXT_PRIMARY, width=1, tags=(tag,),
            )

        # 2 Motion Pulse — node glow
        if stage >= 1:
            canvas.create_oval(
                x - 16, y - 16, x + 16, y + 16,
                outline=Theme.DANGER_LIGHT, width=3, tags=(tag,),
            )
            canvas.create_oval(
                x - 10, y - 10, x + 10, y + 10,
                fill="#FF3B3B55", outline="", tags=(tag,),
            )

        # 3 Expanding Wave — concentric rings
        if stage >= 2:
            for r in (28, 44, 60):
                canvas.create_oval(
                    x - r, y - r, x + r, y + r,
                    outline=Theme.DANGER_LIGHT, width=2, tags=(tag,),
                )

        # 4 Room Highlight — polygon tint, or soft zone if no room mapped
        if stage >= 3:
            if len(self._room_points) >= 3:
                flat = []
                for nx, ny in self._room_points:
                    cx, cy = self.floorplan.norm_to_canvas(nx, ny)
                    flat.extend([cx, cy])
                canvas.create_polygon(
                    *flat,
                    fill="#FF3B3B33",
                    outline=Theme.DANGER,
                    width=2,
                    tags=(tag,),
                )
            else:
                canvas.create_oval(
                    x - 70, y - 50, x + 70, y + 50,
                    fill="#FF3B3B22", outline=Theme.DANGER_LIGHT, width=1, tags=(tag,),
                )

        # 5 Event Complete — floating label + silhouette mark
        if stage >= 4:
            canvas.create_oval(
                x - 14, y - 28, x + 14, y - 4,
                fill=Theme.DANGER, outline=Theme.TEXT_PRIMARY, width=1, tags=(tag,),
            )
            canvas.create_text(
                x, y - 42,
                text=self._label,
                fill=Theme.DANGER_LIGHT,
                font=("Segoe UI", 10, "bold"),
                tags=(tag,),
            )

        canvas.tag_raise(tag)
        canvas.tag_raise("overlay")
