import argparse
import csv
import getpass
import re
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from auth import hash_password
from database import SessionLocal
from schemas import UserRole

ROSTER_FIELDS = {"role", "full_name", "email", "phone"}


def validate_account(role: str, full_name: str, email: str, phone: str) -> dict:
    role = role.strip().upper()
    full_name = full_name.strip()
    email = email.strip().lower()
    phone = phone.strip()
    if role not in {UserRole.POLICE.value, UserRole.DRIVER.value}:
        raise ValueError("Role must be POLICE or DRIVER.")
    if len(full_name) < 2:
        raise ValueError("Enter a valid full name.")
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise ValueError("Enter a valid email address.")
    if len(phone) < 7 or len(phone) > 30:
        raise ValueError("Enter a valid phone number.")
    return {
        "role": role,
        "full_name": full_name,
        "email": email,
        "phone": phone,
    }


def load_roster(path: Path) -> list[dict]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as roster_file:
            reader = csv.DictReader(roster_file)
            if not reader.fieldnames or set(reader.fieldnames) != ROSTER_FIELDS:
                raise ValueError(
                    "Roster must have exactly these columns: "
                    "role, full_name, email, phone. Do not add passwords."
                )
            accounts = []
            seen_emails = set()
            seen_phones = set()
            for row_number, row in enumerate(reader, start=2):
                account = validate_account(
                    row.get("role") or "",
                    row.get("full_name") or "",
                    row.get("email") or "",
                    row.get("phone") or "",
                )
                if account["email"] in seen_emails or account["phone"] in seen_phones:
                    raise ValueError(f"Duplicate email or phone on row {row_number}.")
                seen_emails.add(account["email"])
                seen_phones.add(account["phone"])
                accounts.append(account)
    except (OSError, csv.Error, UnicodeError) as exc:
        raise ValueError(f"Could not read roster file '{path}': {exc}") from exc

    if not accounts:
        raise ValueError("The roster file has no accounts.")
    return accounts


def choose_account(accounts: list[dict]) -> dict:
    for index, account in enumerate(accounts, start=1):
        print(f"{index}. {account['role']} — {account['full_name']} ({account['email']})")
    choice = input("Choose the account number to create (or Q to cancel): ").strip()
    if choice.lower() == "q":
        raise SystemExit("Cancelled; no account was created.")
    try:
        selected = int(choice)
    except ValueError as exc:
        raise SystemExit("Enter a listed account number, or Q to cancel.") from exc
    if selected < 1 or selected > len(accounts):
        raise SystemExit("Choose a listed account number.")
    return accounts[selected - 1]


def prompt_account() -> dict:
    try:
        return validate_account(
            input("Portal role (POLICE/DRIVER): "),
            input("Full name: "),
            input("Work email: "),
            input("Work phone: "),
        )
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def provision_account(account: dict, password: str) -> None:
    user_id = uuid4()
    is_police = account["role"] == UserRole.POLICE.value
    with SessionLocal.begin() as db:
        duplicate = db.execute(
            text("SELECT 1 FROM users WHERE email = :email OR phone = :phone LIMIT 1"),
            {"email": account["email"], "phone": account["phone"]},
        ).first()
        if duplicate:
            raise SystemExit("That email or phone number is already registered.")
        db.execute(
            text(
                """
                INSERT INTO users
                    (id, full_name, email, phone, user_role, password_hash, created_at)
                VALUES
                    (:id, :full_name, :email, :phone, :role, :password_hash, CURRENT_TIMESTAMP)
                """
            ),
            {
                "id": user_id,
                "full_name": account["full_name"],
                "email": account["email"],
                "phone": account["phone"],
                "role": account["role"],
                "password_hash": hash_password(password),
            },
        )
        db.execute(
            text(
                """
                INSERT INTO user_game_profiles
                    (user_id, total_points, current_level, is_police_eligible,
                     is_driver_trained, has_gov_license, updated_at)
                VALUES
                    (:user_id, 0, 1, :is_police, :is_driver, :is_driver, CURRENT_TIMESTAMP)
                """
            ),
            {
                "user_id": user_id,
                "is_police": is_police,
                "is_driver": account["role"] == UserRole.DRIVER.value,
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a verified Police or Driver portal account."
    )
    parser.add_argument(
        "--file",
        type=Path,
        help="Choose one account from a private CSV roster.",
    )
    args = parser.parse_args()

    try:
        account = choose_account(load_roster(args.file)) if args.file else prompt_account()
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc

    password = getpass.getpass("Initial password (at least 10 characters): ")
    if len(password) < 10 or len(password) > 128:
        raise SystemExit("Password must be between 10 and 128 characters.")
    if password != getpass.getpass("Confirm password: "):
        raise SystemExit("Passwords do not match.")

    provision_account(account, password)
    print(f"Created {account['role']} portal account for {account['email']}.")
    print("Share the initial password with the account holder privately.")


if __name__ == "__main__":
    main()
