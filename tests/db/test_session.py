from sqlalchemy import inspect
from sqlalchemy.engine import Engine


def test_database_schema_is_created(
    db_engine: Engine,
):
    table_names = set(
        inspect(db_engine).get_table_names()
    )

    assert table_names == {
        "conversations",
        "messages",
        "usage_costs",
        "usage_records",
    }


def test_sqlite_foreign_keys_are_enabled(
    db_engine: Engine,
):
    with db_engine.connect() as connection:
        enabled = connection.exec_driver_sql(
            "PRAGMA foreign_keys"
        ).scalar_one()

    assert enabled == 1
