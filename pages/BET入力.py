from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import streamlit as st

from auth_session import user_bets_path
from bet_analytics import profit_for_result, settle_bet
from bet_store import BetStoreError, append_bet
from manual_bet_form import render_manual_bet_form
from virtual_replay_ui import render_virtual_replay
from studio_theme import apply_studio_theme, render_topbar, render_hero, render_nav_links

JST = ZoneInfo("Asia/Tokyo")
REPO_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PROD_DATA_DIR = Path("/app/data")
DATA_DIR = PROD_DATA_DIR if PROD_DATA_DIR.exists() else REPO_DATA_DIR
SCHEDULE_CACHE_PATHS = (
    Path("/app/shared-data/npb_today.json"),
    DATA_DIR / "npb_today.json",
    DATA_DIR / "npb_schedule_cache.json",
    REPO_DATA_DIR.parent / "npb_schedule_fallback.json",
)
st.set_page_config(page_title="BET入力 | MY AI BASEBALL", page_icon="✍️", layout="wide")
apply_studio_theme()
auth_user = render_topbar("BET MANAGEMENT")
BETS_FILE = user_bets_path(DATA_DIR, auth_user)
render_hero(
    "BET・収支入力",
    "当日のNPBカードからBET先・ハンデ・金額・結果を登録し、収支マップへ即時反映します。",
    kicker="AI BASEBALL STUDIO / BET INPUT",
    accent="BET",
)
render_nav_links()
render_virtual_replay(BETS_FILE)


render_manual_bet_form(BETS_FILE, SCHEDULE_CACHE_PATHS, prefix="bet_manual")
if notice := st.session_state.pop("bet_notice", None):
    st.success(notice)
