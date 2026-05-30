import base64
import json
from typing import Any

from Crypto.Cipher import AES
from Crypto.Util.Padding import pad, unpad

from door_service.constants import IV, KEY


def encrypt_json(obj: dict[str, Any]) -> str:
    text = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    encrypted = cipher.encrypt(pad(text, AES.block_size))
    return base64.b64encode(encrypted).decode("utf-8")


def decrypt_text(b64_text: str) -> str:
    cipher = AES.new(KEY, AES.MODE_CBC, IV)
    decoded = base64.b64decode(b64_text)
    plain = unpad(cipher.decrypt(decoded), AES.block_size)
    return plain.decode("utf-8")


def decode_jwt_payload(token: str) -> dict[str, Any] | None:
    try:
        parts = token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return json.loads(base64.urlsafe_b64decode(payload.encode("utf-8")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
