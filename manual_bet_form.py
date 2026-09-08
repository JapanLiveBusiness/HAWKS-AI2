"""Shared manual-entry form for the profit map and BET entry page."""
from datetime import datetime
from uuid import uuid4
from zoneinfo import ZoneInfo
import streamlit as st

from bet_analytics import profit_for_result, settle_bet
from bet_store import BetStoreError, append_bet
from manual_bet_defaults import entry_defaults, load_entry_games

JST = ZoneInfo("Asia/Tokyo")


@st.cache_data(ttl=300, show_spinner=False)
def _games(selected_date, cache_paths, today):
    return load_entry_games(selected_date, cache_paths, today=today)


def render_manual_bet_form(bets_file, cache_paths, *, prefix="manual"):
    selected_date = st.date_input("試合日", value=datetime.now(JST).date(), key=f"{prefix}_date")
    games = _games(selected_date, tuple(cache_paths), datetime.now(JST).date())
    selected_game = None
    if games:
        index = st.selectbox(
            "開催試合", range(len(games)),
            format_func=lambda i: f"{games[i]['home']} vs {games[i]['away']} ({games[i].get('time') or '--:--'})",
            key=f"{prefix}_game_{selected_date}",
        )
        selected_game = games[index]
        selection_key = f"{prefix}_side_{selected_date}_{selected_game['home']}_{selected_game['away']}"
        selected_team = st.selectbox("BET先 / チーム", [selected_game["home"], selected_game["away"]], key=selection_key)
    else:
        selected_team = ""
        st.info("この日付の試合を取得できませんでした。対戦・ハンデ・得点を手動入力してください。")
    defaults = entry_defaults(selected_game, selected_team)
    context = (str(selected_date), (selected_game or {}).get("home"), (selected_game or {}).get("away"), selected_team)
    if st.session_state.get(f"{prefix}_context") != context:
        st.session_state[f"{prefix}_context"] = context
        for field, value in defaults.items():
            if field == "time":
                try:
                    value = datetime.strptime(value, "%H:%M").time()
                except (TypeError, ValueError):
                    value = datetime.strptime("18:00", "%H:%M").time()
            st.session_state[f"{prefix}_{field}"] = value
    if defaults["status"] == "確定":
        st.caption("終了済みの試合結果を入力しました。BET先を切り替えると得点とハンデも切り替わります。")
    if defaults["handicap"] is None:
        st.caption("ハンデを取得できませんでした。適用する値を入力してください（ハンデなしは0）。")

    with st.form(f"{prefix}_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        team = c1.text_input("BET先", key=f"{prefix}_team", disabled=bool(games))
        opponent = c2.text_input("対戦相手", key=f"{prefix}_opponent", disabled=bool(games))
        c3, c4, c5 = st.columns(3)
        game_time = c3.time_input("試合開始時刻", key=f"{prefix}_time")
        amount = c4.number_input("BET金額（円）", min_value=0, step=1000, value=10000, key=f"{prefix}_amount")
        handicap = c5.number_input("ハンディ", value=None, step=0.1, key=f"{prefix}_handicap")
        status = st.selectbox("状態", ["未確定", "確定"], key=f"{prefix}_status")
        st.caption("BET先得点からハンデを差し引いて判定します。的中 +BET額の90%、外れ -BET額の100%、PUSH 0円です。")
        c6, c7 = st.columns(2)
        team_score = c6.number_input("BET先チーム得点", min_value=0, value=None, step=1, key=f"{prefix}_team_score")
        opponent_score = c7.number_input("対戦相手得点", min_value=0, value=None, step=1, key=f"{prefix}_opponent_score")
        memo = st.text_area("メモ / その他情報", key=f"{prefix}_memo")
        submitted = st.form_submit_button("このBET・収支を保存", type="primary", width="stretch")
    if not submitted:
        return
    if not team.strip() or not opponent.strip() or team.strip() == opponent.strip():
        st.error("異なる2チームを入力してください。")
        return
    if amount <= 0 or handicap is None:
        st.error("BET金額は1円以上、ハンデは数値で入力してください。")
        return
    final = status == "確定"
    if final and (team_score is None or opponent_score is None):
        st.error("確定するには両チームの得点が必要です。未取得の得点を0として保存することはありません。")
        return
    adjusted, result = settle_bet(team_score, opponent_score, handicap) if final else (None, None)
    record = {
        "id": f"manual-{uuid4().hex}", "date": selected_date.isoformat(),
        "time": game_time.strftime("%H:%M"), "team": team.strip(), "opponent": opponent.strip(),
        "handicap": float(handicap), "bet_units": float(amount) / 10000, "bet_amount": int(amount),
        "status": "final" if final else "pending", "settled": final, "result": result,
        "profit": profit_for_result(result, amount) if final else 0,
        "team_score": int(team_score) if final else None,
        "opponent_score": int(opponent_score) if final else None,
        "adjusted_score": adjusted, "memo": memo.strip(), "source": "manual",
        "created_at": datetime.now(JST).isoformat(timespec="seconds"),
    }
    try:
        append_bet(bets_file, record)
    except BetStoreError as exc:
        st.error(str(exc))
    else:
        st.session_state["bet_notice"] = "BET・収支を1件保存しました。"
        st.rerun()
