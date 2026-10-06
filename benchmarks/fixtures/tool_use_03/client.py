from config import SETTINGS


def request_options():
    return {
        "timeout": SETTINGS["timeout_seconds"],
        "retries": SETTINGS["retries"],
    }
