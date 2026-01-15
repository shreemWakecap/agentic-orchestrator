"""Order model for parallel test module."""

from typing import List


class Order:
    """Represents an order with user and product information."""

    def __init__(self, id: int, user_id: int, product_ids: List[int], total: float):
        """Initialize an Order instance.

        Args:
            id: Unique order identifier.
            user_id: ID of the user who placed the order.
            product_ids: List of product IDs in the order.
            total: Total price of the order.
        """
        self.id = id
        self.user_id = user_id
        self.product_ids = product_ids
        self.total = total
