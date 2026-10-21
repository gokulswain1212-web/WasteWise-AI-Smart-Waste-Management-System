from __future__ import annotations

import os
import re
import secrets
import string
from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError


BACKEND_DIR = Path(__file__).resolve().parent
ENV_PATH = BACKEND_DIR / ".env"
APP_USERNAME = "wastewise_app"
PASSWORD_ALPHABET = string.ascii_letters + string.digits


def main() -> None:
    config = dotenv_values(ENV_PATH)
    admin_url = config.get("MYSQL_ADMIN_URL")
    database_name = config.get("MYSQL_DATABASE", "wastewise")
    if not admin_url:
        raise SystemExit(
            "Set MYSQL_ADMIN_URL in backend/.env to the local MySQL admin connection."
        )
    if not re.fullmatch(r"[A-Za-z0-9_]+", str(database_name)):
        raise SystemExit("MYSQL_DATABASE may contain only letters, digits and underscores.")

    generated_password = "".join(
        secrets.choice(PASSWORD_ALPHABET) for _ in range(40)
    )
    engine = create_engine(
        str(admin_url),
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    f"CREATE DATABASE IF NOT EXISTS `{database_name}` "
                    "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
                )
            )
            connection.execute(
                text(
                    f"CREATE USER IF NOT EXISTS '{APP_USERNAME}'@'127.0.0.1' "
                    "IDENTIFIED BY :password"
                ),
                {"password": generated_password},
            )
            connection.execute(
                text(
                    f"ALTER USER '{APP_USERNAME}'@'127.0.0.1' "
                    "IDENTIFIED BY :password"
                ),
                {"password": generated_password},
            )
            connection.execute(
                text(
                    f"GRANT ALL PRIVILEGES ON `{database_name}`.* "
                    f"TO '{APP_USERNAME}'@'127.0.0.1'"
                )
            )
    except SQLAlchemyError as error:
        detail = str(getattr(error, "orig", error))
        raise SystemExit(
            f"MySQL setup failed ({type(error).__name__}: {detail}). Check the admin "
            "username, password, and database privileges in backend/.env."
        ) from error
    finally:
        engine.dispose()

    app_url = URL.create(
        "mysql+pymysql",
        username=APP_USERNAME,
        password=generated_password,
        host="127.0.0.1",
        port=3306,
        database=str(database_name),
        query={"charset": "utf8mb4"},
    )
    ENV_PATH.write_text(
        f"DATABASE_URL={app_url.render_as_string(hide_password=False)}\n",
        encoding="utf-8",
    )
    try:
        os.chmod(ENV_PATH, 0o600)
    except OSError:
        pass
    print(
        f"Created database '{database_name}' and restricted app account "
        f"'{APP_USERNAME}'. Admin credentials were removed from backend/.env."
    )
    print("Restart the backend, then run `python backend/import_data.py`.")


if __name__ == "__main__":
    main()
