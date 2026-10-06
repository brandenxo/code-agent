def parse_port(value):
    """Return an integer TCP port from 1 through 65535."""
    port = int(value)
    if port < 0 or port > 65535:
        raise ValueError("invalid port")
    return port
