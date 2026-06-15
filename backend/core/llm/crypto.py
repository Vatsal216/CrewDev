import os
import json
import base64
import hashlib
from pathlib import Path

from cryptography.fernet import Fernet

_SECRET_FILE = Path(__file__).resolve().parent.parent.parent / ".app_secret"


def _get_secret() -> str:
    secret = os.environ.get("APP_SECRET")
    if secret:
        return secret
    if _SECRET_FILE.exists():
        return _SECRET_FILE.read_text().strip()
    generated = base64.urlsafe_b64encode(os.urandom(32)).decode()
    _SECRET_FILE.write_text(generated)
    return generated


def _fernet() -> Fernet:
    raw = _get_secret().encode()
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def encrypt(data: dict) -> str:
    return _fernet().encrypt(json.dumps(data).encode()).decode()


def decrypt(token: str) -> dict:
    return json.loads(_fernet().decrypt(token.encode()).decode())


def mask(secret: str) -> str:
    if not secret:
        return ""
    if len(secret) <= 7:
        # head(3)+tail(4) would reveal a <=7 char secret entirely; show only the tail.
        return "…" + secret[-2:]
    return secret[:3] + "…" + secret[-4:]
