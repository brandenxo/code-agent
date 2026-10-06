def subtotal(items):
    return sum(item["price"] * item["quantity"] for item in items)


def apply_discount(amount, rate):
    return amount * (1 - rate)
