# notifier.py
from logger_utils import log_event

def send_notification(message: str, level: str = "INFO"):
    """
    Basic notification function.
    Currently prints to console and logs.
    Can be extended for email, SMS, or app alerts.
    """
    alert = f"[{level}] {message}"
    print(alert)   # Console notification (Streamlit will also show)
    log_event("NOTIFICATION", {"level": level, "message": message})
    return alert
