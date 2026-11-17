import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from config import load_environment

load_environment()

TOKEN_LIFETIME_SECONDS = 60 * 60 * 12
PASSWORD_ITERATIONS = 600_000
TOKEN_SECRET = os.environ.get("SMARTTRANSIT_SECRET_KEY")
if not TOKEN_SECRET:
    TOKEN_SECRET = secrets.token_urlsafe(48)
    if os.environ.get("APP_ENV") == "production":
        raise RuntimeError("SMARTTRANSIT_SECRET_KEY is required in production.")

bearer_scheme = HTTPBearer(auto_error=False)


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS
    )
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${_b64encode(salt)}${_b64encode(digest)}"


def verify_password(password: str, stored_hash: str | None) -> bool:
    if not stored_hash:
        return False
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), _b64decode(salt), int(iterations)
        )
        return hmac.compare_digest(actual, _b64decode(expected))
    except (ValueError, TypeError):
        return False


DUMMY_PASSWORD_HASH = hash_password("invalid-login-timing-only")


def create_access_token(user_id: UUID) -> str:
    now = int(time.time())
    header = _b64encode(b'{"alg":"HS256","typ":"JWT"}')
    payload = _b64encode(
        json.dumps(
            {"sub": str(user_id), "iat": now, "exp": now + TOKEN_LIFETIME_SECONDS},
            separators=(",", ":"),
        ).encode("utf-8")
    )
    message = f"{header}.{payload}".encode("ascii")
    signature = hmac.new(TOKEN_SECRET.encode("utf-8"), message, hashlib.sha256).digest()
    return f"{header}.{payload}.{_b64encode(signature)}"


def decode_access_token(token: str) -> UUID:
    try:
        header, payload, signature = token.split(".")
        message = f"{header}.{payload}".encode("ascii")
        expected = hmac.new(
            TOKEN_SECRET.encode("utf-8"), message, hashlib.sha256
        ).digest()
        if not hmac.compare_digest(expected, _b64decode(signature)):
            raise ValueError("Invalid signature")
        header_claims = json.loads(_b64decode(header))
        if header_claims.get("alg") != "HS256" or header_claims.get("typ") != "JWT":
            raise ValueError("Invalid token header")
        claims = json.loads(_b64decode(payload))
        if claims.get("exp", 0) <= int(time.time()):
            raise ValueError("Expired token")
        return UUID(claims["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Your session is invalid or expired. Please sign in again.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None


def get_current_user_id(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> UUID:
    token = (
        credentials.credentials
        if credentials is not None and credentials.scheme.lower() == "bearer"
        else request.cookies.get("smarttransit_session")
    )
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to continue.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return decode_access_token(token)
