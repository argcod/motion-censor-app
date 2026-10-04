"""Discord incoming webhook — JSON content or multipart with a snapshot file."""
from __future__ import annotations

import json
import os
from typing import Optional

from utils.logger import logger


def _mask_url(url: str) -> str:
    if not url:
        return ""
    if len(url) <= 8:
        return "****"
    return url[:12] + "…" + url[-4:]


class DiscordNotifier:
    TIMEOUT = 20

    def __init__(self, webhook_url: str = ""):
        self.webhook_url = (webhook_url or "").strip()

    @classmethod
    def from_settings(cls, settings) -> "DiscordNotifier":
        url = settings.get("alert_discord_webhook", "") or os.getenv("ALERT_DISCORD_WEBHOOK", "")
        return cls(webhook_url=url)

    def is_configured(self) -> bool:
        return self.webhook_url.startswith("https://")

    def send(self, text: str, snapshot_path: Optional[str] = None) -> tuple[bool, str]:
        if not self.is_configured():
            return False, "discord_not_configured"
        try:
            import requests  # lazy so unit tests do not require the package
        except ImportError:
            return False, "requests_not_installed"
        try:
            if snapshot_path and os.path.isfile(snapshot_path):
                return self._send_with_file(requests, text, snapshot_path)
            resp = requests.post(
                self.webhook_url,
                json={"content": text[:2000]},
                timeout=self.TIMEOUT,
            )
            if resp.status_code in (200, 204):
                return True, "ok"
            return False, f"discord_status_{resp.status_code}"
        except Exception as e:
            logger.error(f"Discord send failed ({_mask_url(self.webhook_url)}): {e}")
            return False, f"discord_error: {e}"

    def _send_with_file(self, requests, text: str, path: str) -> tuple[bool, str]:
        # Multipart keeps caption + image in one Discord message
        payload = {"content": text[:2000]}
        with open(path, "rb") as fh:
            resp = requests.post(
                self.webhook_url,
                data={"payload_json": json.dumps(payload)},
                files={"file": (os.path.basename(path), fh, "image/jpeg")},
                timeout=self.TIMEOUT,
            )
        if resp.status_code in (200, 204):
            return True, "ok"
        return False, f"discord_status_{resp.status_code}"

    def describe(self) -> str:
        return f"discord({_mask_url(self.webhook_url)})"
