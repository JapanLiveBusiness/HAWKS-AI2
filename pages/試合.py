from __future__ import annotations

import html
import json
import re
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from game_calendar import (
    attach_handicaps,
    attach_hawks_history_results,
    fetch_daily_handicaps,
    fetch_npb_schedule_day,
    merge_game_sources,
    pending_status_label,
)
from gamecast import gamecast_snapshot, select_featured_game
from daily_data import load_current_daily_json
from npb_live import fetch_npb_live_game
from studio_theme import apply_studio_theme, render_hero, render_nav_links, render_section, render_topbar

JST = ZoneInfo("Asia/Tokyo")
REPO_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PROD_DATA_DIR = Path("/app/data")
LIVE_STATUSES = {"live", "in_progress", "playing", "試合中", "開催中"}
FINAL_STATUSES = {"final", "finished", "completed", "終了", "試合終了"}

st.set_page_config(page_title="試合カレンダー | AI BASEBALL STUDIO", page_icon="⚾", layout="wide", initial_sidebar_state="collapsed")


def data_path(name: str) -> Path:
    prod = PROD_DATA_DIR / name
    return prod if prod.exists() else REPO_DATA_DIR / name


def load_json(name: str, fallback):
    try:
        return json.loads(data_path(name).read_text(encoding="utf-8"))
    except Exception:
        return fallback


def load_schedule_cache() -> dict:
    runtime_cache = PROD_DATA_DIR / "npb_schedule_cache.json"
    bundled_fallback = REPO_DATA_DIR.parent / "npb_schedule_fallback.json"
    merged = {}
    for path in (bundled_fallback, runtime_cache):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for game in payload.get("games") or []:
            key = (str(game.get("date") or ""), str(game.get("home") or ""), str(game.get("away") or ""))
            merged[key] = game
    return {"games": list(merged.values())}


def load_results_cache() -> dict:
    runtime_cache = PROD_DATA_DIR / "npb_results_cache.json"
    bundled_fallback = REPO_DATA_DIR.parent / "npb_results_fallback.json"
    merged = {}
    for path in (bundled_fallback, runtime_cache):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for game in payload.get("games") or []:
            key = (str(game.get("date") or ""), str(game.get("home") or ""), str(game.get("away") or ""))
            merged[key] = game
    return {"games": list(merged.values())}


@st.cache_data(ttl=30, max_entries=32, show_spinner=False)
def cached_official_games(date_iso: str) -> list[dict]:
    return fetch_npb_schedule_day(date.fromisoformat(date_iso), timeout=6)


@st.cache_data(ttl=300, max_entries=32, show_spinner=False)
def cached_handicaps(date_iso: str) -> list[dict]:
    return fetch_daily_handicaps(date.fromisoformat(date_iso), timeout=6, strict=True)


@st.cache_data(ttl=15, max_entries=12, show_spinner=False)
def cached_live_game(date_iso: str, home: str, away: str) -> dict:
    return fetch_npb_live_game(date.fromisoformat(date_iso), home, away)


def status_key(game: dict) -> str:
    return str(game.get("status") or "scheduled").strip().lower()


def is_live(game: dict) -> bool:
    key = status_key(game)
    return key in LIVE_STATUSES or any(token in key for token in ("live", "progress", "試合中"))


def is_final(game: dict) -> bool:
    key = status_key(game)
    return key in FINAL_STATUSES or any(token in key for token in ("final", "finish", "終了"))


def status_label(game: dict) -> tuple[str, str]:
    key = status_key(game)
    if is_live(game):
        return "LIVE", "live"
    if is_final(game):
        return "試合終了", "final"
    if "cancel" in key or "中止" in key:
        return "中止", "cancelled"
    if key == "result_pending":
        return pending_status_label(game), "scheduled"
    return "開始前", "scheduled"


def score_text(value) -> str:
    return "-" if value is None or value == "" else html.escape(str(value))


def prediction_index(payload: dict) -> dict[tuple[str, str], dict]:
    out = {}
    for row in payload.get("games") or []:
        home = str(row.get("home") or "")
        away = str(row.get("away") or "")
        if home and away:
            out[(home, away)] = row
    return out


