from __future__ import annotations

import argparse
import json

from src.app.db.session import (
    get_session_factory,
    init_db,
)
from src.app.services import (
    APIKeyService,
)


def serialize_record(record) -> dict:
    return {
        "id": record.id,
        "prefix": record.prefix,
        "name": record.name,
        "status": record.status,
        "created_at": (
            record.created_at.isoformat()
        ),
        "revoked_at": (
            record.revoked_at.isoformat()
            if record.revoked_at
            is not None
            else None
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m src.app.auth"
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    create_parser = (
        subparsers.add_parser(
            "create",
            help="Create an API key",
        )
    )
    create_parser.add_argument(
        "--name",
        required=True,
    )

    list_parser = subparsers.add_parser(
        "list",
        help="List API key metadata",
    )
    list_parser.add_argument(
        "--limit",
        type=int,
        default=100,
    )
    list_parser.add_argument(
        "--offset",
        type=int,
        default=0,
    )

    revoke_parser = (
        subparsers.add_parser(
            "revoke",
            help="Revoke an API key",
        )
    )
    revoke_parser.add_argument(
        "key_id",
    )

    return parser


def main() -> None:
    args = build_parser().parse_args()

    init_db()

    with get_session_factory()() as session:
        service = APIKeyService(session)

        if args.command == "create":
            created = service.create_key(
                name=args.name
            )

            payload = {
                "id": created.id,
                "api_key": created.api_key,
                "prefix": created.prefix,
                "name": created.name,
                "status": created.status,
                "created_at": (
                    created
                    .created_at
                    .isoformat()
                ),
                "warning": (
                    "The plaintext API key "
                    "is returned only once."
                ),
            }

        elif args.command == "list":
            records = service.list_keys(
                limit=args.limit,
                offset=args.offset,
            )

            payload = {
                "items": [
                    serialize_record(record)
                    for record in records
                ]
            }

        elif args.command == "revoke":
            record = service.revoke_key(
                args.key_id
            )

            payload = serialize_record(
                record
            )

        else:
            raise AssertionError(
                "Unsupported command"
            )

    print(
        json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
