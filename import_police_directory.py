import argparse
import posixpath
import re
import zipfile
from datetime import date
from xml.etree import ElementTree

from sqlalchemy import text

from database import engine

SOURCE_URL = "https://www.police.gov.bd/en/contacts_of_bangladesh_police_-pdf"
SOURCE_PUBLISHED_ON = date(2020, 10, 3)
NAMESPACES = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "relationships": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "package": "http://schemas.openxmlformats.org/package/2006/relationships",
}


def _column_index(cell_reference: str) -> int:
    letters = re.match(r"[A-Z]+", cell_reference.upper())
    if not letters:
        raise ValueError(f"Invalid spreadsheet cell reference: {cell_reference}")
    index = 0
    for character in letters.group():
        index = index * 26 + ord(character) - ord("A") + 1
    return index - 1


def _cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    if cell.attrib.get("t") == "inlineStr":
        return "".join(
            item.text or ""
            for item in cell.findall(".//main:t", NAMESPACES)
        ).strip()
    value = cell.find("main:v", NAMESPACES)
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return shared_strings[int(value.text)].strip()
    return value.text.strip()


def _workbook_sheets(archive: zipfile.ZipFile):
    workbook = ElementTree.fromstring(archive.read("xl/workbook.xml"))
    relationships = ElementTree.fromstring(
        archive.read("xl/_rels/workbook.xml.rels")
    )
    targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships.findall("package:Relationship", NAMESPACES)
    }
    shared_strings = []
    if "xl/sharedStrings.xml" in archive.namelist():
        strings_root = ElementTree.fromstring(
            archive.read("xl/sharedStrings.xml")
        )
        shared_strings = [
            "".join(
                item.text or ""
                for item in string.findall(".//main:t", NAMESPACES)
            )
            for string in strings_root.findall("main:si", NAMESPACES)
        ]

    for sheet in workbook.findall("main:sheets/main:sheet", NAMESPACES):
        relationship_id = sheet.attrib[
            f"{{{NAMESPACES['relationships']}}}id"
        ]
        target = targets[relationship_id]
        sheet_path = (
            target.lstrip("/")
            if target.startswith("/")
            else posixpath.normpath(posixpath.join("xl", target))
        )
        root = ElementTree.fromstring(archive.read(sheet_path))
        yield sheet.attrib["name"], root, shared_strings


def extract_officer_in_charge_contacts(workbook_path: str) -> list[dict]:
    records = []
    with zipfile.ZipFile(workbook_path) as archive:
        for sheet_name, root, shared_strings in _workbook_sheets(archive):
            unit_name = sheet_name
            for row in root.findall(".//main:sheetData/main:row", NAMESPACES):
                cells = {
                    _column_index(cell.attrib["r"]): _cell_value(
                        cell, shared_strings
                    )
                    for cell in row.findall("main:c", NAMESPACES)
                }
                first_cell = cells.get(0, "")
                unit_match = re.match(
                    r"\s*Unit/Office Name\s*:\s*(.+)", first_cell, re.IGNORECASE
                )
                if unit_match:
                    unit_name = unit_match.group(1).strip().rstrip(".")
                    continue

                designation = cells.get(1, "").strip()
                station_post = cells.get(2, "").strip()
                is_oc = re.search(r"\bO\.?\s*C\.?\b", station_post, re.IGNORECASE)
                is_station = re.search(
                    r"\b(thana|ps|police station)\b", station_post, re.IGNORECASE
                )
                if not is_oc or not is_station:
                    continue

                station_name = re.sub(
                    r"\bO\.?\s*C\.?\b\s*[:,.-]?\s*",
                    "",
                    station_post,
                    count=1,
                    flags=re.IGNORECASE,
                ).strip()
                if not station_name:
                    continue
                records.append(
                    {
                        "unit_name": unit_name,
                        "station_name": station_name,
                        "designation": designation or "Officer-in-Charge",
                        "official_phone": cells.get(3, ""),
                        "listed_phone": cells.get(4, ""),
                        "new_phone": cells.get(5, ""),
                        "email": cells.get(6, ""),
                    }
                )
    return records


def import_contacts(workbook_path: str) -> int:
    records = extract_officer_in_charge_contacts(workbook_path)
    if not records:
        raise ValueError("No station Officer-in-Charge records were found.")

    with engine.begin() as connection:
        connection.execute(
            text(
                """
                INSERT IGNORE INTO police_contacts
                    (unit_name, station_name, designation, official_phone,
                     listed_phone, new_phone, email, source_url,
                     source_published_on, verified)
                VALUES
                    (:unit_name, :station_name, :designation, :official_phone,
                     :listed_phone, :new_phone, :email, :source_url,
                     :source_published_on, FALSE)
                """
            ),
            [
                {
                    **record,
                    "source_url": SOURCE_URL,
                    "source_published_on": SOURCE_PUBLISHED_ON,
                }
                for record in records
            ],
        )
        total = connection.execute(
            text(
                """
                SELECT COUNT(*) FROM police_contacts
                WHERE source_url = :source_url
                """
            ),
            {"source_url": SOURCE_URL},
        ).scalar_one()
    return total


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Import Officer-in-Charge contacts from the official 2020 "
            "Bangladesh Police workbook as unverified records."
        )
    )
    parser.add_argument("workbook", help="Path to the downloaded police XLSX file")
    args = parser.parse_args()
    count = import_contacts(args.workbook)
    print(
        f"Loaded {count} directory records. All remain unverified; "
        "the source workbook was published on 2020-10-03."
    )


if __name__ == "__main__":
    main()
