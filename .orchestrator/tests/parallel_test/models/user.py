"""User model for parallel test module."""

from dataclasses import dataclass


@dataclass
class User:
    """Represents a user with id, name, and email fields."""

    id: int
    name: str
    email: str

    def validate_email(self) -> bool:
        """Validate email format by checking for @ symbol.

        Returns:
            bool: True if email contains @ symbol, False otherwise.
        """
        return "@" in self.email if self.email else False

    def __post_init__(self) -> None:
        """Validate email format after initialization.

        Raises:
            ValueError: If email format is invalid.
        """
        if not self.validate_email():
            raise ValueError(f"Invalid email format: {self.email}")
