from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st

from prediction_metrics import build_prediction_metrics
from prediction_results import archive_predictions, backfill_season_predictions, build_performance, merge_prediction_archives, settle_predictions
from result_sources import load_final_results
from studio_theme import apply_studio_theme, render_hero, render_nav_links, render_section, render_topbar

PROD_DATA_DIR = Path("/app/data")
REPO_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SHARED_DATA_DIR = Path(os.getenv("AI_BASEBALL_SHARED_DATA_DIR", "/app/shared-data"))

st.set_page_config(
    page_title="予想結果 | AI BASEBALL STUDIO",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="collapsed",
)


def active_data_dir() -> Path:
    return PROD_DATA_DIR if PROD_DATA_DIR.exists() else REPO_DATA_DIR


def pct(value):
    return "--" if value is None else f"{float(value):.1f}%"


def brier_label(value):
    return "--" if value is None else f"{float(value):.4f}"


def raw_pick_probability(row):
    value = row.get("raw_home_win_probability")
    if value is None:
        return None
    probability = float(value)
    return probability if row.get("pick") == row.get("home") else 100.0 - probability


apply_studio_theme()
render_topbar("RESULTS / VERIFIED")
render_hero(
    "予想結果",
    "試合前に固定したAI予測と実際の勝敗を照合します。結果確定後に予測値を書き換えず、的中率と確率精度を検証します。",
    kicker="AI BASEBALL STUDIO / VERIFICATION",
    accent="結果",
)
render_nav_links()

shared_available = SHARED_DATA_DIR.exists()
metrics = build_prediction_metrics(active_data_dir(), SHARED_DATA_DIR if shared_available else None)
games = metrics.get("games") or []
verified_count = int(metrics.get("verified_count") or 0)
hits = int(metrics.get("hits") or 0)
hit_rate = metrics.get("hit_rate")
brier = metrics.get("brier_score")
misses = verified_count - hits

high_conf = [g for g in games if abs(float(g.get("probability", 50)) - 50) >= 10]
high_hits = sum(1 for g in high_conf if g.get("hit"))
high_rate = (high_hits / len(high_conf) * 100.0) if high_conf else None

