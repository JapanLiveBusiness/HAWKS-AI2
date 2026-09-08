from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
DATA_DIRS = [Path("/app/data"), ROOT / "data", Path("/opt/ai-baseball2026/data")]

PAGE_CSS = """
<style>
#MainMenu, footer {visibility:hidden}
.block-container{max-width:1380px;padding-top:1.25rem;padding-bottom:2rem}
.studio-kicker{color:#f2c94c;font-size:.75rem;font-weight:900;letter-spacing:.16em}
.studio-title{font-size:2rem;font-weight:950;color:#0b1728;margin:.15rem 0 .25rem}
.studio-sub{color:#667085;margin-bottom:1rem}
div[data-testid="stMetric"]{background:#fff;border:1px solid #e5eaf0;border-radius:14px;padding:.7rem .85rem;box-shadow:0 4px 16px rgba(11,23,40,.05)}
@media(max-width:700px){.studio-title{font-size:1.45rem}.block-container{padding-left:.65rem;padding-right:.65rem}}
</style>
"""


def setup(title: str, subtitle: str) -> None:
    st.set_page_config(page_title=f"{title} | AI BASEBALL STUDIO", page_icon="⚾", layout="wide")
    st.markdown(PAGE_CSS, unsafe_allow_html=True)
    st.markdown('<div class="studio-kicker">AI BASEBALL STUDIO</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="studio-title">{title}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="studio-sub">{subtitle}</div>', unsafe_allow_html=True)


def load_json(filename: str, default: Any) -> Any:
    for directory in DATA_DIRS:
        path = directory / filename
        try:
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
    return default


def rows(value: Any) -> list[dict]:
    if isinstance(value, list):
        return [x for x in value if isinstance(x, dict)]
    if isinstance(value, dict):
        for key in ("games", "predictions", "results", "records", "data"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return [x for x in candidate if isinstance(x, dict)]
        return [value] if value else []
    return []


def frame(value: Any) -> pd.DataFrame:
    data = rows(value)
    return pd.DataFrame(data) if data else pd.DataFrame()


def show_empty(message: str) -> None:
    st.info(message)


def percent(value: Any) -> str:
    try:
        n = float(value)
        if n <= 1:
            n *= 100
        return f"{n:.1f}%"
    except Exception:
        return "-"


def money(value: Any) -> str:
    try:
        n = int(float(value))
        return f"{'+' if n > 0 else ''}¥{n:,}"
    except Exception:
        return "¥0"


def first(record: dict, *keys: str, default: Any = "-") -> Any:
    for key in keys:
        value = record.get(key)
        if value not in (None, ""):
            return value
    return default


def game_label(record: dict) -> str:
    away = first(record, "away_team", "away", "visitor", "team")
    home = first(record, "home_team", "home", "opponent")
    return f"{away} vs {home}"


def updated_at() -> str:
    for directory in DATA_DIRS:
        if directory.exists():
            try:
                latest = max((p.stat().st_mtime for p in directory.glob("*.json")), default=0)
                if latest:
                    return datetime.fromtimestamp(latest).strftime("%Y-%m-%d %H:%M")
            except Exception:
                pass
    return "-"
