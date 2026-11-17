import os
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from auth import hash_password
from database import SessionLocal
from schemas import UserRole

DEMO_ACCOUNTS = (
    {
        "full_name": "Ayesha Rahman",
        "email": "citizen@smarttransit.com",
        "phone": "+8801000000001",
        "identity_number": "DEMO-CITIZEN-001",
        "password_env": "SMARTTRANSIT_DEMO_CITIZEN_PASSWORD",
        "role": UserRole.CITIZEN.value,
        "points": 80,
        "level": 1,
        "police_eligible": False,
        "driver_trained": False,
        "has_license": False,
    },
    {
        "full_name": "Dhaka Traffic Demo",
        "email": "police@smarttransit.com",
        "phone": "+8801000000002",
        "identity_number": "DEMO-POLICE-001",
        "password_env": "SMARTTRANSIT_DEMO_POLICE_PASSWORD",
        "role": UserRole.POLICE.value,
        "points": 1000,
        "level": 10,
        "police_eligible": True,
        "driver_trained": False,
        "has_license": False,
    },
    {
        "full_name": "Rafiq Hasan",
        "email": "driver@smarttransit.com",
        "phone": "+8801000000003",
        "identity_number": "DEMO-DRIVER-001",
        "password_env": "SMARTTRANSIT_DEMO_DRIVER_PASSWORD",
        "role": UserRole.DRIVER.value,
        "points": 120,
        "level": 2,
        "police_eligible": False,
        "driver_trained": True,
        "has_license": True,
    },
)


def main() -> None:
    if os.environ.get("SMARTTRANSIT_DEMO_MODE") != "1":
        raise SystemExit(
            "Demo seeding is disabled. Set SMARTTRANSIT_DEMO_MODE=1 for local demos only."
        )

    demo_passwords = {
        account["email"]: os.environ.get(account["password_env"])
        for account in DEMO_ACCOUNTS
    }
    missing_passwords = [
        account["password_env"]
        for account in DEMO_ACCOUNTS
        if not demo_passwords[account["email"]]
    ]
    if missing_passwords:
        raise SystemExit(
            "Set private local demo passwords for: " + ", ".join(missing_passwords)
        )

    ready_accounts = set()
    try:
        with SessionLocal.begin() as db:
            for account in DEMO_ACCOUNTS:
                existing = db.execute(
                    text(
                        """
                        SELECT id FROM users
                        WHERE email = :email OR nid_passport_number = :identity_number
                        """
                    ),
                    {
                        "email": account["email"],
                        "identity_number": account["identity_number"],
                    },
                ).mappings().all()
                existing_ids = {str(user["id"]) for user in existing}
                if len(existing_ids) > 1:
                    raise SystemExit(
                        f"Refusing to merge conflicting records for {account['email']}."
                    )

                if existing:
                    user_id = existing[0]["id"]
                    db.execute(
                        text(
                            """
                            UPDATE users
                            SET email = :email, full_name = :full_name, phone = :phone,
                                user_role = :user_role, password_hash = :password_hash
                            WHERE id = :id
                            """
                        ),
                        {
                            "id": user_id,
                            "email": account["email"],
                            "full_name": account["full_name"],
                            "phone": account["phone"],
                            "user_role": account["role"],
                            "password_hash": hash_password(demo_passwords[account["email"]]),
                        },
                    )
                else:
                    user_id = uuid4()
                    db.execute(
                        text(
                            """
                            INSERT INTO users
                                (id, full_name, email, phone, identity_type,
                                 nid_passport_number, user_role, password_hash, created_at)
                            VALUES
                                (:id, :full_name, :email, :phone, 'NID',
                                 :identity_number, :user_role, :password_hash, CURRENT_TIMESTAMP)
                            """
                        ),
                        {
                            "id": user_id,
                            "full_name": account["full_name"],
                            "email": account["email"],
                            "phone": account["phone"],
                            "identity_number": account["identity_number"],
                            "user_role": account["role"],
                            "password_hash": hash_password(demo_passwords[account["email"]]),
                        },
                    )
                db.execute(
                    text(
                        """
                        INSERT INTO user_game_profiles
                            (user_id, total_points, current_level,
                             is_police_eligible, is_driver_trained, has_gov_license,
                             updated_at)
                        VALUES
                            (:user_id, :points, :level, :police_eligible,
                             :driver_trained, :has_license, CURRENT_TIMESTAMP)
                        ON DUPLICATE KEY UPDATE
                            total_points = :points,
                            current_level = :level,
                            is_police_eligible = :police_eligible,
                            is_driver_trained = :driver_trained,
                            has_gov_license = :has_license,
                            updated_at = CURRENT_TIMESTAMP
                        """
                    ),
                    {
                        "user_id": user_id,
                        "points": account["points"],
                        "level": account["level"],
                        "police_eligible": account["police_eligible"],
                        "driver_trained": account["driver_trained"],
                        "has_license": account["has_license"],
                    },
                )
                ready_accounts.add(account["email"])
    except OperationalError as exc:
        raise SystemExit(
            "Cannot connect to MySQL. Start MySQL in XAMPP, create smarttransit_db, "
            "and check DATABASE_URL."
        ) from exc
    except SQLAlchemyError as exc:
        raise SystemExit(
            "Could not create demo accounts. Apply the MySQL migration first. Details: "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc

    for account in DEMO_ACCOUNTS:
        if account["email"] in ready_accounts:
            print(f"ready (password/profile reset): {account['email']}")
    print("Demo accounts are for local testing only; do not use them in production.")


if __name__ == "__main__":
    main()
