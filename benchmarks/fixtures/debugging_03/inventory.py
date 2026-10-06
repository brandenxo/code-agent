def remove_stock(stock, item, quantity):
    """Remove quantity from an existing item without changing other items."""
    if item not in stock:
        raise KeyError(item)
    stock = {item: stock[item] - quantity}
    return stock
