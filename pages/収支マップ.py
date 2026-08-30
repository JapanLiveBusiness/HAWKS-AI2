from pathlib import Path
from datetime import date, datetime
import json

import plotly.graph_objects as go
import requests
import streamlit as st

from bet_analytics import SORT_OPTIONS, calculate_hit_rate, sort_bets

st.set_page_config(page_title="収支マップ | HAWKS AI", page_icon="💰", layout="wide")

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
BETS_FILE = DATA_DIR / "bet_records.json"
NPB_API = "https://npb.jp/bis/eng/2026/games/"


def load_bets():
    try:
        data = json.loads(BETS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_bets(bets):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BETS_FILE.write_text(json.dumps(bets, ensure_ascii=False, indent=2), encoding="utf-8")


def yen(value):
    try:
        return f"¥{int(value):,}"
    except (TypeError, ValueError):
        return "-"


def result_label(value):
    return {"win": "WIN", "loss": "LOSE", "push": "PUSH"}.get(value, "未確定")


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_games(selected_date):
    """NPB公式日程ページから選択日の開催試合候補を取得する。取得失敗時は手動入力へフォールバック。"""
    from bs4 import BeautifulSoup

    target = selected_date.strftime("%Y%m%d")
    games = []
    try:
        url = f"https://npb.jp/bis/eng/2026/games/gm{target}.html"
        response = requests.get(url, timeout=8)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        text = soup.get_text(" ", strip=True)
        teams = [
            "Hawks", "Fighters", "Marines", "Eagles", "Buffaloes", "Lions",
            "Giants", "Tigers", "BayStars", "Carp", "Swallows", "Dragons",
        ]
        found = [team for team in teams if team in text]
        for i in range(0, len(found) - 1, 2):
            games.append({"home": found[i], "away": found[i + 1], "time": ""})
    except Exception:
        pass
    return games


st.title("💰 収支マップ")
st.caption("BETした試合の収支確認と、当日のBET・収支を手動登録できます。")

with st.expander("➕ 当日のBET・収支を手動入力", expanded=True):
    selected_date = st.date_input("試合日", value=date.today(), key="manual_bet_date")
    games = fetch_games(selected_date)

    if games:
        game_labels = [f"{g['home']} vs {g['away']}" + (f" ({g['time']})" if g.get('time') else "") for g in games]
        game_choice = st.selectbox("開催試合", game_labels)
        selected_game = games[game_labels.index(game_choice)]
        default_team = selected_game["home"]
        default_opponent = selected_game["away"]
        st.caption("選択した日付のNPB開催試合から選択できます。")
    else:
        st.info("この日付の開催試合を自動取得できませんでした。対戦カードを手動入力できます。")
        default_team = ""
        default_opponent = ""

    with st.form("manual_bet_form", clear_on_submit=False):
        c1, c2 = st.columns(2)
        team = c1.text_input("BET先 / チーム", value=default_team)
        opponent = c2.text_input("対戦相手", value=default_opponent)

        c3, c4, c5 = st.columns(3)
        game_time = c3.time_input("試合開始時刻", value=datetime.strptime("18:00", "%H:%M").time())
        bet_amount = c4.number_input("BET金額（円）", min_value=0, step=1000, value=10000)
        handicap = c5.number_input("ハンディ", step=0.5, value=0.0)

        c6, c7, c8 = st.columns(3)
        status_label = c6.selectbox("状態", ["未確定", "確定"])
        result_display = c7.selectbox("結果", ["未確定", "WIN", "LOSE", "PUSH"])
        profit = c8.number_input("当日の損益（円）", step=1000, value=0)

        c9, c10 = st.columns(2)
        team_score = c9.number_input("BET先チーム得点", min_value=0, step=1, value=0)
        opponent_score = c10.number_input("対戦相手得点", min_value=0, step=1, value=0)
        memo = st.text_area("メモ / その他情報", placeholder="オッズ、BET理由、ブックメーカー、補足など")

        submitted = st.form_submit_button("このBET・収支を保存", type="primary", use_container_width=True)

    if submitted:
        if not team.strip() or not opponent.strip():
            st.error("BET先と対戦相手を入力してください。")
        elif status_label == "確定" and result_display == "未確定":
            st.error("確定BETでは結果（WIN / LOSE / PUSH）を選択してください。")
        else:
            result_map = {"WIN": "win", "LOSE": "loss", "PUSH": "push", "未確定": None}
            record = {
                "id": f"manual-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                "date": selected_date.isoformat(),
                "time": game_time.strftime("%H:%M"),
                "team": team.strip(),
                "opponent": opponent.strip(),
                "handicap": handicap,
                "bet_units": float(bet_amount) / 10000.0,
                "bet_amount": int(bet_amount),
                "status": "final" if status_label == "確定" else "pending",
                "result": result_map[result_display],
                "profit": int(profit) if status_label == "確定" else 0,
                "team_score": int(team_score) if status_label == "確定" else None,
                "opponent_score": int(opponent_score) if status_label == "確定" else None,
                "memo": memo.strip(),
                "source": "manual",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }
            current = load_bets()
            current.append(record)
            save_bets(current)
            st.success(f"{selected_date.isoformat()} {team} vs {opponent} のBETを保存しました。")
            st.rerun()

bets = load_bets()
if not bets:
    st.info("BET記録がまだありません。上のフォームから最初のBETを登録できます。")
    st.stop()

bets = sort_bets(bets, "古い日付順")
settled = [b for b in bets if b.get("status") == "final"]
pending = [b for b in bets if b.get("status") != "final"]

sort_option = st.selectbox(
    "履歴の並び順",
    SORT_OPTIONS,
    key="profit_map_sort",
)
sorted_settled = sort_bets(settled, sort_option)
sorted_pending = sort_bets(pending, sort_option)

if settled:
    wins = sum(1 for b in settled if b.get("result") == "win")
    losses = sum(1 for b in settled if b.get("result") == "loss")
    pushes = sum(1 for b in settled if b.get("result") == "push")
    total_profit = sum(int(b.get("profit", 0) or 0) for b in settled)
    total_bet = sum(float(b.get("bet_amount", abs(float(b.get("bet_units", 0) or 0)) * 10000) or 0) for b in settled)
    decided = wins + losses
    _, decided, hit_rate = calculate_hit_rate(settled)
    roi = (total_profit / total_bet * 100.0) if total_bet else 0.0

    s1, s2, s3, s4, s5 = st.columns(5)
    s1.metric("総収支", yen(total_profit))
    s2.metric("確定BET", f"{len(settled)}試合")
    s3.metric("勝敗", f"{wins}勝 {losses}敗" + (f" {pushes}分" if pushes else ""))
    s4.metric("的中率", f"{hit_rate:.1f}%" if hit_rate is not None else "-")
    s5.metric("ROI", f"{roi:+.1f}%" if total_bet else "-")

    running = 0
    x_values, y_values, hover_values = [], [], []
    for bet in settled:
        profit_value = int(bet.get("profit", 0) or 0)
        running += profit_value
        bet_date, bet_time = str(bet.get("date", "-")), str(bet.get("time", "-"))
        team_name, opponent_name = str(bet.get("team", "-")), str(bet.get("opponent", "-"))
        amount = float(bet.get("bet_amount", abs(float(bet.get("bet_units", 0) or 0)) * 10000) or 0)
        team_score_value, opponent_score_value = bet.get("team_score"), bet.get("opponent_score")
        score = f"{team_score_value} - {opponent_score_value}" if team_score_value is not None and opponent_score_value is not None else "未確定"
        x_values.append(f"{bet_date} {bet_time}")
        y_values.append(running)
        hover_values.append(
            f"<b>{team_name} vs {opponent_name}</b><br>日時: {bet_date} {bet_time}<br>BET先: {team_name}"
            f"<br>ハンディ: {bet.get('handicap', 0)}<br>BET額: {yen(amount)}<br>スコア: {score}"
            f"<br>結果: {result_label(bet.get('result'))}<br>この試合の損益: {yen(profit_value)}"
            f"<br><b>累積収支: {yen(running)}</b>"
        )

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x_values, y=y_values, mode="lines+markers", customdata=hover_values,
                             hovertemplate="%{customdata}<extra></extra>", name="累積収支"))
    fig.add_hline(y=0, line_dash="dash", line_width=1)
    fig.update_layout(xaxis_title="BETした試合", yaxis_title="累積収支（円）", hovermode="closest", height=500,
                      margin=dict(l=20, r=20, t=30, b=30), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    fig.update_yaxes(tickformat=",")
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### BETした試合の詳細")
    for bet in sorted_settled:
        profit_value = int(bet.get("profit", 0) or 0)
        amount = float(bet.get("bet_amount", abs(float(bet.get("bet_units", 0) or 0)) * 10000) or 0)
        team_name, opponent_name = str(bet.get("team", "-")), str(bet.get("opponent", "-"))
        team_score_value, opponent_score_value = bet.get("team_score"), bet.get("opponent_score")
        score = f"{team_score_value} - {opponent_score_value}" if team_score_value is not None and opponent_score_value is not None else "未確定"
        icon = "🟢" if profit_value > 0 else ("🔴" if profit_value < 0 else "⚪")
        title = f"{icon} {bet.get('date', '-')} {bet.get('time', '-')} | {team_name} vs {opponent_name} | {yen(profit_value)}"
        with st.expander(title):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("BET先", team_name)
            c2.metric("BET額", yen(amount))
            c3.metric("ハンディ", str(bet.get("handicap", 0)))
            c4.metric("損益", yen(profit_value))
            st.write(f"**試合スコア:** {score}　｜　**結果:** {result_label(bet.get('result'))}")
            if bet.get("memo"):
                st.write(f"**メモ:** {bet['memo']}")
else:
    st.info("確定済みBETはまだありません。未確定BETは下に表示されます。")

if pending:
    st.markdown("### 未確定BET")
    for bet in sorted_pending:
        amount = float(bet.get("bet_amount", abs(float(bet.get("bet_units", 0) or 0)) * 10000) or 0)
        st.write(f"⏳ {bet.get('date', '-')} {bet.get('time', '-')} ｜ {bet.get('team', '-')} vs {bet.get('opponent', '-')} ｜ "
                 f"BET {yen(amount)} ｜ ハンディ {bet.get('handicap', 0)}")
