"""Unit tests for AlertPolicy schedule / cooldown / armed gates (Phase 5)."""
from __future__ import annotations

import datetime
import unittest

from core.notifiers.alert_policy import AlertPolicy


class FakeSettings:
    def __init__(self, data=None):
        self.data = dict(data or {})

    def get(self, key, default=None):
        return self.data.get(key, default)


class AlertPolicyTests(unittest.TestCase):
    def _policy(self, **kwargs):
        defaults = {
            "mobile_alerts_armed": "true",
            "mobile_alerts_schedule_enabled": "false",
            "mobile_alerts_days": '["mon","tue","wed","thu","fri","sat","sun"]',
            "mobile_alerts_start": "22:00",
            "mobile_alerts_end": "06:00",
            "mobile_alert_cooldown_sec": "180",
        }
        defaults.update(kwargs)
        return AlertPolicy(FakeSettings(defaults))

    def test_disarmed_blocks(self):
        p = self._policy(mobile_alerts_armed="false")
        ok, reason = p.evaluate(sensor_id="Sensor01")
        self.assertFalse(ok)
        self.assertEqual(reason, "disarmed")

    def test_armed_allows(self):
        p = self._policy()
        ok, reason = p.evaluate(sensor_id="Sensor01")
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_overnight_schedule_inside(self):
        # 23:00 is inside 22:00–06:00
        p = self._policy(mobile_alerts_schedule_enabled="true")
        now = datetime.datetime(2026, 3, 16, 23, 0)  # Monday
        ok, reason = p.evaluate(sensor_id="S1", now=now)
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")

    def test_overnight_schedule_outside(self):
        # 12:00 is outside 22:00–06:00
        p = self._policy(mobile_alerts_schedule_enabled="true")
        now = datetime.datetime(2026, 3, 16, 12, 0)
        ok, reason = p.evaluate(sensor_id="S1", now=now)
        self.assertFalse(ok)
        self.assertEqual(reason, "outside_schedule")

    def test_same_day_schedule(self):
        p = self._policy(
            mobile_alerts_schedule_enabled="true",
            mobile_alerts_start="09:00",
            mobile_alerts_end="17:00",
        )
        inside = datetime.datetime(2026, 3, 16, 10, 0)
        outside = datetime.datetime(2026, 3, 16, 18, 0)
        self.assertTrue(p.evaluate(now=inside)[0])
        self.assertFalse(p.evaluate(now=outside)[0])

    def test_cooldown_global(self):
        p = self._policy(mobile_alert_cooldown_sec="60")
        t0 = datetime.datetime(2026, 3, 16, 10, 0, 0)
        self.assertTrue(p.evaluate(sensor_id="A", now=t0)[0])
        p.mark_sent("A", when=t0)
        t1 = t0 + datetime.timedelta(seconds=30)
        ok, reason = p.evaluate(sensor_id="B", now=t1)
        self.assertFalse(ok)
        self.assertEqual(reason, "cooldown_global")

    def test_cooldown_expires(self):
        p = self._policy(mobile_alert_cooldown_sec="60")
        t0 = datetime.datetime(2026, 3, 16, 10, 0, 0)
        p.mark_sent("A", when=t0)
        t1 = t0 + datetime.timedelta(seconds=61)
        self.assertTrue(p.evaluate(sensor_id="A", now=t1)[0])

    def test_bypass_flags_for_test_alert(self):
        p = self._policy(mobile_alerts_armed="false", mobile_alerts_schedule_enabled="true")
        now = datetime.datetime(2026, 3, 16, 12, 0)
        ok, reason = p.evaluate(
            sensor_id="TEST",
            now=now,
            bypass_armed=True,
            bypass_schedule=True,
            bypass_cooldown=True,
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "ok")


if __name__ == "__main__":
    unittest.main()
