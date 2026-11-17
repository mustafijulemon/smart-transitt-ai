import base64
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from config import load_environment

load_environment()

NONCE_LENGTH = 12


def _cipher() -> AESGCM:
    encoded_key = os.environ.get("SMARTTRANSIT_ENCRYPTION_KEY")
    if not encoded_key:
        raise RuntimeError(
            "SMARTTRANSIT_ENCRYPTION_KEY must be configured before using chat."
        )
    try:
        key = base64.urlsafe_b64decode(encoded_key + "=" * (-len(encoded_key) % 4))
    except (ValueError, TypeError) as exc:
        raise RuntimeError("SMARTTRANSIT_ENCRYPTION_KEY is not valid base64.") from exc
    if len(key) != 32:
        raise RuntimeError("SMARTTRANSIT_ENCRYPTION_KEY must decode to 32 bytes.")
    return AESGCM(key)


def validate_encryption_key() -> None:
    _cipher()


def encrypt_message(message: str) -> str:
    nonce = secrets.token_bytes(NONCE_LENGTH)
    encrypted = _cipher().encrypt(nonce, message.encode("utf-8"), None)
    payload = base64.urlsafe_b64encode(nonce + encrypted).decode("ascii")
    return f"v1:{payload}"


def decrypt_message(payload: str) -> str:
    version, encoded = payload.split(":", 1)
    if version != "v1":
        raise ValueError("Unsupported encrypted message version.")
    raw = base64.urlsafe_b64decode(encoded)
    if len(raw) <= NONCE_LENGTH:
        raise ValueError("Encrypted message is incomplete.")
    message = _cipher().decrypt(raw[:NONCE_LENGTH], raw[NONCE_LENGTH:], None)
    return message.decode("utf-8")
