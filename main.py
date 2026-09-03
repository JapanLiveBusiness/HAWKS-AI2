from datetime import date, datetime
from zoneinfo import ZoneInfo
from pathlib import Path
import json
import os
import re

import requests
import streamlit as st
from bs4 import BeautifulSoup

st.set_page_config(
    page_title="ホークス応援 AI勝率シミュレーター",
    page_icon="⚾",
    layout="wide",
)

JST = ZoneInfo("Asia/Tokyo")
DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data")).expanduser().resolve()
BETS_FILE = DATA_DIR / "bet_records.json"

TEAM_NAMES = [
    "ソフトバンク", "日本ハム", "楽天", "西武", "ロッテ", "オリックス",
    "巨人", "阪神", "DeNA", "広島", "ヤクルト", "中日",
]


def load_bets():
    try:
        data = json.loads(BETS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_bets(records):
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    BETS_FILE.write_text(
        json.dumps(records, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@st.cache_data(ttl=1800, show_spinner=False)
def fetch_npb_games(selected_date):
    """NPB公式の月間詳細日程から指定日の開催試合を取得。"""
    year = selected_date.year
    month = selected_date.month
    target_md = f"{selected_date.month}/{selected_date.day}"
    url = f"https://npb.jp/games/{year}/schedule_{month:02d}_detail.html"
    games = []

    try:
        r = requests.get(
            url,
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=10,
        )
        r.raise_for_status()
        soup = BeautifulSoup(r.content, "html.parser")

        current_date = None
        for tr in soup.find_all("tr"):
            text = " ".join(tr.get_text(" ", strip=True).split())
            dm = re.search(r"(\d{1,2})/(\d{1,2})", text)
            if dm:
                current_date = f"{int(dm.group(1))}/{int(dm.group(2))}"

            if current_date != target_md:
                continue

            found = []
            for team in TEAM_NAMES:
                if team in text and team not in found:
                    found.append(team)

            if len(found) < 2:
                continue

            tm = re.search(r"(\d{1,2}:\d{2})", text)
            game_time = tm.group(1) if tm else "18:00"

            pair = (found[0], found[1], game_time)
            if pair not in [(g["team1"], g["team2"], g["time"]) for g in games]:
                games.append({
                    "team1": found[0],
                    "team2": found[1],
                    "time": game_time,
                })
    except Exception:
        pass

    return games


st.markdown("## ➕ 当日のBET・収支を手動入力")
st.caption("日付を選ぶと、その日のNPB開催試合から選択できます。保存内容は収支マップへ即時反映されます。")

selected_date = st.date_input(
    "試合日",
    value=datetime.now(JST).date(),
    key="top_manual_bet_date",
)

games = fetch_npb_games(selected_date)

if games:
    labels = [
        f"{g['team1']} vs {g['team2']}（{g['time']}）"
        for g in games
    ]
    selected_label = st.selectbox(
        "当日の開催試合",
        labels,
        key="top_manual_game",
    )
    selected_game = games[labels.index(selected_label)]
    team_options = [selected_game["team1"], selected_game["team2"]]
    default_time = selected_game["time"]
else:
    st.info("指定日の試合を自動取得できませんでした。チーム名を手動入力できます。")
    team_options = []
    default_time = "18:00"

with st.form("top_manual_bet_form", clear_on_submit=False):
    c1, c2 = st.columns(2)

    if team_options:
        bet_team = c1.selectbox("BET先", team_options)
        opponent = team_options[1] if bet_team == team_options[0] else team_options[0]
        c2.text_input("対戦相手", value=opponent, disabled=True)
    else:
        bet_team = c1.text_input("BET先 / チーム")
        opponent = c2.text_input("対戦相手")

    try:
        default_time_obj = datetime.strptime(default_time, "%H:%M").time()
    except ValueError:
        default_time_obj = datetime.strptime("18:00", "%H:%M").time()

    c3, c4, c5 = st.columns(3)
    game_time = c3.time_input("開始時刻", value=default_time_obj)
    bet_amount = c4.number_input(
        "BET金額（円）",
        min_value=0,
        value=10000,
        step=1000,
    )
    handicap = c5.number_input("ハンディ", value=0.0, step=0.5)

    c6, c7, c8 = st.columns(3)
    status_label = c6.selectbox("状態", ["未確定", "確定"])
    result_label = c7.selectbox("結果", ["未確定", "WIN", "LOSE", "PUSH"])
    profit = c8.number_input("損益（円）", value=0, step=1000)

    c9, c10 = st.columns(2)
    team_score = c9.number_input("BET先チーム得点", min_value=0, value=0, step=1)
    opponent_score = c10.number_input("対戦相手得点", min_value=0, value=0, step=1)

    memo = st.text_area(
        "その他情報",
        placeholder="オッズ、BET理由、ブックメーカー、補足など",
    )

    submitted = st.form_submit_button(
        "BET・収支を保存",
        type="primary",
        use_container_width=True,
    )

if submitted:
    if not str(bet_team).strip() or not str(opponent).strip():
        st.error("BET先と対戦相手を入力してください。")
    elif status_label == "確定" and result_label == "未確定":
        st.error("確定の場合は WIN / LOSE / PUSH を選択してください。")
    else:
        result_map = {
            "WIN": "win",
            "LOSE": "loss",
            "PUSH": "push",
            "未確定": None,
        }
        records = load_bets()
        records.append({
            "id": f"manual-{datetime.now(JST).strftime('%Y%m%d%H%M%S%f')}",
            "date": selected_date.isoformat(),
            "time": game_time.strftime("%H:%M"),
            "team": str(bet_team).strip(),
            "opponent": str(opponent).strip(),
            "handicap": float(handicap),
            "bet_units": float(bet_amount) / 10000.0,
            "bet_amount": int(bet_amount),
            "status": "final" if status_label == "確定" else "pending",
            "result": result_map[result_label],
            "profit": int(profit) if status_label == "確定" else 0,
            "team_score": int(team_score) if status_label == "確定" else None,
            "opponent_score": int(opponent_score) if status_label == "確定" else None,
            "memo": memo.strip(),
            "source": "manual-top",
            "created_at": datetime.now(JST).isoformat(timespec="seconds"),
        })
        save_bets(records)
        st.success("BET・収支を保存しました。収支マップにも反映されています。")

st.divider()

# app.py側のset_page_configは2回目になるため、この実行中だけno-op化する。
_original_set_page_config = st.set_page_config
st.set_page_config = lambda *args, **kwargs: None
try:
    exec(
        compile(
            Path(__file__).with_name("app.py").read_text(encoding="utf-8"),
            str(Path(__file__).with_name("app.py")),
            "exec",
        ),
        globals(),
        globals(),
    )
finally:
    st.set_page_config = _original_set_page_config
