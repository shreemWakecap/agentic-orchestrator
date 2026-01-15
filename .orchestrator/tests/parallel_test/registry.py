"""Model registry for parallel test module.

This module imports all models and provides a get_model function
to retrieve model classes by name.
"""

from typing import Type

from .models import User, Product, Order

# Registry mapping model name strings to their classes
_MODEL_REGISTRY: dict[str, Type] = {
    'User': User,
    'Product': Product,
    'Order': Order,
}


def get_model(name: str) -> Type:
    """Get a model class by name.

    Args:
        name: The name of the model to retrieve (case-sensitive).

    Returns:
        The model class.

    Raises:
        KeyError: If the model name is not found in the registry.
    """
    if name not in _MODEL_REGISTRY:
        raise KeyError(f"Model '{name}' not found in registry. Available models: {list(_MODEL_REGISTRY.keys())}")
    return _MODEL_REGISTRY[name]


def list_models() -> list[str]:
    """List all registered model names.

    Returns:
        A list of all registered model names.
    """
    return list(_MODEL_REGISTRY.keys())


def register_model(name: str, model_class: Type) -> None:
    """Register a new model in the registry.

    Args:
        name: The name to register the model under.
        model_class: The model class to register.

    Raises:
        ValueError: If a model with this name is already registered.
    """
    if name in _MODEL_REGISTRY:
        raise ValueError(f"Model '{name}' is already registered")
    _MODEL_REGISTRY[name] = model_class
