"""Queue mobile alerts off the UI thread and fan out to enabled channels."""
from __future__ import annotations

import queue
import threading
from typing import Callable, Optional

from core.notifiers.alert_policy import AlertPolicy
from core.notifiers.discord_notifier import DiscordNotifier
from core.notifiers.telegram_notifier import TelegramNotifier
from core.notifiers.whatsapp_notifier import WhatsAppNotifier
from utils.logger import logger


class NotifierManager:
    def __init__(self, settings_manager, db_manager, ui_callback: Optional[Callable] = None):
        self.settings = settings_manager
        self.db = db_manager
        self.policy = AlertPolicy(settings_manager)
        self.ui_callback = ui_callback

        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, name="NotifierWorker", daemon=True)
        self._worker.start()

    # --- public API ---------------------------------------------------------

    def enqueue_motion(self, event: dict):
        """Real motion path — honor Armed / schedule / cooldown."""
        self._queue.put({"kind": "motion", "event": dict(event or {})})

    def enqueue_test(self, channels: Optional[list] = None, on_done: Optional[Callable] = None):
        """
        Test Alert: needs valid credentials, bypasses schedule.
        Still sends while Disarmed (caller should show the warning toast).
        """
        self._queue.put(
            {
                "kind": "test",
                "channels": channels,
                "on_done": on_done,
            }
        )

    def configured_channels(self) -> list[str]:
        # Used by Settings / topbar to warn when Armed with nothing wired up
        ready = []
        if self._channel_enabled("telegram") and TelegramNotifier.from_settings(self.settings).is_configured():
            ready.append("telegram")
        if self._channel_enabled("discord") and DiscordNotifier.from_settings(self.settings).is_configured():
            ready.append("discord")
        if self._channel_enabled("whatsapp") and WhatsAppNotifier.from_settings(self.settings).is_configured():
            ready.append("whatsapp")
        return ready

    def channel_credentials_ok(self, name: str) -> bool:
        # Test buttons only need credentials — the enable switch is not required
        if name == "telegram":
            return TelegramNotifier.from_settings(self.settings).is_configured()
        if name == "discord":
            return DiscordNotifier.from_settings(self.settings).is_configured()
        if name == "whatsapp":
            return WhatsAppNotifier.from_settings(self.settings).is_configured()
        return False

    def has_any_configured_channel(self) -> bool:
        return bool(self.configured_channels())

    def shutdown(self, timeout: float = 3.0):
        # Best-effort drain so logout / window close does not drop the last alert mid-send
        self._stop.set()
        self._queue.put({"kind": "stop"})
        if self._worker.is_alive():
            self._worker.join(timeout=timeout)

    # --- worker -------------------------------------------------------------

    def _run(self):
        while not self._stop.is_set():
            try:
                job = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                kind = job.get("kind")
                if kind == "stop":
                    break
                if kind == "test":
                    self._handle_test(job)
                else:
                    self._handle_motion(job.get("event") or {})
            except Exception as e:
                logger.error(f"Notifier worker error: {e}")
            finally:
                self._queue.task_done()

    def _handle_motion(self, event: dict):
        sensor_id = event.get("sensor_id")
        allowed, reason = self.policy.evaluate(sensor_id=sensor_id)
        log_id = event.get("id")

        if not allowed:
            logger.info(f"Mobile alert skipped ({reason}) for sensor={sensor_id}")
            if log_id:
                self.db.update_mobile_alert_status(
                    log_id,
                    sent=False,
                    channels="",
                    error=f"skipped:{reason}",
                )
            return

        results = self._fan_out(event, channels=None)
        if not results.get("attempted"):
            results["errors"] = list(results.get("errors") or []) + ["no_channels"]
        self._persist_results(log_id, results)
        if results["ok"]:
            self.policy.mark_sent(sensor_id)

    def _handle_test(self, job: dict):
        channels = job.get("channels")
        on_done = job.get("on_done")
        # Test bypasses schedule + armed + cooldown so operators can verify credentials anytime
        event = {
            "detected_at": _now_str(),
            "location": "Test Location",
            "sensor_id": "TEST",
            "camera_uid": None,
            "risk_level": "Test",
            "snapshot_path": None,
            "armed": self.policy.is_armed(),
            "is_test": True,
        }
        results = self._fan_out(event, channels=channels)
        if callable(on_done):
            try:
                on_done(results)
            except Exception as e:
                logger.error(f"Test alert callback failed: {e}")

    def _fan_out(self, event: dict, channels: Optional[list]) -> dict:
        text = self._format_payload(event)
        snapshot = event.get("snapshot_path")
        wanted = self._resolve_channels(channels)

        ok_channels: list[str] = []
        errors: list[str] = []

        for name in wanted:
            ok, detail = self._send_one(name, text, snapshot)
            if ok:
                ok_channels.append(name)
            else:
                errors.append(f"{name}:{detail}")

        return {
            "ok": bool(ok_channels),
            "channels": ok_channels,
            "errors": errors,
            "attempted": wanted,
        }

    def _send_one(self, name: str, text: str, snapshot: Optional[str]) -> tuple[bool, str]:
        if name == "telegram":
            return TelegramNotifier.from_settings(self.settings).send(text, snapshot)
        if name == "discord":
            return DiscordNotifier.from_settings(self.settings).send(text, snapshot)
        if name == "whatsapp":
            return WhatsAppNotifier.from_settings(self.settings).send(text, snapshot)
        return False, "unknown_channel"

    def _resolve_channels(self, channels: Optional[list]) -> list[str]:
        if channels:
            return [c for c in channels if c in ("telegram", "discord", "whatsapp")]
        out = []
        if self._channel_enabled("telegram"):
            out.append("telegram")
        if self._channel_enabled("discord"):
            out.append("discord")
        if self._channel_enabled("whatsapp"):
            out.append("whatsapp")
        return out

    def _channel_enabled(self, name: str) -> bool:
        key = {
            "telegram": "alert_telegram_enabled",
            "discord": "alert_discord_enabled",
            "whatsapp": "alert_whatsapp_enabled",
        }.get(name)
        if not key:
            return False
        return str(self.settings.get(key, "false")).lower() in ("1", "true", "yes", "on")

    def _persist_results(self, log_id, results: dict):
        if not log_id:
            return
        channels = ",".join(results.get("channels") or [])
        errors = "; ".join(results.get("errors") or [])
        sent = bool(results.get("ok"))
        # Persist send outcome on the motion_log row so Event Details can show it
        self.db.update_mobile_alert_status(
            log_id,
            sent=sent,
            channels=channels or None,
            error=errors or None,
        )

    def _format_payload(self, event: dict) -> str:
        armed = event.get("armed")
        if armed is None:
            armed = self.policy.is_armed()
        status = "Armed (Away)" if armed else "Disarmed (Home)"
        title = "Test Alert — Smart Motion Detection Alarm System using IoT" if event.get("is_test") else "Motion Detected — Smart Motion Detection Alarm System using IoT"
        lines = [
            title,
            f"Time: {event.get('detected_at') or '—'}",
            f"Location: {event.get('location') or '—'}",
            f"Sensor: {event.get('sensor_id') or '—'}",
            f"Camera: {event.get('camera_uid') or '—'}",
            f"Risk: {event.get('risk_level') or '—'}",
            f"Mobile Status: {status}",
        ]
        return "\n".join(lines)


def _now_str() -> str:
    import datetime
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
