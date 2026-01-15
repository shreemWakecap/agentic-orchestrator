"""
Parallel Test Module

A complete test module demonstrating parallel build capabilities with
models, registry, and utilities that can be built independently.

Usage:
    # Import models directly
    from parallel_test import User, Product, Order

    # Use registry functions
    from parallel_test import get_model, list_models, register_model
    UserModel = get_model('User')

    # Use utilities directly
    from parallel_test import validate_email, format_currency

    # Or access submodules
    from parallel_test import models, utils
"""

# Model classes - direct access
from .models import User, Product, Order

# Registry functions
from .registry import get_model, list_models, register_model

# Utility functions - direct access
from .utils import validate_email, validate_price, format_currency, format_date

# Submodules for explicit access
from . import models
from . import utils

__all__ = [
    # Models
    "User",
    "Product",
    "Order",
    # Registry
    "get_model",
    "list_models",
    "register_model",
    # Validators
    "validate_email",
    "validate_price",
    # Formatters
    "format_currency",
    "format_date",
    # Submodules
    "models",
    "utils",
]
