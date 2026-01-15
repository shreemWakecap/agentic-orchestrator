"""
Parallel Test Module

A complete test module demonstrating parallel build capabilities with
models, registry, and utilities that can be built independently.
"""

from .registry import get_model
from . import models
from . import utils

__all__ = ["get_model", "models", "utils"]
