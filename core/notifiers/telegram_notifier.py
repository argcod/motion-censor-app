"""Telegram Bot API — send text or photo without blocking the UI thread."""
from __future__ import annotations

import os
from typing import Optional

from utils.logger import logger


def _mask(value: str, keep: int = 4) -> str:
    if not value:
        return ""
    if len(value) <= keep:
        return "*" * len(value)
    return "*" * (len(value) - keep) + value[-keep:]


class TelegramNotifier:
    TIMEOUT = 20

    def __init__(self, token: str = "", chat_id: str = ""):
        self.token = (token or "").strip()
        self.chat_id = (chat_id or "").strip()

    @classmethod
    def from_settings(cls, settings) -> "TelegramNotifier":
        token = settings.get("alert_telegram_token", "") or os.getenv("ALERT_TELEGRAM_TOKEN", "")
        chat_id = settings.get("alert_telegram_chat_id", "") or os.getenv("ALERT_TELEGRAM_CHAT_ID", "")
        return cls(token=token, chat_id=chat_id)

    def is_configured(self) -> bool:
        return bool(self.token and self.chat_id)

    def send(self, text: str, snapshot_path: Optional[str] = None) -> tuple[bool, str]:
        if not self.is_configured():
            return False, "telegram_not_configured"
        try:
            import requests  # lazy so AlertPolicy tests do not need the package
        except ImportError:
            return False, "requests_not_installed"
        try:
            if snapshot_path and os.path.isfile(snapshot_path):
                return self._send_photo(requests, text, snapshot_path)
            return self._send_message(requests, text)
        except Exception as e:
            # Never log the bot token — only a short error reason
            logger.error(f"Telegram send failed: {e}")
            return False, f"telegram_error: {e}"

    def _api(self, method: str) -> str:
        return f"https://api.telegram.org/bot{self.token}/{method}"

    def _send_message(self, requests, text: str) -> tuple[bool, str]:
        resp = requests.post(
            self._api("sendMessage"),
            json={"chat_id": self.chat_id, "text": text},
            timeout=self.TIMEOUT,
        )
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "ok"
        return False, f"telegram_status_{resp.status_code}"

    def _send_photo(self, requests, caption: str, path: str) -> tuple[bool, str]:
        with open(path, "rb") as fh:
            resp = requests.post(
                self._api("sendPhoto"),
                data={"chat_id": self.chat_id, "caption": caption[:1024]},
                files={"photo": fh},
                timeout=self.TIMEOUT,
            )
        if resp.status_code == 200 and resp.json().get("ok"):
            return True, "ok"
        return False, f"telegram_status_{resp.status_code}"

    def describe(self) -> str:
        return f"telegram(chat={_mask(self.chat_id)})"
