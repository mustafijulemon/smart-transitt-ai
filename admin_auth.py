import os
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException, Request, status

from auth import decode_access_token

ADMIN_COOKIE_NAME = "smarttransit_admin_session"


def admin_configuration() -> tuple[str | None, str | None]:
    email = os.environ.get("SMARTTRANSIT_ADMIN_EMAIL", "").strip().lower() or None
    password_hash = os.environ.get("SMARTTRANSIT_ADMIN_PASSWORD_HASH", "").strip() or None
    return email, password_hash


def admin_subject(email: str) -> UUID:
    return uuid5(NAMESPACE_URL, f"smarttransit-admin:{email.casefold()}")


def require_admin(request: Request) -> str:
    email, password_hash = admin_configuration()
    if email is None or password_hash is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin login is not configured. Run configure_admin.py locally.",
        )

    token = request.cookies.get(ADMIN_COOKIE_NAME)
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin sign-in is required.",
        )
    try:
        authenticated_subject = decode_access_token(token)
    except HTTPException:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin sign-in is required.",
        ) from None
    if authenticated_subject != admin_subject(email):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This session is not an administrator session.",
        )
    return email
