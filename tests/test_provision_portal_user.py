import csv
import tempfile
import unittest
from pathlib import Path

from provision_portal_user import load_roster


class PortalUserRosterTests(unittest.TestCase):
    def write_roster(self, rows, fields=("role", "full_name", "email", "phone")):
        temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(temporary_directory.cleanup)
        path = Path(temporary_directory.name) / "portal_users.csv"
        with path.open("w", newline="", encoding="utf-8") as roster_file:
            writer = csv.DictWriter(roster_file, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_loads_and_normalizes_roster_entries(self):
        path = self.write_roster(
            [
                {
                    "role": " police ",
                    "full_name": " Officer One ",
                    "email": "OFFICER@example.com",
                    "phone": " 01700000000 ",
                }
            ]
        )

        self.assertEqual(
            load_roster(path),
            [
                {
                    "role": "POLICE",
                    "full_name": "Officer One",
                    "email": "officer@example.com",
                    "phone": "01700000000",
                }
            ],
        )

    def test_rejects_password_column(self):
        fields = ("role", "full_name", "email", "phone", "password")
        path = self.write_roster(
            [
                {
                    "role": "POLICE",
                    "full_name": "Officer One",
                    "email": "officer@example.com",
                    "phone": "01700000000",
                    "password": "do-not-store",
                }
            ],
            fields,
        )

        with self.assertRaisesRegex(ValueError, "Do not add passwords"):
            load_roster(path)

    def test_rejects_duplicate_contact_details(self):
        path = self.write_roster(
            [
                {
                    "role": "POLICE",
                    "full_name": "Officer One",
                    "email": "officer@example.com",
                    "phone": "01700000000",
                },
                {
                    "role": "DRIVER",
                    "full_name": "Driver One",
                    "email": "OFFICER@example.com",
                    "phone": "01700000001",
                },
            ]
        )

        with self.assertRaisesRegex(ValueError, "Duplicate email or phone"):
            load_roster(path)


if __name__ == "__main__":
    unittest.main()
