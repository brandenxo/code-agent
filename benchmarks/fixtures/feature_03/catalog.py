class Catalog:
    def __init__(self, products):
        self.products = list(products)

    def search(self, query):
        """Return products whose name contains query, case-insensitively."""
        raise NotImplementedError
