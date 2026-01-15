"""Model registry for parallel test module."""

from typing import Optional, Type

from .models import User, Product, Order

# Registry mapping model names to their classes
_registry = {
    'User': User,
    'Product': Product,
    'Order': Order,
}


def get_model(name: str) -> Optional[Type]:
    """Get a model class by name.

    Args:
        name: The name of the model to retrieve.

    Returns:
        The model class if found, None otherwise.
    """
    return _registry.get(name)


def list_models() -> list:
    """List all registered model names.

    Returns:
        A list of all registered model names.
    """
    return list(_registry.keys())
