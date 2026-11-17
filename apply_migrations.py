from pathlib import Path

from sqlalchemy import text
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from database import engine

MIGRATION_DIR = Path(__file__).with_name("migrations_mysql")


def migration_statements(contents: str) -> list[str]:
    statements = []
    for statement in contents.split(";"):
        sql = "\n".join(
            line for line in statement.splitlines()
            if not line.lstrip().startswith("--")
        ).strip()
        if sql:
            statements.append(sql)
    return statements


def main() -> None:
    if engine.dialect.name != "mysql":
        raise SystemExit(
            "This setup targets a fresh XAMPP MySQL database. "
            "Set DATABASE_URL to a mysql+pymysql connection first."
        )

    migrations = sorted(MIGRATION_DIR.glob("*.sql"))
    if not migrations:
        raise SystemExit(f"No MySQL migrations found in {MIGRATION_DIR}")

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS smarttransit_schema_migrations (
                        migration_name VARCHAR(255) PRIMARY KEY,
                        applied_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                    ) ENGINE=InnoDB
                    """
                )
            )

        for migration in migrations:
            with engine.begin() as connection:
                exists = connection.execute(
                    text(
                        """
                        SELECT 1 FROM smarttransit_schema_migrations
                        WHERE migration_name = :name
                        """
                    ),
                    {"name": migration.name},
                ).first()
                if exists:
                    print(f"already applied: {migration.name}")
                    continue

                for statement in migration_statements(
                    migration.read_text(encoding="utf-8")
                ):
                    connection.exec_driver_sql(statement)
                connection.execute(
                    text(
                        """
                        INSERT INTO smarttransit_schema_migrations (migration_name)
                        VALUES (:name)
                        """
                    ),
                    {"name": migration.name},
                )
            print(f"applied: {migration.name}")
    except OperationalError as exc:
        raise SystemExit(
            "Cannot connect to MySQL. Start MySQL in XAMPP, create the "
            "smarttransit_db database, and check DATABASE_URL."
        ) from exc
    except SQLAlchemyError as exc:
        raise SystemExit(
            "MySQL migration failed. Use an empty smarttransit_db database "
            "for this fresh setup. Details: "
            f"{exc.__class__.__name__}: {exc}"
        ) from exc


if __name__ == "__main__":
    main()
