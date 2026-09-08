"""Copy the pre-Auth0 BET history into one verified Auth0 user's store."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from auth_session import AuthUser, user_bets_path
from bet_store import import_bets, load_bets


def migrate_legacy_bets(
    data_dir: Path,
    auth0_subject: str,
    *,
    apply: bool = False,
    merge: bool = False,
) -> tuple[Path, int]:
    source = Path(data_dir) / "bet_records.json"
    if not source.exists():
        raise FileNotFoundError(f"Legacy BET file not found: {source}")
    user = AuthUser(auth0_subject, "", "", True)
    target = user_bets_path(Path(data_dir), user)
    records = load_bets(source)

    if target.exists() and not merge:
        raise FileExistsError(
            "Target user already has BET data. Use --merge to preserve both histories."
        )
    if apply:
        _, imported_count = import_bets(target, records, replace=not merge)
        return target, imported_count
    return target, len(records)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preview or apply a legacy BET migration for one Auth0 subject."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("/opt/hawks-ai/data"))
    parser.add_argument("--auth0-sub", required=True, help="Exact Auth0 user_id/sub")
    parser.add_argument("--apply", action="store_true", help="Write the target file")
    parser.add_argument("--merge", action="store_true", help="Append only IDs not already present")
    args = parser.parse_args()

    target, count = migrate_legacy_bets(
        args.data_dir,
        args.auth0_sub,
        apply=args.apply,
        merge=args.merge,
    )
    mode = "applied" if args.apply else "dry-run"
    print(f"{mode}: records={count} target={target}")


if __name__ == "__main__":
    main()
