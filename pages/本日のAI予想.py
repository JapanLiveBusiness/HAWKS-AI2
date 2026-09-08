import streamlit as st

from daily_data import load_current_daily_json
from daily_board import coverage, merge_daily_board
from studio_theme import apply_studio_theme, render_topbar, render_hero, render_section, render_nav_links

st.set_page_config(page_title="AI予測 | MY AI BASEBALL", page_icon="⚾", layout="wide")
apply_studio_theme()
render_topbar("AI PREDICTION")
render_hero(
    "本日のAI予測",
    "勝率・予想スコア・信頼度を1画面で比較。AI Baseball Studioのメインデザインに統一しています。",
    kicker="TODAY / NPB / AI PREDICTION",
    accent="AI予測",
)
render_nav_links()

@st.cache_data(ttl="1m", max_entries=4)
def load_json(name, fallback):
    return load_current_daily_json(name, fallback)


payload = load_json("today_ai_predictions.json", {"games": []})
schedule = load_json("npb_today.json", {"games": []})
games = merge_daily_board(schedule, payload)
status = coverage(games)
display_date = schedule.get("date") or payload.get("date") or ""
render_section("DAILY BOARD", f"{display_date} NPB 全開催試合の予想と結果")

source_url = next((row.get("source_url") for row in schedule.get("games") or [] if row.get("source_url")), "https://handenomori.com/jpb/")
st.markdown(f"ハンデ情報: [ハンデの森]({source_url})（各試合の開始100分前までに一度取得し、取得値を固定）")

if not games:
    st.info("本日の試合データを同期中です。")
    st.stop()

if not status["complete"]:
    st.warning(f"全{status['games']}試合中、予想済みは{status['predicted']}試合です。未生成の試合は同期後に表示されます。")

for game in games:
    rank = game.get("rank")
    home = game.get("home", "-")
    away = game.get("away", "-")
    pick = game.get("pick", "-")
    prob = game.get("win_probability", 0)
    score = game.get("predicted_score", "-")
    confidence = game.get("confidence", "-")
    home_score = game.get("home_score")
    away_score = game.get("away_score")
    result = game.get("actual_result", "未確定")
    verified = game.get("verified")

    c1, c2, c3, c4 = st.columns([0.7, 2.4, 1.8, 1.4])
    with c1:
        st.markdown(f'<div class="studio-rank">{rank if rank is not None else "—"}</div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f"### {home} vs {away}")
        st.caption(f"予想スコア {score}")
    with c3:
        st.metric("勝利予想", pick, f"{prob}%")
    with c4:
        st.metric("信頼度", confidence)
    if pick and isinstance(prob, (int, float)):
        st.progress(max(0, min(100, int(prob))) / 100)
    else:
        st.caption("予想生成待ち")
    if result != "未確定":
        verdict = "的中" if verified is True else "外れ" if verified is False else "判定対象外"
        st.markdown(f"結果: **{away} {away_score} - {home_score} {home}** ／ 勝者 **{result}** ／ {verdict}")
    else:
        st.caption(f"試合結果: 未確定（{game.get('status') or '開始前'}）")
    st.divider()

ranked = [game for game in games if game.get("pick")]
best = max(ranked, key=lambda row: float(row.get("win_probability") or 0)) if ranked else None
render_section("TOP RECOMMENDATION", "本日の最上位予想")
if best:
    left, mid, right = st.columns([1.6, 1, 1])
    left.markdown(f"## {best.get('pick', '-')}")
    left.caption(f"{best.get('home', '-')} vs {best.get('away', '-')} / 予想スコア {best.get('predicted_score', '-')}")
    mid.metric("推定勝率", f"{best.get('win_probability', '-')}%")
    right.metric("信頼度", best.get("confidence", "-"))
else:
    st.info("予想生成後に最上位予想を表示します。")

st.caption("※勝率・予想スコアはAI予測値であり、試合結果を保証するものではありません。")