st.markdown(
    """
<style>
.result-kpis{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:14px 0 20px}
.result-kpi{background:#fffdf8;border:1px solid #ddd5c8;border-radius:13px;padding:15px}
.result-kpi span{display:block;font-size:8px;letter-spacing:.16em;color:#a77e11;font-weight:900}
.result-kpi strong{display:block;font-size:24px;margin-top:7px}
.result-table{display:flex;flex-direction:column;gap:8px}
.result-row{display:grid;grid-template-columns:120px 1fr 110px 90px 90px;align-items:center;gap:10px}
.result-row{background:#fffdf8;border:1px solid #ddd5c8;border-radius:12px;padding:12px 14px}
.result-row.hit{border-left:4px solid #2f8f57}.result-row.miss{border-left:4px solid #b64848}
.result-date{font-size:10px;color:#746f66}.result-match strong{font-size:14px}
.result-match span{display:block;font-size:9px;color:#746f66;margin-top:3px}
.result-prob{font-weight:900;text-align:right}.result-actual{text-align:center;font-weight:900}
.result-badge{justify-self:end;border-radius:999px;padding:5px 9px;font-size:9px;font-weight:950}
.result-badge.hit{background:#e8f6ee;color:#217043}.result-badge.miss{background:#fdecec;color:#9d3636}
.empty-results{padding:28px;background:#fffdf8;border:1px dashed #d8d0c3;border-radius:14px;color:#746f66;text-align:center;font-size:12px}
.verify-note{padding:11px 13px;border-radius:10px;background:#191919;color:#fff;font-size:10px;line-height:1.6;margin-bottom:16px}
.verify-note b{color:#f1c40f}
@media(max-width:980px){.result-kpis{grid-template-columns:repeat(3,1fr)}.result-row{grid-template-columns:100px 1fr 90px 72px}}
@media(max-width:980px){.result-badge{display:none}}
@media(max-width:650px){.result-kpis{grid-template-columns:1fr 1fr}.result-row{grid-template-columns:1fr 78px}}
@media(max-width:650px){.result-date{grid-column:1/-1}.result-match{grid-column:1}.result-prob{grid-column:2}}
@media(max-width:650px){.result-actual{grid-column:1/-1;text-align:left}.result-badge{display:none}}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    f"""
<div class="result-kpis">
  <div class="result-kpi"><span>VERIFIED</span><strong>{verified_count}</strong></div>
  <div class="result-kpi"><span>HITS</span><strong>{hits}</strong></div>
  <div class="result-kpi"><span>MISSES</span><strong>{misses}</strong></div>
  <div class="result-kpi"><span>HIT RATE</span><strong>{pct(hit_rate)}</strong></div>
  <div class="result-kpi"><span>BRIER SCORE</span><strong>{brier_label(brier)}</strong></div>
</div>
<div class="verify-note"><b>高信頼帯</b>：60%以上または40%以下の予測を対象にした的中率は <b>{pct(high_rate)}</b>（{high_hits}/{len(high_conf)}）です。Brier Scoreは低いほど確率予測の精度が高い指標です。</div>
""",
    unsafe_allow_html=True,
)

render_section("VERIFIED RESULTS", "試合別の予想結果")

jst_today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
result_period = st.radio(
    "表示する試合日",
    options=("今日", "前日", "すべて"),
    horizontal=True,
    key="prediction_result_period",
)
target_result_date = {
    "今日": jst_today.isoformat(),
    "前日": (jst_today - timedelta(days=1)).isoformat(),
}.get(result_period)
display_games = (
    [
        game
        for game in games
        if str(game.get("date") or "")[:10] == target_result_date
    ]
    if target_result_date
    else games
)
if target_result_date:
    st.caption(f"{target_result_date} の確定済み予想結果を表示しています。")

if shared_available:
    shared_games = int(metrics.get("shared_count") or 0)
    st.success(
        f"研究環境（8502）の共有データを参照中です。共有履歴 {shared_games}件を本番データと統合しています。",
        icon=":material/sync:",
    )
    st.caption("参照元: http://100.124.205.15:8502/ ／ 読み取り専用で接続")
else:
    st.caption("研究環境（8502）の共有データが未接続のため、本番保存データを表示しています。")

if not display_games:
    empty_message = (
        f"{target_result_date} の検証可能な終了試合はありません。"
        if target_result_date
        else "検証可能な終了試合がまだありません。試合結果が保存されると自動的に集計されます。"
    )
    st.markdown(
        f'<div class="empty-results">{empty_message}</div>',
        unsafe_allow_html=True,
    )
else:
    rows = []
    for game in sorted(display_games, key=lambda x: str(x.get("date") or ""), reverse=True):
        hit = bool(game.get("hit"))
        cls = "hit" if hit else "miss"
        badge = "的中" if hit else "外れ"
        rows.append(
            f'''<div class="result-row {cls}">
  <div class="result-date">{game.get('date') or '--'}</div>
  <div class="result-match"><strong>ソフトバンク vs {game.get('opponent') or '--'}</strong><span>GAME ID: {game.get('game_id') or '--'}</span></div>
  <div class="result-prob">AI {pct(game.get('probability'))}</div>
  <div class="result-actual">実績 {game.get('result') or '--'}</div>
  <div class="result-badge {cls}">{badge}</div>
</div>'''
        )
    st.markdown(f'<div class="result-table">{"".join(rows)}</div>', unsafe_allow_html=True)

st.caption("試合前予測は固定値として検証し、引き分け・未終了試合は的中率計算から除外します。")


@st.cache_data(max_entries=2)
def load_historical_report(path: str):
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


historical_path = active_data_dir() / "historical_backtest_report.json"
if not historical_path.exists():
    historical_path = REPO_DATA_DIR / "historical_backtest_report.json"
historical = load_historical_report(str(historical_path))

render_section("HISTORICAL VALIDATION", "過去データ・年度別・モデル別バックテスト")
if not historical:
    st.info("長期バックテスト結果はまだ生成されていません。")
else:
    model_labels = {
        "historical_baseline": "過去勝率ベースライン",
        "logistic_rolling": "ロジスティック回帰",
        "gradient_rolling": "勾配ブースティング",
    }
    overall = historical.get("overall") or []
    recommended = historical.get("recommended_model")
    with st.container(horizontal=True):
        st.metric("元データ", f"{int(historical.get('source_games') or 0):,}試合", border=True)
        st.metric("公式戦評価対象", f"{int(historical.get('evaluated_games') or 0):,}試合", border=True)
        st.metric("検証年度", f"{len(historical.get('evaluated_seasons') or [])}シーズン", border=True)
        st.metric("推奨モデル", model_labels.get(recommended, recommended or "--"), border=True)

    overall_rows = [
        {
            "モデル": model_labels.get(row.get("model"), row.get("model")),
            "検証試合": int(row.get("games") or 0),
            "的中率": float(row.get("accuracy") or 0),
            "Brier Score": float(row.get("brier") or 0),
            "LogLoss": float(row.get("log_loss") or 0),
        }
        for row in overall
    ]
    st.dataframe(
        overall_rows,
        hide_index=True,
        column_config={
            "的中率": st.column_config.NumberColumn(format="%.2f%%"),
            "Brier Score": st.column_config.NumberColumn(format="%.4f"),
            "LogLoss": st.column_config.NumberColumn(format="%.4f"),
        },
        key="historical_overall_models",
    )

    season_rows = [
        {
            "年度": int(row.get("season") or 0),
            "モデル": model_labels.get(row.get("model"), row.get("model")),
            "学習期間": f"〜{int(row.get('train_through') or 0)}",
            "試合数": int(row.get("games") or 0),
            "的中率": float(row.get("accuracy") or 0),
            "Brier Score": float(row.get("brier") or 0),
            "LogLoss": float(row.get("log_loss") or 0),
        }
        for row in historical.get("by_season") or []
    ]
    st.dataframe(
        season_rows,
        hide_index=True,
        column_config={
            "的中率": st.column_config.NumberColumn(format="%.2f%%"),
            "Brier Score": st.column_config.NumberColumn(format="%.4f"),
            "LogLoss": st.column_config.NumberColumn(format="%.4f"),
        },
        key="historical_by_season",
    )
    st.caption(
        f"対象期間: {historical.get('source_start', '--')}〜{historical.get('source_end', '--')}。"
        "各年度は、それ以前の年度だけで学習するウォークフォワード方式です。引き分けと未来情報は除外しています。"
    )

# ============================================================
# 全NPB AI予測成績
# ============================================================

AI_PERFORMANCE_FILE = (
    active_data_dir()
    / "ai_prediction_performance.json"
)

AI_HISTORY_FILE = (
    active_data_dir()
    / "ai_prediction_history.json"
)


def _load_optional_json(path, default):
    try:
        return json.loads(
            path.read_text(encoding="utf-8")
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
    ):
        return default


st.markdown("---")
st.subheader("全NPB AI予測パフォーマンス")

ai_perf = _load_optional_json(
    AI_PERFORMANCE_FILE,
    {},
)

ai_history = _load_optional_json(
    AI_HISTORY_FILE,
    [],
)

if not isinstance(ai_history, list):
    ai_history = []

shared_history = _load_optional_json(SHARED_DATA_DIR / "ai_prediction_history.json", []) if shared_available else []
if not isinstance(shared_history, list):
    shared_history = []
ai_history = merge_prediction_archives(ai_history, shared_history)

backtest_csv = active_data_dir() / "historical_backtest_predictions.csv"
if not backtest_csv.exists():
    backtest_csv = REPO_DATA_DIR / "historical_backtest_predictions.csv"
ai_history, season_backfilled = backfill_season_predictions(
    ai_history,
    backtest_csv,
    season=jst_today.year,
)

current_predictions = _load_optional_json(active_data_dir() / "today_ai_predictions.json", {})
current_schedule = _load_optional_json(active_data_dir() / "npb_today.json", {})
shared_predictions = {}
if shared_available:
    shared_predictions = _load_optional_json(SHARED_DATA_DIR / "today_ai_predictions.json", {})
    shared_schedule = _load_optional_json(SHARED_DATA_DIR / "npb_today.json", {})
    ai_history, _ = archive_predictions(ai_history, shared_predictions, shared_schedule)
    ai_history, _ = settle_predictions(ai_history, shared_schedule)
ai_history, _ = archive_predictions(ai_history, current_predictions, current_schedule)
ai_history, _ = settle_predictions(ai_history, current_schedule)
ai_history, _ = settle_predictions(
    ai_history,
    {"games": load_final_results(active_data_dir(), SHARED_DATA_DIR if shared_available else None)},
)
ai_perf = build_performance(ai_history)
shared_prediction_count = len(shared_history) + len(shared_predictions.get("games") or [])
season_dates = sorted(
    str(row.get("date") or "")[:10]
    for row in ai_history
    if isinstance(row, dict)
    and str(row.get("date") or "").startswith(str(jst_today.year))
)
season_start = season_dates[0] if season_dates else "--"
calibrated_pending = sum(
    int(row.get("validation_sample_size") or 0) > 0
    for row in ai_history
    if isinstance(row, dict) and row.get("status") == "pending"
)

settled_games = int(
    ai_perf.get("settled_games") or 0
)

hits = int(
    ai_perf.get("hits") or 0
)

hit_rate = ai_perf.get("hit_rate")
brier_score = ai_perf.get("brier_score")
score_mae = ai_perf.get("score_mae")

with st.container(horizontal=True):
    st.metric("シーズン開始", season_start, border=True)
    st.metric("固定予測", f"{len(ai_history)}試合", border=True)
    st.metric("8502共有", f"{shared_prediction_count}試合", border=True)
    st.metric("確定試合", f"{settled_games}試合", border=True)
    st.metric("的中", f"{hits}試合", border=True)
    st.metric("的中率", f"{hit_rate:.1f}%" if hit_rate is not None else "-", border=True)
    st.metric("Brier Score", f"{brier_score:.4f}" if brier_score is not None else "-", border=True)

if score_mae is not None:
    st.caption(
        "平均スコア誤差: "
        f"{float(score_mae):.2f}点"
    )

st.info(
    f"{jst_today.year}年の全NPB予測履歴を開幕日から表示しています。"
    f"バックテスト補完 {season_backfilled}試合。"
    "勝敗確率は、対象試合より前に確定した同一確率帯の検証結果だけで補正します。"
    f"現在の未確定予測のうち検証反映済みは {calibrated_pending}試合です。",
    icon=":material/analytics:",
)

confidence = ai_perf.get("confidence") or {}

if confidence:
    st.markdown("#### 信頼度別成績")

    confidence_rows = []

    labels = {
        "HIGH": "HIGH",
        "MEDIUM": "MEDIUM",
        "LOW": "LOW",
    }

    for level in confidence:
        row = confidence.get(level) or {}

        confidence_rows.append(
            {
                "信頼度": labels.get(level, level),
                "試合数": int(
                    row.get("games") or 0
                ),
                "的中": int(
                    row.get("hits") or 0
                ),
                "的中率": (
                    float(row["hit_rate"])
                    if row.get("hit_rate")
                    is not None
                    else None
                ),
            }
        )

    st.dataframe(
        confidence_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "的中率":
                st.column_config.NumberColumn(
                    format="%.1f%%"
                )
        },
    )

pending = [
    row
    for row in ai_history
    if isinstance(row, dict)
    and row.get("status") == "pending"
]

if pending:
    st.markdown("#### 未確定の固定予測")

    pending_rows = []

    for row in sorted(
        pending,
        key=lambda x: (
            str(x.get("date") or ""),
            str(x.get("time") or ""),
        ),
    ):
        pending_rows.append(
            {
                "日付": row.get("date"),
                "開始": row.get("time"),
                "対戦":
                    f'{row.get("away", "-")} @ '
                    f'{row.get("home", "-")}',
                "予想": row.get("pick"),
                "勝率":
                    row.get("win_probability"),
                "補正前":
                    raw_pick_probability(row),
                "検証数":
                    row.get("validation_sample_size"),
                "予想スコア":
                    row.get("predicted_score"),
                "信頼度":
                    row.get("confidence"),
                "モデル":
                    row.get("model"),
            }
        )

    st.dataframe(
        pending_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "勝率":
                st.column_config.NumberColumn(
                    format="%.1f%%"
                ),
            "補正前":
                st.column_config.NumberColumn(
                    format="%.1f%%"
                ),
        },
    )

final_rows = [
    row
    for row in ai_history
    if isinstance(row, dict)
    and row.get("status") == "final"
]

if final_rows:
    st.markdown("#### 全NPB AI予測履歴")

    display_rows = []

    for row in sorted(
        final_rows,
        key=lambda x: (
            str(x.get("date") or ""),
            str(x.get("time") or ""),
        ),
        reverse=True,
    ):
        result_text = (
            "○"
            if row.get("hit") is True
            else "×"
        )

        display_rows.append(
            {
                "日付": row.get("date"),
                "対戦":
                    f'{row.get("away", "-")} @ '
                    f'{row.get("home", "-")}',
                "予想": row.get("pick"),
                "勝率":
                    row.get("win_probability"),
                "補正前":
                    raw_pick_probability(row),
                "予想スコア":
                    row.get("predicted_score"),
                "実スコア":
                    f'{row.get("actual_home_score") if row.get("actual_home_score") is not None else "-"}'
                    f'-'
                    f'{row.get("actual_away_score") if row.get("actual_away_score") is not None else "-"}',
                "結果": result_text,
                "Brier":
                    row.get("brier"),
                "スコア誤差":
                    row.get("score_error"),
            }
        )

    st.dataframe(
        display_rows,
        width="stretch",
        hide_index=True,
        column_config={
            "勝率":
                st.column_config.NumberColumn(
                    format="%.1f%%"
                ),
            "Brier":
                st.column_config.NumberColumn(
                    format="%.4f"
                ),
            "スコア誤差":
                st.column_config.NumberColumn(
                    format="%.2f"
                ),
        },
    )

if (
    not settled_games
    and pending
):
    st.info(
        "試合終了後、的中率・Brier Score・"
        "予想スコア誤差が自動集計されます。"
    )

st.caption(
    f"固定予測 {len(ai_history)}件・未確定 {len(pending)}件。"
    "試合日程データを60秒ごとに確認し、終了スコアが届くと自動で照合します。"
)
