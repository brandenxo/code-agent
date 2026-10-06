VALID_TRANSITIONS = {
    "pending": {"running"},
    "running": {"complete", "failed"},
    "complete": set(),
    "failed": set(),
}


class Job:
    def __init__(self):
        self.status = "pending"

    def transition(self, new_status):
        if new_status not in VALID_TRANSITIONS[self.status]:
            raise ValueError("invalid transition")
        self.status = new_status