def games_for_date(selected_date: date) -> tuple[list[dict], dict, dict]:
    selected_iso = selected_date.isoformat()
    today_payload = load_current_daily_json("npb_today.json", {"games": []})
    predictions = load_current_daily_json("today_ai_predictions.json", {"games": []})
    history = load_json("historical_games_2017_2026.json", [])
    local_games = [
        game for game in today_payload.get("games") or []
        if str(game.get("date") or today_payload.get("date") or "") == selected_iso
    ]
    history_games = []
    for row in history if isinstance(history, list) else []:
        if str(row.get("date") or "") != selected_iso:
            continue
        game = dict(row)
        game["status"] = "final"
        game["result_source"] = game.get("result_source") or "保存済み試合結果"
        history_games.append(game)

    current_date = datetime.now(JST).date()
    is_past = selected_date < current_date
    is_current_or_past = selected_date <= current_date
    stored_results = [
        game for game in load_results_cache().get("games") or []
        if str(game.get("date") or "") == selected_iso
    ] if is_current_or_past else []
    try:
        live_results = cached_handicaps(selected_iso) if is_current_or_past else []
    except Exception:
        live_results = []
        st.warning("ハンデの森の認証付き取得に失敗しました。表示値は保存済みデータで、空欄は未取得です。")
    daily_results = (
        merge_game_sources(stored_results, live_results)
        if is_current_or_past
        else []
    )
    # ハンデ掲載元の結果が未更新でも、NPB公式の確定スコアを併用する。
    official_games = cached_official_games(selected_iso)
    if not official_games:
        schedule_cache = load_schedule_cache()
        official_games = [
            game for game in schedule_cache.get("games") or []
            if str(game.get("date") or "") == selected_iso
        ]
    games = merge_game_sources(official_games, history_games, local_games, daily_results)
    saved_hawks_history = load_json("game_history.json", [])
    if isinstance(saved_hawks_history, list):
        games = attach_hawks_history_results(games, saved_hawks_history)
    if selected_date == current_date:
        hawks_index = next(
            (
                index
                for index, game in enumerate(games)
                if "ソフトバンク" in {str(game.get("home") or ""), str(game.get("away") or "")}
            ),
            None,
        )
        if hawks_index is not None and not is_final(games[hawks_index]):
            game = games[hawks_index]
            live_update = cached_live_game(
                selected_iso,
                str(game.get("home") or ""),
                str(game.get("away") or ""),
            )
            if live_update:
                games[hawks_index] = merge_game_sources([game], [live_update])[0]
    if is_current_or_past:
        games = attach_handicaps(games, live_results)

    predictions_date = str(predictions.get("date") or "")
    if predictions_date and predictions_date != selected_iso:
        predictions = {"games": []}
    return games, today_payload, predictions


def clean_venue(value) -> str:
    venue = re.sub(r"^\d{1,2}:\d{2}", "", str(value or "")).strip()
    return venue or "会場未定"


def handicap_html(game: dict, show_handicap: bool) -> str:
    if not show_handicap:
        return ""
    entries = []
    for side in ("home", "away"):
        token = game.get(f"{side}_handicap")
        if token is not None:
            team = html.escape(str(game.get(side) or ("ホーム" if side == "home" else "ビジター")))
            entries.append(f"{team} {html.escape(str(token))}")
    value = " / ".join(entries) if entries else "未掲載・未取得"
    return f'<div class="handicap"><span>HANDICAP</span><strong>{value}</strong></div>'


def _count_lights(label: str, active: int, total: int, css_class: str) -> str:
    lights = "".join(
        f'<i class="count-light {css_class} {"on" if index < active else ""}"></i>'
        for index in range(total)
    )
    return f'<span class="count-row"><b>{label}</b>{lights}</span>'


def _base_indicator(base: int, occupied_bases: set[int]) -> str:
    occupied = base in occupied_bases
    state_class = " occupied" if occupied else ""
    state_label = "走者あり" if occupied else "走者なし"
    return (
        f'<i class="base base-{base}{state_class}" role="img" '
        f'aria-label="{base}塁 {state_label}" title="{base}塁 {state_label}"></i>'
    )


