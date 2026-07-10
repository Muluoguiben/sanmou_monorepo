"""Inspect or explicitly grant a pending frame-bound operator request.

Examples:
  python3 -m pioneer_agent.app.operator_confirmation show \
    --request data/loop/operator_confirmation_request.json
  python3 -m pioneer_agent.app.operator_confirmation grant \
    --request data/loop/operator_confirmation_request.json --confirm
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from pioneer_agent.app.cli_utils import user_path
from pioneer_agent.executor.operator_confirmation import (
    JsonlOperatorConfirmationStore,
    OperatorConfirmationError,
    grant_operator_confirmation,
    load_operator_confirmation_request,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inspect or grant one pending live final-click confirmation."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    show = subparsers.add_parser("show", help="Print the exact active request.")
    show.add_argument("--request", type=user_path, required=True)

    grant = subparsers.add_parser(
        "grant",
        help="Append one explicit, short-lived grant copied from the active request.",
    )
    grant.add_argument("--request", type=user_path, required=True)
    grant.add_argument(
        "--confirm",
        action="store_true",
        help="Required explicit human acknowledgement; omission never grants.",
    )

    args = parser.parse_args(argv)
    try:
        request = load_operator_confirmation_request(Path(args.request))
        if args.command == "show":
            print(
                json.dumps(
                    request.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        if not args.confirm:
            parser.error("grant requires --confirm after reviewing the active request")
        confirmation = grant_operator_confirmation(request)
        store = JsonlOperatorConfirmationStore(
            Path(request.confirmation_store_path),
            max_ttl_seconds=request.confirmation_ttl_seconds,
        )
        store.append_grant(confirmation)
    except OperatorConfirmationError as exc:
        parser.error(str(exc))

    print(
        json.dumps(
            {
                "status": "granted",
                "request_id": request.request_id,
                "confirmation": confirmation.model_dump(mode="json"),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
