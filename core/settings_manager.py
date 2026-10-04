# Default settings for Phase 0 — mobile keys exist early so later phases just flip them on
import json
import os

DEFAULT_SETTINGS = {
    "com_port": "COM3",
    "baud_rate": "115200",
    "notifications_enabled": "true",
    "camera_capture_enabled": "true",
    "camera_index": "0",
    "active_floor_plan_id": "",
    "mobile_alerts_armed": "false",
    "mobile_alerts_schedule_enabled": "false",
    "mobile_alerts_days": '["mon","tue","wed","thu","fri","sat","sun"]',
    "mobile_alerts_start": "22:00",
    "mobile_alerts_end": "06:00",
    "mobile_alert_cooldown_sec": "180",
    "alert_telegram_enabled": "false",
    "alert_telegram_token": "",
    "alert_telegram_chat_id": "",
    "alert_discord_enabled": "false",
    "alert_discord_webhook": "",
    "alert_whatsapp_enabled": "false",
    "alert_whatsapp_provider": "twilio",
    "alert_whatsapp_credentials_json": "",
    "alert_whatsapp_to": "",
}

# .env keys that may override DB secrets for local demos (UI still owns Armed/schedule)
_ENV_OVERRIDES = {
    "ALERT_TELEGRAM_TOKEN": "alert_telegram_token",
    "ALERT_TELEGRAM_CHAT_ID": "alert_telegram_chat_id",
    "ALERT_DISCORD_WEBHOOK": "alert_discord_webhook",
    "ALERT_WHATSAPP_TO": "alert_whatsapp_to",
    "COM_PORT": "com_port",
    "BAUD_RATE": "baud_rate",
    "CAMERA_INDEX": "camera_index",
}


class SettingsManager:
    def __init__(self, db_manager):
        self.db = db_manager
        self.settings = {}
        self.load_settings()
        self.apply_env_overrides()

    def load_settings(self):
        self.settings = self.db.get_settings() or {}

        # Fill any missing keys so the UI never crashes on a fresh install
        for key, value in DEFAULT_SETTINGS.items():
            if key not in self.settings:
                self.settings[key] = value

    def apply_env_overrides(self):
        # Mirror .env secrets into memory (and DB if empty) so notifiers see them
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        for env_key, setting_key in _ENV_OVERRIDES.items():
            val = os.getenv(env_key)
            if not val:
                continue
            current = (self.settings.get(setting_key) or "").strip()
            if not current:
                self.settings[setting_key] = val
                self.db.save_setting(setting_key, val)

        # Twilio WhatsApp creds live as one JSON blob when SID/token/from come from .env
        sid = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
        token = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
        from_num = os.getenv("TWILIO_WHATSAPP_FROM", "").strip()
        if sid or token or from_num:
            existing = self.settings.get("alert_whatsapp_credentials_json") or ""
            try:
                data = json.loads(existing) if existing else {}
                if not isinstance(data, dict):
                    data = {}
            except (json.JSONDecodeError, TypeError):
                data = {}
            if sid and not data.get("account_sid"):
                data["account_sid"] = sid
            if token and not data.get("auth_token"):
                data["auth_token"] = token
            if from_num and not data.get("from"):
                data["from"] = from_num
            if data:
                blob = json.dumps(data)
                self.settings["alert_whatsapp_credentials_json"] = blob
                if not (existing or "").strip():
                    self.db.save_setting("alert_whatsapp_credentials_json", blob)

    def get(self, key, default=None):
        return self.settings.get(key, default)

    def set(self, key, value):
        self.settings[key] = str(value)
        self.db.save_setting(key, str(value))

    def ensure_persisted_defaults(self):
        # Write defaults into MySQL once so Settings and later phases see them
        stored = self.db.get_settings() or {}
        for key, value in DEFAULT_SETTINGS.items():
            if key not in stored:
                self.db.save_setting(key, value)
                self.settings[key] = value
