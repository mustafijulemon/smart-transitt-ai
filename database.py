import os
from uuid import UUID

from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from config import load_environment

load_environment()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "mysql+pymysql://root:@127.0.0.1:3306/smarttransit_db?charset=utf8mb4",
)

if os.environ.get("APP_ENV") == "production" and "DATABASE_URL" not in os.environ:
    raise RuntimeError("DATABASE_URL is required in production.")

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@event.listens_for(engine, "before_cursor_execute", retval=True)
def adapt_mysql_uuids(connection, cursor, statement, parameters, context, executemany):
    if connection.dialect.name not in {"mysql", "sqlite"}:
        return statement, parameters

    def convert(value):
        if isinstance(value, UUID):
            return str(value)
        if isinstance(value, dict):
            return {key: convert(item) for key, item in value.items()}
        if isinstance(value, (tuple, list)):
            return type(value)(convert(item) for item in value)
        return value

    return statement, convert(parameters)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
