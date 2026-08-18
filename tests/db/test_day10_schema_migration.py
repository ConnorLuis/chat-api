from sqlalchemy import (
    inspect,
    text,
)

from src.app.db.session import (
    build_engine,
    init_db,
)


def test_init_db_adds_caller_column_to_old_usage_table(
    tmp_path,
):
    database_path = (
        tmp_path
        / "day9_database.db"
    )
    engine = build_engine(
        f"sqlite:///{database_path}"
    )

    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    """
                    CREATE TABLE usage_records (
                        request_id VARCHAR(36)
                            PRIMARY KEY,
                        created_at DATETIME
                            NOT NULL
                    )
                    """
                )
            )

        init_db(engine)

        inspector = inspect(engine)

        columns = {
            item["name"]
            for item in inspector.get_columns(
                "usage_records"
            )
        }
        indexes = {
            item["name"]
            for item in inspector.get_indexes(
                "usage_records"
            )
        }

        assert "caller_key_id" in columns
        assert (
            "ix_usage_records_caller_created"
            in indexes
        )

    finally:
        engine.dispose()
