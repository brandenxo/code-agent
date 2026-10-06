def create_user(email):
    normalized = email.strip().lower()
    return {"kind": "user", "email": normalized}


def create_admin(email):
    normalized = email.lower()
    return {"kind": "admin", "email": normalized}
