from pricing import apply_discount, subtotal


def sample_order():
    items = [{"price": 10.0, "quantity": 2}]
    return apply_discount(subtotal(items), 0.10)
