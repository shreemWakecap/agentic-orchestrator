"""User model for parallel test module."""

import re


class User:
    """Represents a user with id, name, and email fields."""

    def __init__(self, id: int, name: str, email: str):
        """Initialize a User instance.

        Args:
            id: Unique user identifier.
            name: User's name.
            email: User's email address.
        """
        self.id = id
        self.name = name
        self.email = email

    def validate(self) -> bool:
        """Validate the user's email address.

        Returns:
            True if the email is valid, False otherwise.
        """
        if not self.email:
            return False
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(email_pattern, self.email))
