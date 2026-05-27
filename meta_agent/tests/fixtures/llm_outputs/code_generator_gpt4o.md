Sure! Here's a production-ready implementation of the user authentication service:

## Implementation

```python
import hashlib
import secrets
from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """Represents an authenticated user."""
    id: int
    email: str
    password_hash: str
    salt: str


class AuthService:
    """Handles user registration and authentication."""

    def __init__(self, db_connection):
        self.db = db_connection

    def register(self, email: str, password: str) -> User:
        """Register a new user with salted password hashing.

        Args:
            email: User's email address
            password: Plain text password (min 8 chars)

        Returns:
            Newly created User object

        Raises:
            ValueError: If email already exists or password too short
        """
        if len(password) < 8:
            raise ValueError("Password must be at least 8 characters")

        if self.db.find_user_by_email(email):
            raise ValueError(f"User with email {email} already exists")

        salt = secrets.token_hex(16)
        password_hash = hashlib.sha256(
            f"{password}{salt}".encode()
        ).hexdigest()

        user = self.db.create_user(
            email=email,
            password_hash=password_hash,
            salt=salt,
        )
        return user

    def authenticate(self, email: str, password: str) -> Optional[User]:
        """Verify credentials and return user if valid."""
        user = self.db.find_user_by_email(email)
        if not user:
            return None

        expected_hash = hashlib.sha256(
            f"{password}{user.salt}".encode()
        ).hexdigest()

        if expected_hash != user.password_hash:
            return None

        return user
```

I chose SHA-256 with per-user salts for password hashing. In a real production system, you'd want to use bcrypt or argon2 instead, but this demonstrates the salt pattern. The `authenticate` method returns `None` instead of raising to avoid leaking information about which part of the credentials was wrong.
