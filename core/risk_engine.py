"""Simple non-AI risk scoring for motion events (Home/Away + time of day)."""
from __future__ import annotations

import datetime


class RiskEngine:
    """Home = Disarmed → lower risk; Away = Armed → higher, especially at night."""

    NIGHT_START = 22  # 10 PM
    NIGHT_END = 6     # 6 AM

    def compute(
        self,
        *,
        armed: bool = False,
        sensor_known: bool = True,
        detected_at: datetime.datetime | None = None,
    ) -> str:
        # Armed flag comes from mobile_alerts_armed (Away vs Home)
        now = detected_at or datetime.datetime.now()
        hour = now.hour
        is_night = hour >= self.NIGHT_START or hour < self.NIGHT_END

        if not armed:
            level = "Low"
        elif is_night:
            level = "High"
        else:
            level = "Medium"

        # Unknown sensor bumps risk one step so operators notice placement gaps
        if not sensor_known:
            level = self._bump(level)
        return level

    @staticmethod
    def _bump(level: str) -> str:
        order = ["Low", "Medium", "High", "Critical"]
        try:
            idx = order.index(level)
        except ValueError:
            return "Medium"
        return order[min(idx + 1, len(order) - 1)]
