import app.models

from app.db.base import Base
from app.db.session import database_status, get_engine


def initialize_schema():
    engine = get_engine()

    # Create tables that do not already exist.
    Base.metadata.create_all(bind=engine)

    status = database_status()

    print("Database schema initialization complete.")
    print(f"Connected: {status['connected']}")
    print(f"Schema ready: {status['schema_ready']}")
    print(f"Tables: {status['tables']}")
    print(f"Missing tables: {status['missing_tables']}")
    print(f"Missing columns: {status['missing_columns']}")

    if not status["schema_ready"]:
        raise SystemExit("The required database schema is still incomplete.")


if __name__ == "__main__":
    initialize_schema()
