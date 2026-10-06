from config import SETTINGS


def describe():
    return f"Timeout: {SETTINGS['timeout_seconds']} seconds"
