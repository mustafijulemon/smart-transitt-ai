import base64
import os
import secrets
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from auth import hash_password

os.environ.setdefault("SMARTTRANSIT_SECRET_KEY", secrets.token_urlsafe(48))
os.environ.setdefault(
    "SMARTTRANSIT_ENCRYPTION_KEY",
    base64.urlsafe_b64encode(secrets.token_bytes(32)).decode("ascii"),
)

from database import adapt_mysql_uuids, get_db
from main import app


class PortalPrivacyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        from sqlalchemy import event

        event.listen(
            cls.engine,
            "before_cursor_execute",
            adapt_mysql_uuids,
            retval=True,
        )
        with cls.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE users (
                        id TEXT PRIMARY KEY, full_name TEXT NOT NULL,
                        email TEXT NOT NULL UNIQUE, phone TEXT NOT NULL UNIQUE,
                        profile_image_url TEXT, identity_type TEXT,
                        nid_passport_number TEXT, user_role TEXT NOT NULL,
                        password_hash TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE user_game_profiles (
                        user_id TEXT PRIMARY KEY, total_points INTEGER NOT NULL,
                        current_level INTEGER NOT NULL, is_police_eligible BOOLEAN NOT NULL,
                        is_driver_trained BOOLEAN NOT NULL, has_gov_license BOOLEAN NOT NULL,
                        driver_rating NUMERIC, completed_trips INTEGER NOT NULL DEFAULT 0,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE chat_messages (
                        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
                        portal_role TEXT NOT NULL, message_role TEXT NOT NULL,
                        encrypted_content TEXT NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE police_stations (
                        id INTEGER PRIMARY KEY, name TEXT, address TEXT, area TEXT,
                        phone TEXT, latitude FLOAT, longitude FLOAT, verified BOOLEAN
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE emergency_faqs (
                        id INTEGER PRIMARY KEY, category TEXT, question TEXT,
                        answer TEXT, keywords TEXT, verified BOOLEAN,
                        active BOOLEAN
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE emergency_hotlines (
                        id INTEGER PRIMARY KEY, code TEXT, service_name TEXT,
                        phone_number TEXT, situations TEXT, keywords TEXT,
                        source_url TEXT, source_published_on DATE,
                        verified BOOLEAN, active BOOLEAN
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE police_contacts (
                        id INTEGER PRIMARY KEY, unit_name TEXT, station_name TEXT,
                        designation TEXT, official_phone TEXT, listed_phone TEXT,
                        new_phone TEXT, email TEXT, source_url TEXT,
                        source_published_on DATE, verified BOOLEAN
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO emergency_faqs
                        (id, category, question, answer, keywords, verified, active)
                    VALUES
                        (1, 'theft', 'Phone stolen?', 'IMEI সংরক্ষণ করুন।',
                         'মোবাইল|ফোন চুরি|stolen phone', FALSE, TRUE),
                        (2, 'fire', 'Fire?', '৯৯৯-এ কল করুন; ১০২ যাচাই বাকি।',
                         'fire|আগুন', TRUE, TRUE)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO police_contacts
                        (id, unit_name, station_name, designation,
                         official_phone, listed_phone, new_phone, email,
                         source_url, source_published_on, verified)
                    VALUES
                        (1, 'DMP', 'Ramna Model Thana', 'Inspector',
                         '49350468', '01713373125', '01320-039492', '',
                         'https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf',
                         '2020-10-03', FALSE)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO emergency_hotlines
                        (id, code, service_name, phone_number, situations,
                         keywords, source_url, source_published_on, verified, active)
                    VALUES
                        (1, 'national-emergency', 'জাতীয় জরুরি সেবা', '999',
                         'জরুরি সহায়তা', '999|জরুরি', 'https://bangladesh.gov.bd/',
                         NULL, TRUE, TRUE),
                        (2, 'fire-service', 'ফায়ার সার্ভিস', '102', 'আগুন',
                         'আগুন|fire', 'https://bangladesh.gov.bd/', NULL, FALSE, TRUE)
                    """
                )
            )
            connection.execute(
                text(
                    """
                    CREATE TABLE bus_observations (
                        id TEXT PRIMARY KEY, reporter_id TEXT, status TEXT
                    )
                    """
                )
            )
        cls.Session = sessionmaker(bind=cls.engine, expire_on_commit=False)

    @classmethod
    def tearDownClass(cls):
        app.dependency_overrides.clear()
        cls.engine.dispose()

    def setUp(self):
        def override_get_db():
            db = self.Session()
            try:
                yield db
            finally:
                db.close()

        self.Session = type(self).Session
        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)

    def tearDown(self):
        self.client.close()
        with self.engine.begin() as connection:
            connection.execute(text("DELETE FROM chat_messages"))
            connection.execute(text("DELETE FROM police_stations"))
            connection.execute(text("DELETE FROM user_game_profiles"))
            connection.execute(text("DELETE FROM users"))

    def register(self, email="citizen@example.com"):
        return self.client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Test Citizen",
                "email": email,
                "phone": "+8801700000001" if email == "citizen@example.com" else "+8801700000002",
                "password": "a-strong-password",
            },
        )

    def test_registration_uses_private_cookie_and_chat_is_encrypted(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["user"]["user_role"], "CITIZEN")
        self.assertNotIn("access_token", response.json())
        self.assertNotIn("nid_passport_number", response.json()["user"])
        self.assertIn("httponly", response.headers["set-cookie"].lower())
        self.assertIn("samesite=strict", response.headers["set-cookie"].lower())
        self.assertEqual(
            self.client.get("/api/v1/auth/session").json()["user"]["id"],
            response.json()["user"]["id"],
        )

        chat = self.client.post(
            "/api/v1/chat/messages",
            json={"message": "জরুরি অবস্থায় কী করব?"},
        )
        self.assertEqual(chat.status_code, 201)
        self.assertIn("৯৯৯", chat.json()["reply"])
        with self.engine.connect() as connection:
            stored = connection.execute(
                text("SELECT encrypted_content FROM chat_messages")
            ).scalars().all()
        self.assertEqual(len(stored), 2)
        self.assertNotIn("জরুরি", "".join(stored))

        history = self.client.get("/api/v1/chat/history")
        self.assertEqual(len(history.json()["messages"]), 2)
        self.assertEqual(history.json()["messages"][0]["content"], "জরুরি অবস্থায় কী করব?")

    def test_nearby_lookup_uses_verified_local_stations(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.text)
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO police_stations
                        (id, name, address, area, phone, latitude, longitude, verified)
                    VALUES
                        (1, 'Nearby Station', 'Verified address', 'Area A',
                         '999', 23.71, 90.40, TRUE),
                        (2, 'Far Station', 'Another verified address', 'Area B',
                         '999', 23.90, 90.60, TRUE)
                    """
                )
            )
        result = self.client.post(
            "/api/v1/chat/messages",
            json={
                "message": "আমার নিকটস্থ থানা কোথায়?",
                "latitude": 23.70,
                "longitude": 90.40,
            },
        )
        self.assertEqual(result.status_code, 201)
        self.assertEqual(result.json()["nearby_stations"][0]["name"], "Nearby Station")
        history = self.client.get("/api/v1/chat/history").json()["messages"]
        self.assertNotIn("23.70", " ".join(message["content"] for message in history))

    def test_chat_answers_from_emergency_faq(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.text)

        theft = self.client.post(
            "/api/v1/chat/messages",
            json={"message": "আমার মোবাইল ফোন চুরি হয়েছে"},
        )
        self.assertEqual(theft.status_code, 201)
        self.assertIn("IMEI", theft.json()["reply"])

        fire = self.client.post(
            "/api/v1/chat/messages",
            json={"message": "fire"},
        )
        self.assertEqual(fire.status_code, 201)
        self.assertIn("৯৯৯", fire.json()["reply"])
        self.assertIn("যাচাই বাকি", fire.json()["reply"])

    def test_emergency_contacts_expose_verification_status(self):
        response = self.client.get("/api/v1/emergency/contacts")
        self.assertEqual(response.status_code, 200)
        contacts = {
            contact["code"]: contact for contact in response.json()["contacts"]
        }
        self.assertTrue(contacts["national-emergency"]["verified"])
        self.assertFalse(contacts["fire-service"]["verified"])

    def test_old_police_contacts_are_disclosed_as_unverified(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.text)
        result = self.client.post(
            "/api/v1/chat/messages",
            json={"message": "Ramna thana phone number"},
        )
        self.assertEqual(result.status_code, 201)
        self.assertIn("২০২০ সালের ডিরেক্টরি", result.json()["reply"])
        self.assertIn("যাচাই করা হয়নি", result.json()["reply"])
        self.assertIn("49350468", result.json()["reply"])

    def test_citizen_cannot_self_assign_staff_portal(self):
        response = self.register()
        self.assertEqual(response.status_code, 201, response.text)
        user_id = response.json()["user"]["id"]
        promotion = self.client.post(
            "/api/v1/user/promote-to-police",
            json={"user_id": user_id},
        )
        self.assertEqual(promotion.status_code, 403)

        queue = self.client.get(
            "/api/v1/police/observations",
            params={"user_id": user_id},
        )
        self.assertEqual(queue.status_code, 403)

    def test_staff_account_creation_requires_admin_session(self):
        admin_settings = {
            "SMARTTRANSIT_ADMIN_EMAIL": "admin@example.com",
            "SMARTTRANSIT_ADMIN_PASSWORD_HASH": hash_password(
                "a-private-admin-password"
            ),
        }
        account = {
            "user_role": "POLICE",
            "full_name": "Verified Officer",
            "email": "officer@example.com",
            "phone": "+8801700000101",
            "password": "a-private-staff-password",
        }
        with patch.dict(os.environ, admin_settings):
            unauthorized = self.client.post("/api/v1/admin/staff", json=account)
            self.assertEqual(unauthorized.status_code, 401)

            wrong_password = self.client.post(
                "/api/v1/admin/login",
                json={
                    "email": "admin@example.com",
                    "password": "wrong-admin-password",
                },
            )
            self.assertEqual(wrong_password.status_code, 401)

            login = self.client.post(
                "/api/v1/admin/login",
                json={
                    "email": "admin@example.com",
                    "password": "a-private-admin-password",
                },
            )
            self.assertEqual(login.status_code, 200, login.text)
            self.assertIn("smarttransit_admin_session", login.headers["set-cookie"])

            created = self.client.post("/api/v1/admin/staff", json=account)
            self.assertEqual(created.status_code, 201, created.text)
            self.assertEqual(created.json()["user"]["user_role"], "POLICE")
            with self.engine.connect() as connection:
                stored = connection.execute(
                    text(
                        """
                        SELECT u.user_role, u.password_hash, p.is_police_eligible
                        FROM users AS u
                        JOIN user_game_profiles AS p ON p.user_id = u.id
                        WHERE u.email = 'officer@example.com'
                        """
                    )
                ).mappings().one()
            self.assertEqual(stored["user_role"], "POLICE")
            self.assertNotEqual(stored["password_hash"], account["password"])
            self.assertTrue(stored["is_police_eligible"])

    def test_staff_account_creation_rejects_citizen_role(self):
        admin_settings = {
            "SMARTTRANSIT_ADMIN_EMAIL": "admin@example.com",
            "SMARTTRANSIT_ADMIN_PASSWORD_HASH": hash_password(
                "a-private-admin-password"
            ),
        }
        with patch.dict(os.environ, admin_settings):
            login = self.client.post(
                "/api/v1/admin/login",
                json={
                    "email": "admin@example.com",
                    "password": "a-private-admin-password",
                },
            )
            self.assertEqual(login.status_code, 200, login.text)
            response = self.client.post(
                "/api/v1/admin/staff",
                json={
                    "user_role": "CITIZEN",
                    "full_name": "Not Staff",
                    "email": "not-staff@example.com",
                    "phone": "+8801700000102",
                    "password": "a-private-staff-password",
                },
            )
            self.assertEqual(response.status_code, 422)

    def test_chat_requires_authentication_and_history_is_user_scoped(self):
        unauthenticated = TestClient(app)
        response = unauthenticated.post(
            "/api/v1/chat/messages",
            json={"message": "hello"},
        )
        self.assertEqual(response.status_code, 401)
        unauthenticated.close()

        first = self.register()
        self.client.post("/api/v1/chat/messages", json={"message": "first user's question"})
        self.assertEqual(first.status_code, 201, first.text)
        first_id = first.json()["user"]["id"]

        second_client = TestClient(app)
        second_client.post(
            "/api/v1/auth/register",
            json={
                "full_name": "Second Citizen",
                "email": "second@example.com",
                "phone": "+8801700000003",
                "password": "another-strong-password",
            },
        )
        second_user = second_client.get("/api/v1/auth/me").json()
        self.assertNotEqual(first_id, second_user["id"])
        history = second_client.get("/api/v1/chat/history")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["messages"], [])
        second_client.close()


if __name__ == "__main__":
    unittest.main()
