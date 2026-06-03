"""Fernet symmetric encryption for secrets at rest (connection strings, credentials)."""

from __future__ import annotations

from cryptography.fernet import Fernet

from src.core.config import settings


def get_fernet() -> Fernet:
    """Build Fernet cipher from config key. Fail fast if key missing — no silent plaintext leaks."""
    key = settings.secret_encryption_key
    if not key:
        raise RuntimeError("SECRET_ENCRYPTION_KEY not set")
    return Fernet(key.encode())


def encrypt_value(value: str) -> bytes:
    """Encrypt a plaintext string -> Fernet token bytes."""
    f = get_fernet()
    return f.encrypt(value.encode())


def decrypt_value(encrypted: bytes) -> str:
    """Decrypt Fernet token bytes -> plaintext. Raises InvalidToken if tampered."""
    f = get_fernet()
    return f.decrypt(encrypted).decode()
