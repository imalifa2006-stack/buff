from typing import Optional
import hashlib
import secrets

from argon2 import PasswordHasher

_ph = PasswordHasher()  # argon2id
_DUMMY = _ph.hash("dummy-password")


def new_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored: Optional[str], password: str) -> bool:
    try:
        return _ph.verify(stored or _DUMMY, password) and stored is not None
    except Exception:
        return False
