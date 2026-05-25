from __future__ import annotations

from cryptography.fernet import Fernet

from src.core.config import settings


def get_fernet() -> Fernet:
    key = settings.secret_encryption_key
    if not key:
        raise RuntimeError("SECRET_ENCRYPTION_KEY not set")
    return Fernet(key.encode())


def encrypt_value(value: str) -> bytes:
    f = get_fernet()
    return f.encrypt(value.encode())


def decrypt_value(encrypted: bytes) -> str:
    f = get_fernet()
    return f.decrypt(encrypted).decode()
