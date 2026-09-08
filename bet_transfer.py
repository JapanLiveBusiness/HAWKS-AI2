"""Validated spreadsheet import and export for BET history."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
import math
from pathlib import Path
from typing import Any, Iterable
from uuid import uuid4

import pandas as pd

from bet_analytics import bet_amount as record_bet_amount
from bet_analytics import profit_for_record, profit_for_result, settle_bet


FORMAT_VERSION = 1
MAX_IMPORT_ROWS = 5000
EXPORT_COLUMNS = {
    "id": "BET ID",
    "date": "試合日",
    "time": "開始時刻",
    "team": "BET先",
    "opponent": "対戦相手",
    "handicap": "ハンディ",
    "bet_amount": "BET金額（円）",
    "status": "状態",
    "team_score": "BET先得点",
    "opponent_score": "対戦相手得点",
    "result": "結果",
    "profit": "損益（円）",
    "memo": "メモ",
    "source": "登録元",
    "created_at": "登録日時",
    "updated_at": "更新日時",
}
IMPORT_ALIASES = {label: key for key, label in EXPORT_COLUMNS.items()}
IMPORT_ALIASES.update({key: key for key in EXPORT_COLUMNS})


class BetSpreadsheetError(ValueError):
    """Raised when an uploaded spreadsheet cannot be safely imported."""


def _spreadsheet_safe(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    if value.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def _restore_safe_text(value: Any) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    if len(text) > 1 and text[0] == "'" and text[1] in "=+-@":
        return text[1:]
    return text


def bets_to_xlsx(records: Iterable[dict[str, Any]]) -> bytes:
    """Create an Excel workbook suitable for backup and re-import."""
    rows = []
    for source in records:
        row = {
            label: _spreadsheet_safe(
                record_bet_amount(source)
                if key == "bet_amount"
                else profit_for_record(source)
                if key == "profit"
                else source.get(key)
            )
            for key, label in EXPORT_COLUMNS.items()
        }
        rows.append(row)
    frame = pd.DataFrame(rows, columns=list(EXPORT_COLUMNS.values()))
    metadata = pd.DataFrame(
        [
            {"項目": "フォーマットバージョン", "値": FORMAT_VERSION},
            {"項目": "出力日時", "値": datetime.now().astimezone().isoformat(timespec="seconds")},
            {"項目": "件数", "値": len(rows)},
        ]
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        frame.to_excel(writer, sheet_name="BET履歴", index=False)
        metadata.to_excel(writer, sheet_name="情報", index=False)
        worksheet = writer.sheets["BET履歴"]
        worksheet.freeze_panes = "A2"
        worksheet.auto_filter.ref = worksheet.dimensions
    return output.getvalue()


def _required_text(row: pd.Series, field: str, row_number: int) -> str:
    text = _restore_safe_text(row.get(field))
    if not text:
        raise BetSpreadsheetError(f"{row_number}行目: {EXPORT_COLUMNS[field]}が空です。")
    if len(text) > 200:
        raise BetSpreadsheetError(f"{row_number}行目: {EXPORT_COLUMNS[field]}が長すぎます。")
    return text


def _number(value: Any, label: str, row_number: int, minimum: float, maximum: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise BetSpreadsheetError(f"{row_number}行目: {label}は数値で入力してください。") from None
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise BetSpreadsheetError(
            f"{row_number}行目: {label}は{minimum:g}〜{maximum:g}の範囲で入力してください。"
        )
    return number


def _optional_score(value: Any, label: str, row_number: int) -> int | None:
    if pd.isna(value) or str(value).strip() == "":
        return None
    number = _number(value, label, row_number, 0, 100)
    if not number.is_integer():
        raise BetSpreadsheetError(f"{row_number}行目: {label}は整数で入力してください。")
    return int(number)


def _normalize_date(value: Any, row_number: int) -> str:
    try:
        parsed = pd.to_datetime(value, errors="raise")
    except (TypeError, ValueError):
        raise BetSpreadsheetError(f"{row_number}行目: 試合日を確認してください。") from None
    return parsed.date().isoformat()


def _normalize_time(value: Any, row_number: int) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return "18:00"
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    text = str(value).strip()
    for pattern in ("%H:%M", "%H:%M:%S"):
        try:
            return datetime.strptime(text, pattern).strftime("%H:%M")
        except ValueError:
            continue
    raise BetSpreadsheetError(f"{row_number}行目: 開始時刻をHH:MM形式で入力してください。")


def normalize_import_frame(frame: pd.DataFrame) -> list[dict[str, Any]]:
    """Validate imported rows and recalculate all settlement-derived values."""
    if len(frame) > MAX_IMPORT_ROWS:
        raise BetSpreadsheetError(f"一度に取り込める履歴は{MAX_IMPORT_ROWS:,}件までです。")
    renamed = frame.rename(columns=lambda name: IMPORT_ALIASES.get(str(name).strip(), str(name).strip()))
    required = {"date", "team", "opponent", "bet_amount"}
    missing = [EXPORT_COLUMNS[name] for name in required if name not in renamed.columns]
    if missing:
        raise BetSpreadsheetError(f"必須列がありません: {', '.join(missing)}")

    records: list[dict[str, Any]] = []
    for offset, row in renamed.iterrows():
        row_number = int(offset) + 2 if isinstance(offset, int) else len(records) + 2
        status_text = _restore_safe_text(row.get("status")).lower()
        is_final = status_text in {"final", "確定", "settled"}
        if status_text not in {"", "pending", "未確定", "final", "確定", "settled"}:
            raise BetSpreadsheetError(f"{row_number}行目: 状態は未確定または確定を指定してください。")

        amount = _number(row.get("bet_amount"), "BET金額（円）", row_number, 0, 1_000_000_000)
        if not amount.is_integer():
            raise BetSpreadsheetError(f"{row_number}行目: BET金額（円）は整数で入力してください。")
        handicap_value = row.get("handicap", 0)
        if pd.isna(handicap_value) or str(handicap_value).strip() == "":
            handicap_value = 0
        handicap = _number(handicap_value, "ハンディ", row_number, -100, 100)
        team_score = _optional_score(row.get("team_score"), "BET先得点", row_number)
        opponent_score = _optional_score(row.get("opponent_score"), "対戦相手得点", row_number)
        if is_final and (team_score is None or opponent_score is None):
            raise BetSpreadsheetError(f"{row_number}行目: 確定BETには両チームの得点が必要です。")

        adjusted_score, result = (
            settle_bet(team_score, opponent_score, handicap)
            if is_final
            else (None, None)
        )
        record_id = _restore_safe_text(row.get("id")) or f"import-{uuid4().hex}"
        records.append(
            {
                "id": record_id[:200],
                "date": _normalize_date(row.get("date"), row_number),
                "time": _normalize_time(row.get("time"), row_number),
                "team": _required_text(row, "team", row_number),
                "opponent": _required_text(row, "opponent", row_number),
                "handicap": handicap,
                "bet_units": amount / 10000.0,
                "bet_amount": int(amount),
                "status": "final" if is_final else "pending",
                "settled": is_final,
                "result": result,
                "profit": profit_for_result(result, amount) if is_final else 0,
                "team_score": team_score if is_final else None,
                "opponent_score": opponent_score if is_final else None,
                "adjusted_score": adjusted_score,
                "memo": _restore_safe_text(row.get("memo"))[:2000],
                "source": _restore_safe_text(row.get("source"))[:100] or "spreadsheet-import",
                "created_at": _restore_safe_text(row.get("created_at"))[:100]
                or datetime.now().astimezone().isoformat(timespec="seconds"),
                "updated_at": _restore_safe_text(row.get("updated_at"))[:100],
            }
        )
    return records


def read_bet_spreadsheet(data: bytes, filename: str) -> list[dict[str, Any]]:
    """Read an XLSX or CSV upload and return validated BET records."""
    suffix = Path(filename or "").suffix.lower()
    if suffix == ".xlsx":
        try:
            frame = pd.read_excel(BytesIO(data), sheet_name="BET履歴", engine="openpyxl")
        except (ValueError, OSError, KeyError) as exc:
            raise BetSpreadsheetError(f"Excelファイルを読み込めません: {exc}") from exc
    elif suffix == ".csv":
        try:
            frame = pd.read_csv(BytesIO(data), encoding="utf-8-sig")
        except UnicodeDecodeError:
            frame = pd.read_csv(BytesIO(data), encoding="cp932")
        except (ValueError, OSError) as exc:
            raise BetSpreadsheetError(f"CSVファイルを読み込めません: {exc}") from exc
    else:
        raise BetSpreadsheetError(".xlsx または .csv ファイルを選択してください。")
    return normalize_import_frame(frame)
