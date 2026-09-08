from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import html
from urllib.parse import quote

import streamlit as st

from auth_session import render_account_controls, require_auth0, user_bets_path
from bet_analytics import weekly_bet_summary
from bet_store import BetStoreError, load_bets
from daily_data import load_current_daily_json
from feature_readiness import STATUS_LABELS, feature

JST = ZoneInfo("Asia/Tokyo")
REPO_DATA_DIR = Path(__file__).resolve().parent / "data"

st.set_page_config(
    page_title="AI BASEBALL STUDIO | GAME INTELLIGENCE",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)
auth_user = require_auth0()
render_account_controls(auth_user)


def safe(value, fallback="--"):
    if value in (None, ""):
        value = fallback
    return html.escape(str(value))


def format_data_timestamp(value):
    """Render source timestamps consistently in local time without exposing raw ISO data."""
    if value in (None, ""):
        return "同期待ち"
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=JST)
        return parsed.astimezone(JST).strftime("%Y/%m/%d %H:%M JST")
    except (TypeError, ValueError):
        return safe(value)


predictions = load_current_daily_json("today_ai_predictions.json", {"games": []})
npb_today = load_current_daily_json("npb_today.json", {"games": []})
write_data_dir = Path("/app/data") if Path("/app/data").exists() else REPO_DATA_DIR
try:
    bet_records = load_bets(user_bets_path(write_data_dir, auth_user))
except BetStoreError:
    bet_records = []

prediction_games = sorted(
    predictions.get("games") or [],
    key=lambda game: game.get("rank", 999),
)
today_games = npb_today.get("games") or []
best = prediction_games[0] if prediction_games else {}
now = datetime.now(JST)

best_pick = safe(best.get("pick"), "データ同期中")
best_match = safe(
    f"{best.get('home', '---')} vs {best.get('away', '---')}"
    if best
    else "本日の予測データを取得中"
)
best_prob = best.get("win_probability")
best_prob_label = (
    f"{float(best_prob):.1f}%"
    if isinstance(best_prob, (int, float))
    else "--"
)
updated_at = format_data_timestamp(
    predictions.get("updated_at") or npb_today.get("updated_at")
)
weekly = weekly_bet_summary(bet_records, now.date())
weekly_profit = weekly["profit"]
profit_label = (
    f"+¥{weekly_profit:,}" if weekly_profit > 0
    else f"-¥{abs(weekly_profit):,}" if weekly_profit < 0
    else "¥0"
)
week_label = (
    f"{weekly['week_start'].strftime('%m/%d')}〜"
    f"{weekly['week_end'].strftime('%m/%d')}"
)

teams = [
    ("H", "ソフトバンク"), ("F", "日本ハム"), ("E", "楽天"),
    ("L", "西武"), ("M", "ロッテ"), ("B", "オリックス"),
    ("G", "巨人"), ("T", "阪神"), ("DB", "DeNA"),
    ("C", "広島"), ("S", "ヤクルト"), ("D", "中日"),
]

rank_cards = []
for idx, game in enumerate(prediction_games[:3], start=1):
    probability = game.get("win_probability")
    probability_label = (
        f"{float(probability):.1f}%"
        if isinstance(probability, (int, float))
        else "--"
    )
    rank_cards.append(
        f"""
        <article class="ranking-card">
          <div class="ranking-no">{idx}</div>
          <div class="ranking-copy">
            <strong>{safe(game.get('pick'))}</strong>
            <span>{safe(game.get('home'))} vs {safe(game.get('away'))}</span>
          </div>
          <div class="ranking-score"><b>{probability_label}</b><small>AI勝率</small></div>
        </article>
        """.strip()
    )

rank_html = "".join(rank_cards) or """
<div class="empty-state">
  <b>本日の予測データを準備中</b>
  <span>データ取得後、勝率の高い順に最大3試合を表示します。</span>
</div>
"""

team_html = "".join(
    f'<a class="team" href="/球団別詳細?team={quote(name)}" target="_self"><b>{abbr}</b><span>{name}</span></a>'
    for abbr, name in teams
)

quick_features = {
    key: feature(key) for key in ("predictions", "bet_entry", "performance", "ai_detail")
}


def readiness_badge(key):
    item = quick_features[key]
    if item.status == "live":
        return ""
    return f'<span class="readiness {item.status}">{STATUS_LABELS[item.status]}</span>'

