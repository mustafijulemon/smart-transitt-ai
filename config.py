from pathlib import Path

from dotenv import load_dotenv

ENV_FILE = Path(__file__).with_name(".env")


def load_environment() -> None:
    load_dotenv(ENV_FILE)
