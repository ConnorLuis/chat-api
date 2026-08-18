from __future__ import annotations

from .session import get_engine, init_db


def main() -> None:
    engine = get_engine()
    init_db(engine)

    database_url = engine.url.render_as_string(
        hide_password=True,
    )

    print(
        f"database initialized: {database_url}"
    )


if __name__ == "__main__":
    main()