st.markdown(
    r"""
<style>
:root{
  --bg:#f4f1ea;--paper:#fffdf9;--ink:#111827;--muted:#6b7280;
  --line:#ddd6c9;--gold:#f3c400;--gold-dark:#a97900;
  --dark:#121212;--soft:#f8f6f1;
}
[data-testid="stHeader"],[data-testid="stToolbar"],footer,[data-testid="stSidebar"]{display:none!important}
[data-testid="stAppViewContainer"]{background:var(--bg)!important;color:var(--ink)!important;overflow-x:hidden!important}
.block-container{box-sizing:border-box;max-width:1460px!important;padding:0 28px 42px!important}

.topbar{box-sizing:border-box;min-height:68px;margin:0 -28px;background:var(--dark);color:#fff;display:flex;align-items:center;padding:0 28px;border-bottom:2px solid rgba(243,196,0,.55);gap:24px}
.brand{display:flex;align-items:center;gap:12px;min-width:270px}.logo{width:40px;height:40px;border-radius:11px;background:var(--gold);color:#111;display:grid;place-items:center;font-size:20px;font-weight:1000;font-style:italic}.brand-title{font-size:14px;font-weight:950;letter-spacing:.13em}.brand-sub{font-size:7px;color:#9ca3af;letter-spacing:.36em;margin-top:4px}
.nav{display:flex;justify-content:center;align-items:center;gap:26px;flex:1}.nav a{font-size:10px;color:#a7a7a7;white-space:nowrap;text-decoration:none}.nav a:hover{color:#fff}.nav .active{color:var(--gold);font-weight:950}.status{font-size:9px;border:1px solid #404040;border-radius:999px;padding:8px 11px;color:#e5e7eb}

.dashboard{padding-top:18px}.overview{display:grid;grid-template-columns:minmax(0,1.55fr) minmax(330px,.85fr);gap:14px;align-items:stretch}
.hero{min-height:232px;border-radius:20px;padding:30px 34px;position:relative;overflow:hidden;color:#fff;background:radial-gradient(circle at 84% 12%,rgba(214,165,30,.48),transparent 35%),linear-gradient(135deg,#101010 0%,#17130c 58%,#3c2c0a 100%);display:flex;flex-direction:column;justify-content:center}
.hero:after{content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:35px 35px;pointer-events:none}.eyebrow,.hero h1,.hero p,.chips{position:relative;z-index:1}.eyebrow{font-size:9px;letter-spacing:.26em;color:#f6d65c;font-weight:950}.hero h1{font-size:45px!important;line-height:1!important;margin:12px 0 12px!important;color:#fff!important;letter-spacing:-.04em;font-style:italic}.hero h1 em{color:var(--gold);font-style:normal}.hero p{font-size:12px;line-height:1.75;color:#d1d5db;max-width:690px;margin:0}.chips{display:flex;gap:7px;flex-wrap:wrap;margin-top:20px}.chip{font-size:9px;border:1px solid rgba(255,255,255,.24);border-radius:999px;padding:6px 10px;background:rgba(0,0,0,.2)}.chip.hot{background:var(--gold);border-color:var(--gold);color:#111;font-weight:950}

.featured{border-radius:20px;background:var(--dark);color:#fff;padding:24px;display:flex;flex-direction:column;justify-content:space-between;box-shadow:0 14px 30px rgba(17,24,39,.12)}.featured-label{font-size:9px;letter-spacing:.22em;color:#f6d65c;font-weight:950}.featured-match{font-size:12px;color:#aeb4bd;margin-top:16px}.featured-pick{font-size:31px;font-weight:950;line-height:1.15;margin-top:5px}.featured-bottom{display:flex;align-items:end;justify-content:space-between;border-top:1px solid #303030;margin-top:22px;padding-top:18px}.featured-bottom small{color:#aeb4bd;font-size:9px}.featured-bottom strong{font-size:34px;color:var(--gold)}

.kpi-row{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:14px}.kpi{background:var(--paper);border:1px solid var(--line);border-radius:15px;padding:17px 19px;display:flex;align-items:center;justify-content:space-between;min-height:83px}.kpi-copy span{font-size:8px;letter-spacing:.18em;color:var(--gold-dark);font-weight:950}.kpi-copy b{display:block;font-size:25px;margin-top:5px}.kpi small{font-size:9px;color:var(--muted);text-align:right;line-height:1.45}

.content-grid{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(320px,.75fr);gap:14px;margin-top:14px}.panel{background:rgba(255,255,255,.64);border:1px solid var(--line);border-radius:18px;padding:18px}.panel-head{display:flex;align-items:end;justify-content:space-between;margin-bottom:14px}.panel-head h2{font-size:21px!important;margin:0!important;color:var(--ink)!important}.panel-head span{font-size:8px;letter-spacing:.15em;color:var(--muted)}
.ranking-list{display:grid;gap:8px}.ranking-card{display:grid;grid-template-columns:42px 1fr 90px;gap:12px;align-items:center;background:var(--paper);border:1px solid var(--line);border-radius:13px;padding:13px 15px}.ranking-no{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;background:#171717;color:var(--gold);font-weight:950}.ranking-copy{display:flex;flex-direction:column}.ranking-copy strong{font-size:16px}.ranking-copy span{font-size:10px;color:var(--muted);margin-top:3px}.ranking-score{text-align:right}.ranking-score b{display:block;font-size:20px}.ranking-score small{font-size:8px;color:var(--muted)}.empty-state{background:var(--paper);border:1px dashed #cfc6b7;border-radius:13px;padding:22px;display:flex;flex-direction:column;gap:5px}.empty-state b{font-size:14px}.empty-state span{font-size:10px;color:var(--muted)}

.actions{display:grid;gap:8px}.action{text-decoration:none;color:inherit;background:var(--paper);border:1px solid var(--line);border-radius:13px;padding:14px 15px;display:grid;grid-template-columns:35px 1fr 18px;align-items:center;gap:10px;min-height:69px}.action.primary{background:#171717;color:#fff;border-color:#282828}.action-icon{width:34px;height:34px;border-radius:9px;background:#f5ebbd;color:#8a6700;display:grid;place-items:center;font-weight:950}.action.primary .action-icon{background:var(--gold);color:#111}.action-copy b{display:flex;align-items:center;gap:7px;font-size:14px}.action-copy>span{display:block;font-size:9px;color:var(--muted);margin-top:3px}.action.primary .action-copy>span{color:#aeb4bd}.action-arrow{color:#b08b00;font-weight:950}.readiness{display:inline-flex!important;margin:0!important;padding:2px 6px;border-radius:999px;font-size:7px!important;line-height:1.2;font-weight:900;background:#e8e3d8;color:#625d54!important}.readiness.live{background:#dff4e7;color:#176b3a!important}.readiness.beta{background:#fff0bd;color:#765800!important}.readiness.preview{background:#e9e2ff;color:#5b3ca5!important}

.teams-panel{margin-top:14px}.teams{display:grid;grid-template-columns:repeat(12,1fr);gap:7px}.team{background:var(--paper);border:1px solid var(--line);border-radius:10px;min-height:68px;padding:8px 5px;text-align:center;display:flex;flex-direction:column;justify-content:center;text-decoration:none;color:inherit;transition:.15s ease}.team:hover{border-color:var(--gold);transform:translateY(-2px);box-shadow:0 5px 14px rgba(169,121,0,.12)}.team b{width:30px;height:30px;border-radius:50%;background:#171717;color:var(--gold);display:grid;place-items:center;margin:0 auto 5px;font-size:9px}.team span{font-size:7px;font-weight:850;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}

.system-row{display:grid;grid-template-columns:minmax(0,1fr) 310px;gap:14px;margin-top:14px}.system{background:#171717;border-radius:15px;color:#fff;padding:17px 20px;display:flex;align-items:center;justify-content:space-between}.system strong{font-size:15px}.system p{font-size:9px;color:#aeb4bd;margin:4px 0 0}.live{font-size:9px;color:var(--gold);border:1px solid #444;border-radius:999px;padding:8px 11px;font-weight:950}.domain{background:var(--paper);border:1px solid var(--line);border-radius:15px;padding:17px}.domain strong{font-size:11px}.domain div{font-size:9px;color:var(--muted);margin-top:5px;overflow-wrap:anywhere}

div[data-testid="stPageLink"] a{background:var(--paper)!important;color:var(--ink)!important;border:1px solid var(--line)!important;border-radius:12px!important;font-weight:850!important;padding:11px 14px!important}div[data-testid="stPageLink"] a:hover{border-color:var(--gold)!important;box-shadow:0 4px 14px rgba(169,121,0,.10)!important}.links{margin-top:14px}

@media(max-width:1100px){.topbar{flex-wrap:wrap;padding-top:10px;padding-bottom:9px;gap:8px 18px}.brand{flex:1}.nav{order:3;flex-basis:100%;justify-content:flex-start;gap:22px;overflow-x:auto;padding:8px 0 2px;scrollbar-width:none}.nav::-webkit-scrollbar{display:none}.overview,.content-grid{grid-template-columns:1fr}.featured{min-height:200px}.teams{grid-template-columns:repeat(6,1fr)}}
@media(max-width:700px){.block-container{padding:0 10px 30px!important}.topbar{margin:0 -10px;padding:9px 12px 8px}.brand-title{font-size:12px}.status{display:none}.nav{gap:18px}.nav a{font-size:9px}.dashboard{padding-top:10px}.hero{min-height:210px;padding:22px 18px}.hero h1{font-size:clamp(28px,9vw,34px)!important}.featured{min-height:180px;padding:20px}.featured-pick{font-size:26px}.kpi-row{grid-template-columns:1fr}.kpi{min-height:74px}.content-grid{gap:10px}.panel{padding:13px}.panel-head{align-items:flex-start;gap:8px}.ranking-card{grid-template-columns:38px minmax(0,1fr) 72px;padding:11px}.ranking-score b{font-size:17px}.teams{grid-template-columns:repeat(4,1fr)}.system-row{grid-template-columns:1fr}.system{align-items:flex-start;gap:10px}.system p{max-width:220px}}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="topbar">
  <div class="brand"><div class="logo">M</div><div><div class="brand-title">AI BASEBALL STUDIO</div><div class="brand-sub">GAME INTELLIGENCE</div></div></div>
  <nav class="nav"><a class="active" href="/" target="_self">HOME</a><a href="/試合" target="_self">GAMES</a><a href="/本日のAI予想" target="_self">AI PREDICTION</a><a href="/予想結果" target="_self">RESULTS</a><a href="/BET入力" target="_self">BET</a><a href="/収支マップ" target="_self">PERFORMANCE</a><a href="/球団別詳細" target="_self">TEAMS</a><a href="/AI詳細" target="_self">AI DETAIL</a></nav>
  <div class="status">JST {now.strftime('%H:%M')} · LIVE</div>
</div>

<main class="dashboard">
  <section class="overview">
    <div class="hero">
      <div class="eyebrow">AI BASEBALL STUDIO / NPB 2026</div>
      <h1>GAME <em>INTELLIGENCE</em></h1>
      <p>今日の試合、AI予測、ハンデ、BET、収支を一つの画面で確認。最重要情報から詳細分析へ、迷わず進めるダッシュボードです。</p>
      <div class="chips"><span class="chip hot">PRODUCTION</span><span class="chip">UPDATE {now.strftime('%H:%M:%S')}</span><span class="chip">DATA {updated_at}</span></div>
    </div>
    <aside class="featured">
      <div><div class="featured-label">TODAY'S BEST AI PICK</div><div class="featured-match">{best_match}</div><div class="featured-pick">{best_pick}</div></div>
      <div class="featured-bottom"><small>本日の最高AI評価</small><strong>{best_prob_label}</strong></div>
    </aside>
  </section>

  <section class="kpi-row">
    <div class="kpi"><div class="kpi-copy"><span>TODAY GAMES</span><b>{len(today_games)}</b></div><small>NPB<br>対象試合</small></div>
    <div class="kpi"><div class="kpi-copy"><span>AI PREDICTIONS</span><b>{len(prediction_games)}</b></div><small>取得済み<br>予測カード</small></div>
    <div class="kpi"><div class="kpi-copy"><span>WEEKLY P/L</span><b>{profit_label}</b></div><small>{week_label}<br>確定BET {weekly['final_count']}件</small></div>
  </section>

  <section class="content-grid">
    <div class="panel">
      <div class="panel-head"><h2>今日のAIランキング</h2><span>TOP 3 / CONFIDENCE</span></div>
      <div class="ranking-list">{rank_html}</div>
    </div>
    <div class="panel">
      <div class="panel-head"><h2>クイック操作</h2><span>WORKSPACE</span></div>
      <div class="actions">
        <a class="action primary" href="/本日のAI予想" target="_self"><div class="action-icon">AI</div><div class="action-copy"><b>AI予測を見る {readiness_badge('predictions')}</b><span>勝率・予測スコア・信頼度</span></div><div class="action-arrow">›</div></a>
        <a class="action" href="/BET入力" target="_self"><div class="action-icon">＋</div><div class="action-copy"><b>BETを入力 {readiness_badge('bet_entry')}</b><span>登録・編集・削除・未確定BETの精算</span></div><div class="action-arrow">›</div></a>
        <a class="action" href="/収支マップ" target="_self"><div class="action-icon">¥</div><div class="action-copy"><b>収支を確認 {readiness_badge('performance')}</b><span>的中率・ROI・累積収支</span></div><div class="action-arrow">›</div></a>
        <a class="action" href="/AI詳細" target="_self"><div class="action-icon">◎</div><div class="action-copy"><b>AI詳細を開く {readiness_badge('ai_detail')}</b><span>公式速報・状況補正・勝率シミュレーター</span></div><div class="action-arrow">›</div></a>
      </div>
    </div>
  </section>

  <section class="panel teams-panel">
    <div class="panel-head"><h2>12球団一覧</h2><span>球団を選択して戦績・次戦・直近成績を表示</span></div>
    <div class="teams">{team_html}</div>
  </section>

  <section class="system-row">
    <div class="system"><div><strong>AI prediction engine</strong><p>先発・直近成績・対戦相性・球場・ハンデ・BET結果を継続同期</p></div><div class="live">● MONITORING</div></div>
    <div class="domain"><strong>Production</strong><div>ai-baseball-studio.f-polaris.jp</div></div>
  </section>
</main>
""",
    unsafe_allow_html=True,
)
