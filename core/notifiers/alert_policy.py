"""Decide whether a mobile alert may send — Armed, schedule, then cooldown."""
from __future__ import annotations

import datetime
import json
from typing import Optional, Tuple


DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
# Monday=0 … Sunday=6 to match datetime.weekday()
_WEEKDAY_TO_KEY = {i: DAY_KEYS[i] for i in range(7)}


class AlertPolicy:
    def __init__(self, settings_manager):
        self.settings = settings_manager
        # Separate from the ~2s desktop motion debounce in MotionManager
        self._last_global_send: float = 0.0
        self._last_sensor_send: dict[str, float] = {}

    def is_armed(self) -> bool:
        return self._bool("mobile_alerts_armed", False)

    def cooldown_seconds(self) -> int:
        try:
            return max(0, int(self.settings.get("mobile_alert_cooldown_sec", "180") or 180))
        except (TypeError, ValueError):
            return 180

    def evaluate(
        self,
        sensor_id: Optional[str] = None,
        *,
        now: Optional[datetime.datetime] = None,
        bypass_schedule: bool = False,
        bypass_armed: bool = False,
        bypass_cooldown: bool = False,
    ) -> Tuple[bool, str]:
        """
        Return (allowed, reason). Policy order is fixed:
        1) master Armed  2) schedule window  3) cooldown
        Test Alert may bypass schedule / armed / cooldown via flags.
        """
        now = now or datetime.datetime.now()

        if not bypass_armed and not self.is_armed():
            return False, "disarmed"

        if not bypass_schedule and self._schedule_enabled():
            if not self._in_schedule_window(now):
                return False, "outside_schedule"

        if not bypass_cooldown:
            cool = self.cooldown_seconds()
            if cool > 0:
                ts = now.timestamp()
                if self._last_global_send and (ts - self._last_global_send) < cool:
                    return False, "cooldown_global"
                sid = (sensor_id or "").strip()
                if sid:
                    last = self._last_sensor_send.get(sid, 0.0)
                    if last and (ts - last) < cool:
                        return False, "cooldown_sensor"

        return True, "ok"

    def mark_sent(self, sensor_id: Optional[str] = None, when: Optional[datetime.datetime] = None):
        # Remember last successful fan-out so cooldown can suppress the next spam burst
        when = when or datetime.datetime.now()
        ts = when.timestamp()
        self._last_global_send = ts
        sid = (sensor_id or "").strip()
        if sid:
            self._last_sensor_send[sid] = ts

    def reset_cooldown(self):
        self._last_global_send = 0.0
        self._last_sensor_send.clear()

    def _schedule_enabled(self) -> bool:
        return self._bool("mobile_alerts_schedule_enabled", False)

    def _in_schedule_window(self, now: datetime.datetime) -> bool:
        days = self._parse_days()
        day_key = _WEEKDAY_TO_KEY.get(now.weekday(), "")
        if days and day_key not in days:
            return False

        start = self._parse_hhmm(self.settings.get("mobile_alerts_start", "22:00"), 22, 0)
        end = self._parse_hhmm(self.settings.get("mobile_alerts_end", "06:00"), 6, 0)
        current = now.hour * 60 + now.minute
        start_m = start[0] * 60 + start[1]
        end_m = end[0] * 60 + end[1]

        # Overnight window e.g. 22:00 → 06:00 spans midnight
        if start_m == end_m:
            return True
        if start_m < end_m:
            return start_m <= current < end_m
        return current >= start_m or current < end_m

    def _parse_days(self) -> set[str]:
        raw = self.settings.get("mobile_alerts_days", "") or ""
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(data, list):
                return {str(d).lower().strip() for d in data if str(d).strip()}
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        return set(DAY_KEYS)

    @staticmethod
    def _parse_hhmm(value, default_h: int, default_m: int) -> tuple[int, int]:
        try:
            text = str(value or "").strip()
            parts = text.split(":")
            h = int(parts[0])
            m = int(parts[1]) if len(parts) > 1 else 0
            if 0 <= h <= 23 and 0 <= m <= 59:
                return h, m
        except (TypeError, ValueError, IndexError):
            pass
        return default_h, default_m

    def _bool(self, key: str, default: bool = False) -> bool:
        raw = self.settings.get(key, "true" if default else "false")
        return str(raw).strip().lower() in ("1", "true", "yes", "on")
