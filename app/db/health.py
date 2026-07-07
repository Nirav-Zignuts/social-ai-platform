from sqlalchemy import text

from app.db.session import engine


def check_database_connection() -> None:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))