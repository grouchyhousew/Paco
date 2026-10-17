"""Telegram Mini App initData verification."""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl


class TelegramAuthError(ValueError):
    pass


def validate_init_data(init_data: str, bot_token: str, max_age: int = 300) -> dict:
    if not init_data or not bot_token:
        raise TelegramAuthError("Telegram authentication is not configured")

    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", None)
    if not received_hash:
        raise TelegramAuthError("Missing Telegram signature")

    auth_date = values.get("auth_date")
    try:
        if abs(int(time.time()) - int(auth_date)) > max_age:
            raise TelegramAuthError("Telegram authentication expired")
    except (TypeError, ValueError) as exc:
        raise TelegramAuthError("Invalid Telegram auth date") from exc

    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", bot_token.encode(), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_hash, received_hash):
        raise TelegramAuthError("Invalid Telegram signature")

    if "user" not in values:
        raise TelegramAuthError("Telegram user is missing")
    try:
        user = json.loads(values["user"])
    except json.JSONDecodeError as exc:
        raise TelegramAuthError("Invalid Telegram user payload") from exc
    if not isinstance(user, dict) or not user.get("id"):
        raise TelegramAuthError("Invalid Telegram user")
    return user
