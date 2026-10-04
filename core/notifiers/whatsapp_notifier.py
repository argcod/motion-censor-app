"""Twilio WhatsApp API only — no unofficial WhatsApp Web automation."""
from __future__ import annotations

import json
import os
from typing import Any, Optional

from utils.logger import logger


def _mask(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


class WhatsAppNotifier:
    def __init__(
        self,
        account_sid: str = "",
        auth_token: str = "",
        from_number: str = "",
        to_number: str = "",
    ):
        self.account_sid = (account_sid or "").strip()
        self.auth_token = (auth_token or "").strip()
        self.from_number = self._normalize_wa(from_number)
        self.to_number = self._normalize_wa(to_number)

    @classmethod
    def from_settings(cls, settings) -> "WhatsAppNotifier":
        creds = cls._parse_credentials(settings.get("alert_whatsapp_credentials_json", ""))
        account_sid = (
            creds.get("account_sid")
            or os.getenv("TWILIO_ACCOUNT_SID", "")
            or ""
        )
        auth_token = (
            creds.get("auth_token")
            or os.getenv("TWILIO_AUTH_TOKEN", "")
            or ""
        )
        from_number = (
            creds.get("from")
            or os.getenv("TWILIO_WHATSAPP_FROM", "")
            or ""
        )
        to_number = (
            settings.get("alert_whatsapp_to", "")
            or os.getenv("ALERT_WHATSAPP_TO", "")
            or ""
        )
        return cls(
            account_sid=account_sid,
            auth_token=auth_token,
            from_number=from_number,
            to_number=to_number,
        )

    def is_configured(self) -> bool:
        return bool(
            self.account_sid
            and self.auth_token
            and self.from_number
            and self.to_number
        )

    def send(self, text: str, snapshot_path: Optional[str] = None) -> tuple[bool, str]:
        if not self.is_configured():
            return False, "whatsapp_not_configured"
        try:
            from twilio.rest import Client
        except ImportError:
            return False, "twilio_not_installed"

        try:
            client = Client(self.account_sid, self.auth_token)
            kwargs: dict[str, Any] = {
                "from_": self.from_number,
                "to": self.to_number,
                "body": text[:1500],
            }
            # Twilio media URL must be publicly reachable — local paths are skipped
            media_url = self._public_media_url(snapshot_path)
            if media_url:
                kwargs["media_url"] = [media_url]

            msg = client.messages.create(**kwargs)
            sid = getattr(msg, "sid", "") or "ok"
            logger.info(f"WhatsApp message queued ({_mask(sid)})")
            return True, "ok"
        except Exception as e:
            # Auth token must never appear in logs
            logger.error(f"WhatsApp send failed: {type(e).__name__}: {e}")
            return False, f"whatsapp_error: {type(e).__name__}"

    @staticmethod
    def _normalize_wa(number: str) -> str:
        n = (number or "").strip()
        if not n:
            return ""
        if n.startswith("whatsapp:"):
            return n
        if n.startswith("+"):
            return f"whatsapp:{n}"
        return n

    @staticmethod
    def _public_media_url(path: Optional[str]) -> Optional[str]:
        # Only attach if the setting already stores an http(s) URL (Twilio cannot read local disks)
        if not path:
            return None
        p = str(path).strip()
        if p.startswith("http://") or p.startswith("https://"):
            return p
        return None

    @staticmethod
    def _parse_credentials(raw) -> dict:
        if not raw:
            return {}
        if isinstance(raw, dict):
            return raw
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, TypeError, ValueError):
            return {}

    def describe(self) -> str:
        return f"whatsapp(to={_mask(self.to_number)})"
