"""Product model for parallel test module."""
from dataclasses import dataclass


@dataclass
class Product:
    """Represents a product with basic information."""

    id: int
    name: str
    price: float
