"""Thread-safe, atomic persistence for BET records."""

from __future__ import annotations

from copy import deepcopy
from contextlib import contextmanager
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
from typing import Any, Iterable
from filelock import FileLock


class BetStoreError(RuntimeError):
    """Base error for BET persistence failures."""


class BetNotFoundError(BetStoreError):
    """Raised when a requested BET record does not exist."""


class DuplicateBetError(BetStoreError):
    """Raised when a BET record ID is already in use."""


_STORE_LOCK = RLock()


@lru_cache(maxsize=128)
def _file_lock(path: str) -> FileLock:
    return FileLock(path + ".lock", timeout=15)


@contextmanager
def _locked(path: Path):
    # Atomic replacement alone does not serialize read-modify-write across workers.
    with _STORE_LOCK:
        path = Path(path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with _file_lock(str(path)):
                yield
        except (OSError, TimeoutError) as exc:
            raise BetStoreError(f"BETデータをロックできません: {exc}") from exc


def _manual_identity(record):
    amount = record.get("bet_amount")
    if amount is None:
        amount = abs(float(record.get("bet_units") or 0)) * 10000
    return (
        *(str(record.get(key) or "").strip() for key in ("date", "time", "team", "opponent")),
        float(amount), float(record.get("handicap") or 0),
        str(record.get("status") or "pending"),
        record.get("team_score"), record.get("opponent_score"),
        str(record.get("memo") or "").strip(),
    )


def _legacy_id(record: dict[str, Any], index: int) -> str:
    payload = json.dumps(record, ensure_ascii=False, sort_keys=True, default=str)
    digest = sha256(f"{index}:{payload}".encode("utf-8")).hexdigest()[:16]
    return f"legacy-{digest}"


def _with_record_ids(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, source in enumerate(records):
        if not isinstance(source, dict):
            continue
        record = deepcopy(source)
        record_id = str(record.get("id") or _legacy_id(record, index))
        if record_id in seen:
            record_id = f"{record_id}-{index}"
        record["id"] = record_id
        seen.add(record_id)
        normalized.append(record)
    return normalized


def load_bets(path: Path) -> list[dict[str, Any]]:
    """Load BET records and provide stable IDs for legacy entries."""
    with _locked(path):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError) as exc:
            raise BetStoreError(f"BETデータを読み込めません: {exc}") from exc
        if not isinstance(raw, list):
            raise BetStoreError("BETデータの形式が不正です。配列形式が必要です。")
        return _with_record_ids(raw)


def _atomic_write(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temp_file:
            json.dump(records, temp_file, ensure_ascii=False, indent=2)
            temp_file.write("\n")
            temp_file.flush()
            os.fsync(temp_file.fileno())
            temp_name = temp_file.name
        os.replace(temp_name, path)
    except OSError as exc:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass
        raise BetStoreError(f"BETデータを保存できません: {exc}") from exc


def save_bets(path: Path, records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Atomically replace all BET records."""
    with _locked(path):
        normalized = _with_record_ids(records)
        _atomic_write(path, normalized)
        return deepcopy(normalized)


def import_bets(
    path: Path,
    imported: Iterable[dict[str, Any]],
    *,
    replace: bool = False,
) -> tuple[list[dict[str, Any]], int]:
    """Atomically import records, skipping IDs already present when appending."""
    with _locked(path):
        incoming = _with_record_ids(imported)
        if replace:
            _atomic_write(path, incoming)
            return deepcopy(incoming), len(incoming)

        current = load_bets(path)
        seen = {record["id"] for record in current}
        additions = [record for record in incoming if record["id"] not in seen]
        merged = [*current, *additions]
        _atomic_write(path, merged)
        return deepcopy(merged), len(additions)


def append_bet(path: Path, record: dict[str, Any]) -> dict[str, Any]:
    """Append one unique BET record without losing concurrent updates."""
    with _locked(path):
        records = load_bets(path)
        normalized = _with_record_ids([record])[0]
        if any(item["id"] == normalized["id"] for item in records):
            raise DuplicateBetError(f"BET ID {normalized['id']} は既に存在します。")
        if normalized.get("source") in {"manual", "manual-page"}:
            identity = _manual_identity(normalized)
            if any(_manual_identity(item) == identity for item in records):
                raise DuplicateBetError("同じ日時・対戦・金額・ハンデ・結果・メモのBETは登録済みです。重複登録はしていません。")
        records.append(normalized)
        _atomic_write(path, records)
        return deepcopy(normalized)


def update_bet(path: Path, record_id: str, changes: dict[str, Any]) -> dict[str, Any]:
    """Update one BET record by ID and persist the complete collection."""
    with _locked(path):
        records = load_bets(path)
        for index, record in enumerate(records):
            if record["id"] != record_id:
                continue
            updated = {**record, **deepcopy(changes), "id": record_id}
            records[index] = updated
            _atomic_write(path, records)
            return deepcopy(updated)
    raise BetNotFoundError(f"BET ID {record_id} が見つかりません。")


def delete_bet(path: Path, record_id: str) -> dict[str, Any]:
    """Delete one BET record by ID."""
    with _locked(path):
        records = load_bets(path)
        for index, record in enumerate(records):
            if record["id"] != record_id:
                continue
            deleted = records.pop(index)
            _atomic_write(path, records)
            return deepcopy(deleted)
    raise BetNotFoundError(f"BET ID {record_id} が見つかりません。")
