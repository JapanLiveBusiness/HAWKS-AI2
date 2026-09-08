from __future__ import annotations

import json
import os
from pathlib import Path

import pandas as pd
import streamlit as st

from daily_data import load_current_daily_json
from result_sources import load_final_results
from studio_theme import apply_studio_theme, render_hero, render_nav_links, render_section, render_topbar
from team_insights import TEAM_META, TEAMS, league_standings, merge_team_history, team_summary, upcoming_team_game

ROOT = Path(__file__).resolve().parents[1]
PROD_DATA_DIR = Path("/app/data")
REPO_DATA_DIR = ROOT / "data"

st.set_page_config(page_title="球団別詳細 | AI BASEBALL STUDIO", page_icon="⚾", layout="wide")
apply_studio_theme()
render_topbar("TEAM INSIGHTS")
render_hero(
    "球団別詳細",
    "12球団のシーズン戦績、直近フォーム、得失点、次戦とAI予測を同じ画面で確認できます。",
    kicker="AI BASEBALL STUDIO / TEAM INTELLIGENCE",
    accent="球団",
)
render_nav_links()


def load_json(name, default):
    for directory in (PROD_DATA_DIR, REPO_DATA_DIR):
        try:
            path = directory / name
            if path.exists():
                return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
    return default


requested_team = str(st.query_params.get("team") or "")
default_team = requested_team if requested_team in TEAMS else TEAMS[0]
team = st.selectbox("球団を選択", TEAMS, index=TEAMS.index(default_team), key="team_detail_selector")
if requested_team != team:
    st.query_params["team"] = team

history = load_json("historical_games_2017_2026.json", [])
history = merge_team_history(
    history if isinstance(history, list) else [],
    load_final_results(
        PROD_DATA_DIR if PROD_DATA_DIR.exists() else REPO_DATA_DIR,
        Path(os.getenv("AI_BASEBALL_SHARED_DATA_DIR", "/app/shared-data")),
    ),
)
schedule = load_current_daily_json("npb_today.json", {})
predictions = load_current_daily_json("today_ai_predictions.json", {})
available_seasons = sorted({int(row.get("season") or 0) for row in history if isinstance(row, dict) and row.get("season")}, reverse=True)
season = st.selectbox("シーズン", available_seasons or [2026], key="team_detail_season")
summary = team_summary(history, team, season)
meta = TEAM_META[team]
standings = league_standings(history, meta["league"], season)
standing = next((row for row in standings if row["team"] == team), {"rank": "--"})

header_left, header_right = st.columns([1, 5], vertical_alignment="center")
logo_path = ROOT / "static" / "team-logos" / "pngアイコン" / meta["logo"]
if logo_path.exists():
    header_left.image(str(logo_path), width=88)
header_right.subheader(f"{team}｜{meta['league']}")
header_right.caption(f"{season}年の共有試合履歴から自動集計")

with st.container(horizontal=True):
    st.metric("順位", f"{standing['rank']}位", border=True)
    st.metric("戦績", f"{summary['wins']}勝 {summary['losses']}敗 {summary['draws']}分", border=True)
    st.metric("勝率", f"{summary['win_rate']:.1f}%" if summary["win_rate"] is not None else "--", border=True)
    st.metric("得失点差", f"{summary['run_diff']:+d}", border=True)
    st.metric("直近10試合", f"{summary['recent_wins']}勝 / {summary['recent_played']}試合", border=True)

render_section("NEXT GAME", "次戦・先発・AI予測")
upcoming = upcoming_team_game(schedule, predictions, team)
if upcoming:
    with st.container(border=True):
        st.subheader(f"{upcoming.get('away', '--')} @ {upcoming.get('home', '--')}")
        st.caption(f"{upcoming.get('date') or schedule.get('date') or '--'} {upcoming.get('time') or '--:--'}｜{upcoming.get('venue') or '会場未定'}")
        with st.container(horizontal=True):
            st.metric("AI予想", upcoming.get("pick") or "同期待ち", border=True)
            probability = upcoming.get("win_probability")
            st.metric("AI勝率", f"{float(probability):.1f}%" if probability is not None else "--", border=True)
            st.metric("予想スコア", upcoming.get("predicted_score") or "--", border=True)
            st.metric("先発", upcoming.get("team_starter") or "未発表", border=True)
else:
    st.info("現在の共有日程に、この球団の次戦は登録されていません。")

render_section("RECENT FORM", "直近試合と得失点")
recent = summary["games"][:10]
if recent:
    chart_rows = pd.DataFrame(
        [{"日付": row["date"], "得点": row["runs_for"], "失点": row["runs_against"]} for row in reversed(recent)]
    )
    st.line_chart(chart_rows, x="日付", y=["得点", "失点"])
    st.dataframe(
        [
            {
                "日付": row["date"],
                "対戦相手": row["opponent"],
                "球場": row["home_away"],
                "スコア": f"{row['runs_for']}-{row['runs_against']}",
                "結果": row["result"],
                "会場": row["venue"],
                "先発": row["starter"] or "--",
            }
            for row in recent
        ],
        hide_index=True,
        width="stretch",
        key="team_detail_recent_games",
    )
else:
    st.info(f"{season}年の試合履歴はまだありません。")

render_section("STANDINGS", f"{meta['league']}比較")
st.dataframe(
    [
        {
            "順位": row["rank"],
            "球団": row["team"],
            "試合": row["played"],
            "勝": row["wins"],
            "敗": row["losses"],
            "分": row["draws"],
            "勝率": row["win_rate"] / 100 if row["win_rate"] is not None else None,
            "得失点差": row["run_diff"],
        }
        for row in standings
    ],
    hide_index=True,
    width="stretch",
    column_config={"勝率": st.column_config.NumberColumn(format="percent")},
    key="team_detail_standings",
)

st.caption("順位は共有試合履歴の勝率、同率時は得失点差で算出します。公式順位と差がある場合があります。")