def render_gamecast(game: dict, prediction: dict, target_date: date) -> None:
    snapshot = gamecast_snapshot(game)
    away = html.escape(str(game.get("away") or "---"))
    home = html.escape(str(game.get("home") or "---"))
    away_score = score_text(game.get("away_score"))
    home_score = score_text(game.get("home_score"))
    venue = html.escape(clean_venue(game.get("venue")))
    start_time = html.escape(str(game.get("time") or "--:--"))
    game_date = html.escape(str(game.get("date") or target_date.isoformat()))
    status_class = "live" if snapshot["live"] else "final" if snapshot["final"] else "pregame"
    bases = snapshot["bases"]
    base_indicators = "".join(
        _base_indicator(base, bases) for base in (1, 2, 3)
    )
    lineup = snapshot["lineup"]
    lineup_html = "".join(
        f'<li><span>{index}</span><b>{html.escape(name)}</b></li>'
        for index, name in enumerate(lineup, start=1)
    ) or '<li class="lineup-empty">スタメン情報の取得待ち</li>'

    pick = html.escape(str(prediction.get("pick") or "AI予測待ち"))
    probability = prediction.get("win_probability")
    probability_label = (
        f"{float(probability):.1f}%"
        if isinstance(probability, (int, float))
        else "--"
    )
    counts = "".join(
        (
            _count_lights("B", snapshot["balls"], 3, "ball"),
            _count_lights("S", snapshot["strikes"], 2, "strike"),
            _count_lights("O", snapshot["outs"], 2, "out"),
        )
    )
    live_note = (
        "NPB公式速報を15秒キャッシュで更新中"
        if snapshot["live"]
        else "確定結果を表示"
        if snapshot["final"]
        else "試合開始後にNPB公式速報へ切り替わります"
    )

    st.markdown(
        f'''
<section class="gamecast-shell">
  <div class="gamecast-titlebar">
    <div><span class="gamecast-dot"></span> LIVE GAMECAST</div>
    <small>{game_date} · {start_time} · {venue}</small>
  </div>
  <div class="gamecast-scoreboard">
    <span class="gamecast-state {status_class}">{html.escape(snapshot["status_label"])}</span>
    <div class="score-team away"><b>{away}</b><strong>{away_score}</strong></div>
    <div class="inning-state">{html.escape(snapshot["inning_label"])}</div>
    <div class="score-team home"><strong>{home_score}</strong><b>{home}</b></div>
  </div>
  <div class="gamecast-content">
    <div class="field-card">
      <div class="field-ribbon">AI BASEBALL · DIAMOND LIVE CENTER</div>
      <div class="ballpark">
        <div class="outfield-stripe stripe-one"></div><div class="outfield-stripe stripe-two"></div>
        <div class="infield"><div class="mound"></div></div>
        {base_indicators}
        <div class="home-plate"></div>
      </div>
      <div class="field-footer">
        <div><span>MATCHUP</span><b>{away} vs {home}</b><small>{venue}</small></div>
        <div class="count-board"><span>ボールカウント</span>{counts}</div>
      </div>
    </div>
    <aside class="gamecast-side">
      <div class="player-panel">
        <span>PITCHER</span><strong>{html.escape(snapshot["pitcher"])}</strong>
        <small>現在の投手 / 予告先発</small>
      </div>
      <div class="player-panel batter-panel">
        <span>AT BAT</span><strong>{html.escape(snapshot["batter"])}</strong>
        <small>現在の打者</small>
      </div>
      <div class="lineup-panel"><span>LINEUP</span><ol>{lineup_html}</ol></div>
    </aside>
  </div>
  <div class="gamecast-info">
    <div><span>AI PICK</span><b>{pick}</b><strong>{probability_label}</strong></div>
    <p>{live_note}</p>
  </div>
</section>
''',
        unsafe_allow_html=True,
    )


def set_selected_date(value: date) -> None:
    st.session_state.games_calendar_date = value


def shift_selected_date(days: int) -> None:
    current = st.session_state.get("games_calendar_date", datetime.now(JST).date())
    st.session_state.games_calendar_date = current + timedelta(days=days)


