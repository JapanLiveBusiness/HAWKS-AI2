"""Fail deployment before replacing the running app if Auth0 is incomplete."""

from pathlib import Path
import sys

import tomli

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from auth_policy import validate_auth_config


if __name__ == "__main__":
    try:
        with Path(sys.argv[1]).open("rb") as source:
            validate_auth_config(tomli.load(source))
    except Exception:
        # Configuration may contain secrets: never print payloads or exceptions.
        print("Auth0 configuration is missing or invalid; deployment stopped.", file=sys.stderr)
        raise SystemExit(1)
    print("Auth0 configuration and access policy validated.")
