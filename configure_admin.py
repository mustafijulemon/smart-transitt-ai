import argparse
import getpass
import re
from pathlib import Path

from auth import hash_password
from schemas import validate_email_address

ENV_FILE = Path(__file__).with_name(".env")
MIN_ADMIN_PASSWORD_LENGTH = 14
ADMIN_KEYS = {
    "SMARTTRANSIT_ADMIN_EMAIL",
    "SMARTTRANSIT_ADMIN_PASSWORD_HASH",
}


def update_admin_environment(email: str, password_hash: str) -> None:
    existing_lines = ENV_FILE.read_text(encoding="utf-8").splitlines()
    updated_lines = []
    replaced = set()
    for line in existing_lines:
        key = line.partition("=")[0].strip()
        if key in ADMIN_KEYS:
            if key not in replaced:
                value = email if key == "SMARTTRANSIT_ADMIN_EMAIL" else password_hash
                updated_lines.append(f"{key}={value}")
                replaced.add(key)
        else:
            updated_lines.append(line)
    for key in ADMIN_KEYS - replaced:
        value = email if key == "SMARTTRANSIT_ADMIN_EMAIL" else password_hash
        updated_lines.append(f"{key}={value}")
    ENV_FILE.write_text("\n".join(updated_lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Set the SmartTransit admin login in the local .env file."
    )
    parser.add_argument("--email", default="admin@example.com")
    args = parser.parse_args()
    try:
        email = validate_email_address(args.email)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    password = getpass.getpass(
        f"Choose a private admin password (at least {MIN_ADMIN_PASSWORD_LENGTH} characters): "
    )
    if len(password) < MIN_ADMIN_PASSWORD_LENGTH or len(password) > 128:
        raise SystemExit(
            f"Admin password must be between {MIN_ADMIN_PASSWORD_LENGTH} and 128 characters."
        )
    if password != getpass.getpass("Confirm admin password: "):
        raise SystemExit("Passwords do not match.")

    update_admin_environment(email, hash_password(password))
    print(f"Admin login configured for {email}. The password is stored as a hash.")
    print("Restart the SmartTransit server before signing in at /admin.")


if __name__ == "__main__":
    main()
