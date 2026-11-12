"""Seller secrets use a separately managed Fernet key; never derive it from JWT keys."""
from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException
from backend.app.core.config import settings


def cipher():
    try:
        return Fernet(settings.CREDENTIALS_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        raise HTTPException(503, "Seller credential encryption is not configured") from None


def encrypt_secret(value: str) -> str:
    return cipher().encrypt(value.encode()).decode()


def decrypt_secret(value: str) -> str:
    try:
        return cipher().decrypt(value.encode()).decode()
    except (InvalidToken, AttributeError):
        raise HTTPException(503, "Seller credentials could not be decrypted") from None