apply_studio_theme()
render_topbar("GAMES / CALENDAR")
render_hero(
    "試合カレンダー",
    "前日までの試合結果とハンデ、当日の進行状況、翌日以降の開始時刻・開催球場を日付ごとに確認できます。",
    kicker="AI BASEBALL STUDIO / MATCH CENTER",
    accent="試合",
)
render_nav_links()

today = datetime.now(JST).date()
if "games_calendar_date" not in st.session_state:
    st.session_state.games_calendar_date = today

nav_left, nav_today, nav_date, nav_right = st.columns([1, 1, 3, 1])
nav_left.button("前日", icon=":material/chevron_left:", key="games_previous_date", on_click=shift_selected_date, args=(-1,), width="stretch")
nav_today.button("今日", icon=":material/today:", key="games_today_date", on_click=set_selected_date, args=(today,), width="stretch")
selected_date = nav_date.date_input("表示日", key="games_calendar_date", format="YYYY/MM/DD", label_visibility="collapsed", width="stretch")
nav_right.button("翌日", icon=":material/chevron_right:", key="games_next_date", on_click=shift_selected_date, args=(1,), width="stretch")

st.markdown(
    """
<style>
.gamecast-shell{margin:16px 0 24px;background:#17181a;color:#fff;border:1px solid #2e3034;border-radius:16px;overflow:hidden;box-shadow:0 16px 36px rgba(20,18,13,.18)}
.gamecast-titlebar{min-height:42px;padding:0 16px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #34363a;font-size:9px;letter-spacing:.18em;font-weight:950}.gamecast-titlebar small{color:#9c9fa5;font-size:9px;letter-spacing:0}.gamecast-dot{display:inline-block;width:7px;height:7px;margin-right:7px;border-radius:50%;background:#ff3b3b;box-shadow:0 0 0 4px rgba(255,59,59,.12)}
.gamecast-scoreboard{position:relative;min-height:74px;display:grid;grid-template-columns:1fr 100px 1fr;align-items:center;padding:0 76px;border-bottom:1px solid #34363a;background:#121315}.gamecast-state{position:absolute;left:14px;top:25px;border-radius:999px;padding:6px 9px;background:#303238;color:#d6d8dc;font-size:8px;font-weight:950}.gamecast-state.live{background:#f1c40f;color:#101010}.gamecast-state.final{background:#dde3e9;color:#171717}.score-team{display:flex;align-items:center;justify-content:center;gap:24px}.score-team b{font-size:17px}.score-team strong{font-size:32px;color:#f1c40f}.inning-state{text-align:center;color:#aeb1b6;font-size:11px}.gamecast-content{display:grid;grid-template-columns:minmax(0,2.35fr) minmax(240px,.65fr);gap:12px;padding:14px}.field-card,.gamecast-side>div{border:1px solid #393b40;border-radius:12px;overflow:hidden}.field-card{background:#101113}.field-ribbon{height:32px;display:flex;align-items:center;justify-content:center;background:repeating-linear-gradient(135deg,#116850 0,#116850 22px,#0c5844 22px,#0c5844 44px);color:#d9fff2;font-size:8px;letter-spacing:.2em;font-weight:950}.ballpark{height:310px;position:relative;overflow:hidden;background:repeating-linear-gradient(90deg,#57ad41 0,#57ad41 42px,#61b84a 42px,#61b84a 84px);border-bottom:8px solid #0d586f}.ballpark:before{content:"";position:absolute;width:390px;height:390px;left:50%;top:52px;transform:translateX(-50%) rotate(45deg);background:#bd7a35;border:3px solid rgba(255,255,255,.75);border-radius:18px}.ballpark:after{content:"";position:absolute;width:270px;height:270px;left:50%;top:112px;transform:translateX(-50%) rotate(45deg);background:#64b94b;border:3px solid rgba(255,255,255,.7);border-radius:8px}.infield{position:absolute;z-index:2;width:74px;height:74px;left:50%;top:136px;transform:translateX(-50%);border-radius:50%;background:#bd7a35}.mound{position:absolute;width:18px;height:8px;left:28px;top:33px;border-radius:999px;background:#e7d7a8}.base{position:absolute;z-index:4;width:13px;height:13px;background:#fff;border:2px solid #eee;transform:rotate(45deg);box-shadow:0 2px 4px rgba(0,0,0,.2)}.base.occupied{background:#f1c40f;border-color:#ffe577;box-shadow:0 0 0 5px rgba(241,196,15,.18)}.base-1{left:calc(50% + 126px);top:200px}.base-2{left:calc(50% - 7px);top:78px}.base-3{left:calc(50% - 140px);top:200px}.home-plate{position:absolute;z-index:5;width:22px;height:16px;left:calc(50% - 11px);bottom:18px;background:#fff;clip-path:polygon(0 0,100% 0,82% 70%,50% 100%,18% 70%)}.field-footer{min-height:86px;padding:12px 15px;display:flex;align-items:center;justify-content:space-between;gap:16px}.field-footer>div:first-child{display:flex;flex-direction:column}.field-footer span,.player-panel span,.lineup-panel>span{font-size:7px;letter-spacing:.16em;color:#d0a917;font-weight:950}.field-footer b{font-size:14px;margin:4px 0}.field-footer small{color:#8f9298;font-size:8px}.count-board{text-align:right}.count-row{display:flex!important;align-items:center;justify-content:flex-end;gap:5px;margin-top:4px;color:#fff!important}.count-row b{width:12px;margin:0;color:#fff;font-size:9px}.count-light{display:block;width:10px;height:10px;border:1px solid #6a6d73;border-radius:50%}.count-light.on.ball{background:#e7bd1d;border-color:#e7bd1d}.count-light.on.strike{background:#d6d8dc;border-color:#d6d8dc}.count-light.on.out{background:#df4545;border-color:#df4545}.gamecast-side{display:flex;flex-direction:column;gap:10px}.player-panel{padding:15px;background:#202124;display:flex;flex-direction:column}.player-panel strong{margin-top:7px;font-size:14px}.player-panel small{margin-top:4px;color:#898c92;font-size:8px}.batter-panel{background:#1c1d20}.lineup-panel{padding:14px;background:#202124;flex:1}.lineup-panel ol{list-style:none;margin:9px 0 0;padding:0}.lineup-panel li{min-height:24px;display:flex;align-items:center;gap:8px;border-top:1px solid #34363a;font-size:9px}.lineup-panel li span{width:17px;height:17px;border-radius:50%;background:#111;display:grid;place-items:center;color:#ddd;font-size:7px}.lineup-panel .lineup-empty{color:#8f9298;justify-content:center;padding:20px 0}.gamecast-info{min-height:54px;padding:10px 15px;border-top:1px solid #34363a;display:flex;align-items:center;justify-content:space-between;gap:18px}.gamecast-info>div{display:flex;align-items:center;gap:10px}.gamecast-info span{font-size:7px;color:#d0a917;font-weight:950;letter-spacing:.14em}.gamecast-info b{font-size:12px}.gamecast-info strong{font-size:15px;color:#f1c40f}.gamecast-info p{margin:0;color:#92959a;font-size:8px}
.base.occupied{width:16px;height:16px;background:#ef2b2d;border:2px solid #fff;border-radius:50%;transform:none;box-shadow:0 0 0 6px rgba(239,43,45,.25),0 0 16px rgba(239,43,45,.9)}
.base.occupied:after{content:"";position:absolute;width:6px;height:6px;left:3px;top:3px;border-radius:50%;background:#fff}
.game-summary{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin:14px 0 18px}
.game-kpi{background:#fffdf8;border:1px solid #ddd5c8;border-radius:13px;padding:14px}
.game-kpi span{display:block;font-size:8px;letter-spacing:.18em;color:#a77e11;font-weight:900}
.game-kpi strong{display:block;margin-top:7px;font-size:20px}
.game-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.game-card{background:#fffdf8;border:1px solid #ddd5c8;border-radius:15px;padding:17px;box-shadow:0 8px 24px rgba(35,29,18,.04)}
.game-card.live{border-color:#d5aa14;box-shadow:0 0 0 2px rgba(241,196,15,.10)}
.game-head{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px}
.game-time{font-size:10px;color:#746f66}
.game-status{font-size:9px;font-weight:950;border-radius:999px;padding:5px 9px;background:#efebe3;color:#5d574e}
.game-status.live{background:#171717;color:#f1c40f}.game-status.final{background:#ebe7df;color:#333}
.game-status.cancelled{background:#f6dfdf;color:#8b2525}
.matchup{display:grid;grid-template-columns:1fr 56px 1fr;gap:8px;align-items:center}
.team-side{min-width:0}.team-side.right{text-align:right}
.team-name{font-size:18px;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.team-score{font-size:31px;font-weight:950;line-height:1;margin-top:6px}
.vs{text-align:center;color:#9b9387;font-size:10px;font-weight:900}
.game-meta{border-top:1px solid #e4ddd2;margin-top:14px;padding-top:12px;display:flex;justify-content:space-between;gap:12px;font-size:9px;color:#746f66}
.prediction,.handicap{margin-top:11px;padding:10px 12px;border-radius:10px;display:flex;justify-content:space-between;align-items:center;gap:12px}
.prediction{background:#191919;color:#fff}.prediction span{font-size:9px;color:#bbb}
.prediction strong{font-size:14px;color:#f1c40f}
.handicap{background:#fff4c7;border:1px solid #ead276;color:#342b13}
.handicap span{font-size:8px;letter-spacing:.14em;color:#8b7018;font-weight:900}.handicap strong{font-size:12px}
.empty-games{padding:28px;background:#fffdf8;border:1px dashed #d8d0c3;border-radius:14px;color:#746f66;text-align:center;font-size:12px}
.sync-note{margin:10px 0 16px;padding:10px 12px;border-radius:10px;background:#fff7d4;border:1px solid #e6cd69;font-size:10px;color:#65551b}
@media(max-width:850px){.gamecast-content{grid-template-columns:1fr}.gamecast-side{display:grid;grid-template-columns:1fr 1fr}.lineup-panel{grid-column:1/-1}.gamecast-scoreboard{padding:0 14px;grid-template-columns:1fr 68px 1fr}.gamecast-state{position:static;grid-column:1/-1;justify-self:center;margin-top:8px}.score-team{gap:10px}.score-team b{font-size:14px}.score-team strong{font-size:25px}.ballpark{height:270px}.game-summary{grid-template-columns:repeat(2,1fr)}.game-grid{grid-template-columns:1fr}}
@media(max-width:520px){.game-summary{grid-template-columns:1fr 1fr}.team-name{font-size:15px}.team-score{font-size:27px}}
@media(max-width:520px){.gamecast-titlebar small{display:none}.gamecast-scoreboard{grid-template-columns:1fr 52px 1fr}.score-team{gap:6px}.score-team b{font-size:11px}.score-team strong{font-size:21px}.inning-state{font-size:9px}.ballpark{height:230px}.ballpark:before{width:300px;height:300px}.ballpark:after{width:205px;height:205px}.base-1{left:calc(50% + 94px);top:166px}.base-2{top:65px}.base-3{left:calc(50% - 108px);top:166px}.field-footer,.gamecast-info{align-items:flex-start;flex-direction:column}.count-board{text-align:left}.count-row{justify-content:flex-start}.gamecast-side{grid-template-columns:1fr}.lineup-panel{grid-column:auto}.matchup{grid-template-columns:1fr 42px 1fr}.game-meta{flex-direction:column;gap:4px}}
</style>
""",
    unsafe_allow_html=True,
)

