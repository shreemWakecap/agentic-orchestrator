# Plan: Create a parallel build test module structure in .orchestrator/tests/parallel_test/. Create: (1) mod

Request: Create a parallel build test module structure in .orchestrator/tests/parallel_test/. Create: (1) models/user.py with User class containing id, name, email fields and validation. (2) models/product.py with Product class containing id, name, price fields. (3) models/order.py with Order class containing id, user_id, product_ids, total. (4) models/__init__.py that exports all models. (5) registry.py that imports all models and provides get_model(name) function. (6) utils/validators.py with validate_email, validate_price functions. (7) utils/formatters.py with format_currency, format_date functions. (8) utils/__init__.py that exports utilities. Each file should have simple, independent implementations.
Complexity: medium

## Goal

Create a complete parallel build test module with models, registry, and utilities that can be built independently.

## Context

- Target directory .orchestrator/tests/parallel_test/ is new
- Use stdlib dataclasses and re module (no external dependencies)
- Follow existing test conventions in .orchestrator/tests/
- Each file should be simple and independently implementable

## Steps

1. Create package structure
   DO: Create __init__.py files for parallel_test/, models/, and utils/ directories to establish Python package structure
   IN: none
   OUT: .orchestrator/tests/parallel_test/__init__.py, .orchestrator/tests/parallel_test/models/__init__.py (empty initially), .orchestrator/tests/parallel_test/utils/__init__.py (empty initially)
   DONE: All three __init__.py files exist and are valid Python
   NEEDS: none

2. Create User model with validation
   DO: Create User dataclass with id (int), name (str), email (str) fields. Add __post_init__ method that validates email format using regex pattern. Raise ValueError for invalid email.
   IN: none
   OUT: .orchestrator/tests/parallel_test/models/user.py
   DONE: File exists, imports successfully, User("1", "test", "test@example.com") works, User("1", "test", "invalid") raises ValueError
   NEEDS: 1

3. Create Product model
   DO: Create Product dataclass with id (int), name (str), price (float) fields. Keep it simple with no validation.
   IN: none
   OUT: .orchestrator/tests/parallel_test/models/product.py
   DONE: File exists, imports successfully, Product(1, "Widget", 9.99) creates instance
   NEEDS: 1

4. Create Order model
   DO: Create Order dataclass with id (int), user_id (int), product_ids (List[int]), total (float) fields. Use field(default_factory=list) for product_ids.
   IN: none
   OUT: .orchestrator/tests/parallel_test/models/order.py
   DONE: File exists, imports successfully, Order(1, 1, [1,2], 19.98) creates instance
   NEEDS: 1

5. Export all models from models package
   DO: Update models/__init__.py to import User, Product, Order from their respective modules and add __all__ list for explicit exports
   IN: .orchestrator/tests/parallel_test/models/user.py, .orchestrator/tests/parallel_test/models/product.py, .orchestrator/tests/parallel_test/models/order.py
   OUT: .orchestrator/tests/parallel_test/models/__init__.py (modified)
   DONE: from parallel_test.models import User, Product, Order works
   NEEDS: 2, 3, 4

6. Create registry with get_model function
   DO: Create registry.py that imports all models, stores them in a dict mapping name strings to classes, and provides get_model(name: str) function that returns the class or raises KeyError
   IN: .orchestrator/tests/parallel_test/models/__init__.py
   OUT: .orchestrator/tests/parallel_test/registry.py
   DONE: get_model("User") returns User class, get_model("Unknown") raises KeyError
   NEEDS: 5

7. Create validators utility module
   DO: Create validate_email(email: str) -> bool using re.match with standard email regex pattern. Create validate_price(price: float) -> bool that returns True if price > 0.
   IN: none
   OUT: .orchestrator/tests/parallel_test/utils/validators.py
   DONE: validate_email("test@example.com") returns True, validate_email("invalid") returns False, validate_price(9.99) returns True, validate_price(-1) returns False
   NEEDS: 1

8. Create formatters utility module
   DO: Create format_currency(amount: float) -> str that returns f"${amount:.2f}". Create format_date(date) -> str that accepts datetime and returns ISO format string using isoformat().
   IN: none
   OUT: .orchestrator/tests/parallel_test/utils/formatters.py
   DONE: format_currency(9.99) returns "$9.99", format_date(datetime(2024,1,1)) returns ISO string
   NEEDS: 1

9. Export utilities from utils package
   DO: Update utils/__init__.py to import validate_email, validate_price from validators and format_currency, format_date from formatters. Add __all__ list.
   IN: .orchestrator/tests/parallel_test/utils/validators.py, .orchestrator/tests/parallel_test/utils/formatters.py
   OUT: .orchestrator/tests/parallel_test/utils/__init__.py (modified)
   DONE: from parallel_test.utils import validate_email, format_currency works
   NEEDS: 7, 8

10. Update main package init
    DO: Update parallel_test/__init__.py to provide convenient top-level imports of models and registry
    IN: .orchestrator/tests/parallel_test/models/__init__.py, .orchestrator/tests/parallel_test/registry.py
    OUT: .orchestrator/tests/parallel_test/__init__.py (modified)
    DONE: import parallel_test works without errors
    NEEDS: 5, 6, 9

## Verify

- python -c "from parallel_test.models import User, Product, Order; print('Models OK')"
- python -c "from parallel_test.registry import get_model; print(get_model('User'))"
- python -c "from parallel_test.utils import validate_email, format_currency; print(validate_email('test@x.com'), format_currency(9.99))"
- All 8 numbered requirements have corresponding implementation steps
