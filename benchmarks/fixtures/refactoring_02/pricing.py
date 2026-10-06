def retail_price(amount, percent):
    discount = amount * percent / 100
    return amount - discount


def vip_price(amount, percent):
    discount = amount * percent
    return amount - discount