refresh_every = "30s" if selected_date == today else None


@st.fragment(run_every=refresh_every)
def render_match_center(target_date: date) -> None:
    current_today = datetime.now(JST).date()
    if target_date == today and current_today != today:
        st.session_state.games_calendar_date = current_today
        st.rerun()
    games, today_payload, predictions = games_for_date(target_date)
    pred_by_game = prediction_index(predictions)
    live_games = [game for game in games if is_live(game)]
    date_relation = "過去の結果" if target_date < today else "本日の試合" if target_date == today else "今後の予定"
    if any(game.get("handicap_source_url") for game in games):
        source_label = "結果・ハンデ取得"
    elif any(str(game.get("date") or "") == str(today_payload.get("date") or "") for game in games):
        source_label = "本番共有データ"
    else:
        source_label = "NPB公式・保存データ"
    st.markdown(
        f"""<div class="game-summary">
  <div class="game-kpi"><span>SELECTED DATE</span><strong>{target_date.strftime('%Y/%m/%d')}</strong></div>
  <div class="game-kpi"><span>VIEW</span><strong>{date_relation}</strong></div>
  <div class="game-kpi"><span>GAMES / LIVE</span><strong>{len(games)} / {len(live_games)}</strong></div>
  <div class="game-kpi"><span>DATA SOURCE</span><strong style="font-size:13px">{source_label}</strong></div>
</div>""",
        unsafe_allow_html=True,
    )
    if live_games:
        st.markdown('<div class="sync-note">● 試合中のため、この試合一覧を30秒ごとに自動更新します。</div>', unsafe_allow_html=True)

    featured_game = select_featured_game(
        games,
        retain_final_hours=(14, 18)
        if target_date == datetime.now(JST).date()
        else None,
    )
    if featured_game:
        featured_key = (
            str(featured_game.get("home") or ""),
            str(featured_game.get("away") or ""),
        )
        render_section("LIVE CENTER", "ダイヤモンド試合速報")
        render_gamecast(
            featured_game,
            pred_by_game.get(featured_key, {}),
            target_date,
        )

    render_section("MATCH CENTER", f"{target_date.strftime('%Y年%m月%d日')}の試合")
    if not games:
        message = "この日の試合結果はまだ取得できていません。" if target_date < today else "この日の試合予定はありません。休養日、または公式日程の更新待ちです。"
        st.markdown(f'<div class="empty-games">{message}</div>', unsafe_allow_html=True)
        return

    cards = []
    for game in games:
        home_name, away_name = str(game.get("home") or "---"), str(game.get("away") or "---")
        home, away = html.escape(home_name), html.escape(away_name)
        venue = html.escape(clean_venue(game.get("venue")))
        game_date = html.escape(str(game.get("date") or target_date.isoformat()))
        label, css_class = status_label(game)
        pred = pred_by_game.get((home_name, away_name), {})
        pick = html.escape(str(pred.get("pick") or ""))
        probability = pred.get("win_probability")
        prediction_html = ""
        if pick:
            probability_label = f"{float(probability):.1f}%" if isinstance(probability, (int, float)) else "--"
            prediction_html = f'<div class="prediction"><span>AI PICK</span><strong>{pick} · {probability_label}</strong></div>'
        result_source = html.escape(str(game.get("result_source") or "NPB公式"))
        cards.append(
            f'''<article class="game-card {"live" if css_class == "live" else ""}">
  <div class="game-head">
    <div class="game-time">{game_date} · {html.escape(str(game.get("time") or "--:--"))} · {venue}</div>
    <div class="game-status {css_class}">{html.escape(label)}</div>
  </div>
  <div class="matchup">
    <div class="team-side"><div class="team-name">{away}</div><div class="team-score">{score_text(game.get("away_score"))}</div></div>
    <div class="vs">VS</div>
    <div class="team-side right"><div class="team-name">{home}</div><div class="team-score">{score_text(game.get("home_score"))}</div></div>
  </div>
  {handicap_html(game, target_date <= today)}
  <div class="game-meta"><span>STATUS: {html.escape(str(game.get("status") or "scheduled"))}</span><span>SOURCE: {result_source}</span></div>
  {prediction_html}
</article>'''
        )
    st.markdown(f'<div class="game-grid">{"".join(cards)}</div>', unsafe_allow_html=True)


render_match_center(selected_date)
st.caption("前日・翌日ボタンまたは日付欄で移動できます。過去日と当日は会員ページのハンデ、未来日は公式の開始時刻・球場を表示します。ハンデは数値が入っている片側だけが対象で、空欄は未掲載または未取得です。")
