"""Verify Telegram Mini App initData (HMAC method from Telegram docs). Standard library only."""
from typing import Optional
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class InvalidInitData(ValueError):
    pass


def verify_init_data(init_data: str, bot_token: str, max_age: int = 86400, now: Optional[float] = None) -> dict:
    """Return the Telegram user dict if the signature is valid and fresh, else raise InvalidInitData."""
    try:
        pairs = dict(parse_qsl(init_data, keep_blank_values=True, strict_parsing=True))
    except ValueError:
        raise InvalidInitData("malformed")
    received = pairs.pop("hash", None)
    if not received:
        raise InvalidInitData("missing hash")
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, received):
        raise InvalidInitData("bad signature")
    try:
        age = (now or time.time()) - int(pairs["auth_date"])
        user = json.loads(pairs["user"])
        user["id"] = int(user["id"])
    except (KeyError, ValueError, TypeError):
        raise InvalidInitData("missing user or auth_date")
    if age > max_age or age < -300:
        raise InvalidInitData("expired")
    return user
