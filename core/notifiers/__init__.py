# Phase 5 — Mobile Alert Hub (Telegram / Discord / Twilio WhatsApp)
from core.notifiers.alert_policy import AlertPolicy

__all__ = ["NotifierManager", "AlertPolicy"]


def __getattr__(name):
    # Lazy-load the manager so policy unit tests do not need requests/twilio installed
    if name == "NotifierManager":
        from core.notifiers.notifier_manager import NotifierManager
        return NotifierManager
    raise AttributeError(name)
