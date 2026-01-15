"""Order model for parallel test module."""

from dataclasses import dataclass, field
from typing import List


@dataclass
class Order:
    """Represents an order with user and product information.

    Attributes:
        id: Unique order identifier.
        user_id: ID of the user who placed the order.
        product_ids: List of product IDs in the order.
        total: Total price of the order.
    """
    id: int
    user_id: int
    product_ids: List[int] = field(default_factory=list)
    total: float = 0.0
