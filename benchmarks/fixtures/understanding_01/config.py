import os

DEFAULT_TIMEOUT = 30


def timeout():
    return int(os.getenv("AGENT_TIMEOUT", DEFAULT_TIMEOUT))
