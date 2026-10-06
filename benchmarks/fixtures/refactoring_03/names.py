def customer_label(first, last):
    full_name = f"{first.strip().title()} {last.strip().title()}"
    return f"Customer: {full_name}"


def employee_label(first, last):
    full_name = f"{first.title()} {last.title()}"
    return f"Employee: {full_name}"
