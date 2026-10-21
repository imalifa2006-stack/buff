import hashlib
import hmac
import json
import time
import unittest
from urllib.parse import urlencode

from app.telegram import InvalidInitData, verify_init_data

TOKEN = "123456:TEST-TOKEN"


def make(user: dict, auth_date: int, token: str = TOKEN) -> str:
    fields = {"auth_date": str(auth_date), "query_id": "AAH", "user": json.dumps(user, separators=(",", ":"))}
    check = "\n".join(f"{k}={v}" for k, v in sorted(fields.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    fields["hash"] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(fields)


class VerifyTests(unittest.TestCase):
    user = {"id": 42, "first_name": "Ali", "username": "ali_demo"}

    def test_valid(self):
        u = verify_init_data(make(self.user, int(time.time())), TOKEN)
        self.assertEqual(u["id"], 42)

    def test_wrong_token_rejected(self):
        with self.assertRaises(InvalidInitData):
            verify_init_data(make(self.user, int(time.time())), "other:token")

    def test_tampered_user_rejected(self):
        data = make(self.user, int(time.time())).replace("42", "43")
        with self.assertRaises(InvalidInitData):
            verify_init_data(data, TOKEN)

    def test_expired_rejected(self):
        with self.assertRaises(InvalidInitData):
            verify_init_data(make(self.user, int(time.time()) - 90000), TOKEN)

    def test_missing_hash_rejected(self):
        with self.assertRaises(InvalidInitData):
            verify_init_data("auth_date=1&user=%7B%7D", TOKEN)


if __name__ == "__main__":
    unittest.main()
