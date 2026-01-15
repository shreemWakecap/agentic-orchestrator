"""Product model for parallel test module."""


class Product:
    """Represents a product with basic information."""

    def __init__(self, id: int, name: str, price: float):
        """Initialize a Product instance.

        Args:
            id: Unique product identifier.
            name: Name of the product.
            price: Price of the product.
        """
        self.id = id
        self.name = name
        self.price = price
