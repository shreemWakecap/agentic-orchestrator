# Implementation Plan

> Part of plan: Create a test module with 3 independent model files (user.py, product.py, order.py) in tests/parallel_test/models/, a registry.py that imports all models, and 2 utility files (validators.py, formatters.py) in tests/parallel_test/utils/. Each file should have a simple class or function. This tests parallel build capability.

## Implementation Steps

### Phase 1: Setup
> Create package structure with __init__.py files

#### Step 1.1: create tests/parallel_test/__init__.py
**Action:** create
**Target:** tests/parallel_test/__init__.py
**Dependencies:** none
**Parallel:** init-files
**Description:** Create package init for the parallel_test module

```python
"""Parallel test module for validating parallel build capability."""
```

#### Step 1.2: create tests/parallel_test/models/__init__.py
**Action:** create
**Target:** tests/parallel_test/models/__init__.py
**Dependencies:** none
**Parallel:** init-files
**Description:** Create package init for models, exposing all model classes

```python
"""Models package containing User, Product, and Order classes."""

from .user import User
from .product import Product
from .order import Order

__all__ = ["User", "Product", "Order"]
```

#### Step 1.3: create tests/parallel_test/utils/__init__.py
**Action:** create
**Target:** tests/parallel_test/utils/__init__.py
**Dependencies:** none
**Parallel:** init-files
**Description:** Create package init for utils, exposing utility functions

```python
"""Utilities package containing validators and formatters."""

from .validators import validate_email, validate_positive
from .formatters import format_currency, format_order_id

__all__ = ["validate_email", "validate_positive", "format_currency", "format_order_id"]
```

### Phase 2: Core Implementation
> Create model classes and utility functions

#### Step 2.1: create tests/parallel_test/models/user.py
**Action:** create
**Target:** tests/parallel_test/models/user.py
**Dependencies:** none
**Parallel:** models
**Description:** Create User model class with name and email attributes

```python
"""User model class."""


class User:
    """Represents a user with name and email."""

    def __init__(self, name: str, email: str):
        self.name = name
        self.email = email

    def __repr__(self) -> str:
        return f"User(name={self.name!r}, email={self.email!r})"
```

#### Step 2.2: create tests/parallel_test/models/product.py
**Action:** create
**Target:** tests/parallel_test/models/product.py
**Dependencies:** none
**Parallel:** models
**Description:** Create Product model class with name and price attributes

```python
"""Product model class."""


class Product:
    """Represents a product with name and price."""

    def __init__(self, name: str, price: float):
        self.name = name
        self.price = price

    def __repr__(self) -> str:
        return f"Product(name={self.name!r}, price={self.price})"
```

#### Step 2.3: create tests/parallel_test/models/order.py
**Action:** create
**Target:** tests/parallel_test/models/order.py
**Dependencies:** none
**Parallel:** models
**Description:** Create Order model class with order_id and total attributes

```python
"""Order model class."""


class Order:
    """Represents an order with order_id and total."""

    def __init__(self, order_id: str, total: float):
        self.order_id = order_id
        self.total = total

    def __repr__(self) -> str:
        return f"Order(order_id={self.order_id!r}, total={self.total})"
```

#### Step 2.4: create tests/parallel_test/utils/validators.py
**Action:** create
**Target:** tests/parallel_test/utils/validators.py
**Dependencies:** none
**Parallel:** utils
**Description:** Create validator utility functions for email and positive numbers

```python
"""Validator utility functions."""

import re


def validate_email(email: str) -> bool:
    """Validate that a string is a valid email format."""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_positive(value: float) -> bool:
    """Validate that a number is positive."""
    return value > 0
```

#### Step 2.5: create tests/parallel_test/utils/formatters.py
**Action:** create
**Target:** tests/parallel_test/utils/formatters.py
**Dependencies:** none
**Parallel:** utils
**Description:** Create formatter utility functions for currency and order IDs

```python
"""Formatter utility functions."""


def format_currency(amount: float) -> str:
    """Format a float as currency string."""
    return f"${amount:,.2f}"


def format_order_id(order_id: str) -> str:
    """Format an order ID with prefix."""
    return f"ORD-{order_id.upper()}"
```

#### Step 2.6: create tests/parallel_test/registry.py
**Action:** create
**Target:** tests/parallel_test/registry.py
**Dependencies:** Step 2.1, Step 2.2, Step 2.3
**Description:** Create registry that imports and exposes all model classes

```python
"""Central registry for all model classes."""

from .models import User, Product, Order

MODELS = {
    "User": User,
    "Product": Product,
    "Order": Order,
}


def get_model(name: str):
    """Get a model class by name."""
    return MODELS.get(name)


def list_models() -> list[str]:
    """List all registered model names."""
    return list(MODELS.keys())
```

### Phase 3: Testing
> Validate the module structure and imports

#### Step 3.1: run python import test
**Action:** run
**Target:** python -c "from tests.parallel_test.models import User, Product, Order; print('Models imported successfully')"
**Dependencies:** Step 2.6
**Parallel:** validation
**Description:** Verify all model classes can be imported

```bash
python -c "from tests.parallel_test.models import User, Product, Order; print('Models imported successfully')"
```

#### Step 3.2: run python utils test
**Action:** run
**Target:** python -c "from tests.parallel_test.utils import validate_email, format_currency; print('Utils imported successfully')"
**Dependencies:** Step 2.4, Step 2.5
**Parallel:** validation
**Description:** Verify all utility functions can be imported

```bash
python -c "from tests.parallel_test.utils import validate_email, format_currency; print('Utils imported successfully')"
```

#### Step 3.3: run python registry test
**Action:** run
**Target:** python -c "from tests.parallel_test.registry import MODELS, get_model; print(f'Registry has {len(MODELS)} models: {list(MODELS.keys())}')"
**Dependencies:** Step 2.6
**Parallel:** validation
**Description:** Verify registry imports and exposes all models

```bash
python -c "from tests.parallel_test.registry import MODELS, get_model; print(f'Registry has {len(MODELS)} models: {list(MODELS.keys())}')"
```

## Testing Strategy

| Test Type | File | What it verifies |
|-----------|------|------------------|
| Import | tests/parallel_test/models/__init__.py | All 3 model classes importable |
| Import | tests/parallel_test/utils/__init__.py | All utility functions importable |
| Import | tests/parallel_test/registry.py | Registry correctly imports and exposes models |
| Functional | Manual validation | Model instantiation and utility function execution |

## Validation Commands

```bash
# Verify all imports work
python -c "from tests.parallel_test.models import User, Product, Order; from tests.parallel_test.utils import validate_email, format_currency; from tests.parallel_test.registry import MODELS; print('All imports successful'); print(f'Models: {list(MODELS.keys())}')"

# Test model instantiation
python -c "from tests.parallel_test.models import User; u = User('Alice', 'alice@example.com'); print(u)"

# Test utility functions
python -c "from tests.parallel_test.utils import validate_email, format_currency; print(validate_email('test@example.com')); print(format_currency(99.99))"

# Test registry lookup
python -c "from tests.parallel_test.registry import get_model; UserClass = get_model('User'); u = UserClass('Bob', 'bob@test.com'); print(u)"
```
