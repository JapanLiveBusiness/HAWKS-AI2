"""Virtual-points performance dashboard. Source records are never overwritten."""
from pathlib import Path
from datetime import date
import json
import os
import streamlit as st

from auth_session import user_bets_path
from bet_store import BetStoreError, load_bets
from studio_theme import apply_studio_theme, render_topbar, render_hero, render_nav_links
from virtual_replay import load_verified_scores, load_verified_handicaps, replay_records
from virtual_dashboard import summarize, month_options, calendar_html, history_rows
from virtual_editor_ui import render_day_editor
from virtual_approval_ui import render_approval
from virtual_calendar_rank import load_calendar_predictions
from virtual_accuracy import render_accuracy

st.set_page_config(page_title="収支マップ | 仮想ポイント", page_icon="📊", layout="wide")
apply_studio_theme()
auth_user = render_topbar("VIRTUAL POINTS / PERFORMANCE")
render_hero("収支マップ", "9回までの公式得点と画像ルールで、仮想ポイントを振り返る。",
            kicker="AI BASEBALL STUDIO / VIRTUAL GAME", accent="POINTS")
render_nav_links()
st.caption("換金・景品交換のない仮想ゲーム専用。カレンダーの日付を押すと内容を編集できます。元履歴と編集履歴は保持します。")
if st.session_state.pop("virtual_edit_saved", None):
    st.success("保存しました。カレンダーと集計を再計算しました。")
st.markdown("""
<style>
.vp-calendar{display:grid;grid-template-columns:repeat(7,minmax(0,1fr));gap:6px;margin:16px 0}
.vp-weekday{text-align:center;font-size:12px;color:#667085}
.vp-cell{min-height:96px;background:#f8fafc;border:1px solid #dce3eb;border-radius:10px;padding:10px;color:#253044}
.vp-cell strong,.vp-cell small{display:block;margin-top:10px;overflow-wrap:anywhere}
.vp-cell strong{font-size:14px}.vp-cell small{font-size:11px;color:#6b5310}
.vp-positive{background:#edf9f3;border-color:#b3dfc7}.vp-positive strong{color:#146c43}
.vp-negative{background:#fff1f0;border-color:#f1c6c2}.vp-negative strong{color:#ad332b}
.vp-empty{border:none;background:transparent}
a.vp-cell{text-decoration:none!important;display:block;color:#253044!important}
a.vp-cell:hover,a.vp-cell:focus-visible{outline:3px solid #c99300;outline-offset:1px}
@media(max-width:600px){.vp-calendar{gap:3px}.vp-cell{padding:5px;min-height:92px;border-radius:6px}
.vp-cell strong{font-size:10px}.vp-cell small{font-size:9px}}
</style>
""", unsafe_allow_html=True)
data_dir = Path("/app/data") if Path("/app/data").exists() else Path(__file__).resolve().parents[1] / "data"
bets_path = user_bets_path(data_dir, auth_user)
try:
    edit_day = date.fromisoformat(st.query_params.get("edit_date", "")).isoformat()
except ValueError:
    edit_day = None
try:
    originals = load_bets(bets_path)
    report = replay_records(originals, load_verified_scores(), handicaps=load_verified_handicaps())
except (BetStoreError, OSError, ValueError) as exc:
    st.error(f"履歴または確認済み得点を読み込めません: {exc}")
    st.stop()

all_rows = report["results"]
calendar_predictions = load_calendar_predictions(data_dir, Path(os.getenv("AI_BASEBALL_SHARED_DATA_DIR", "/app/shared-data")))
with st.expander("適用ルール・データ範囲"):
    st.write("1〜9回の得点のみを使用し、延長を除外します。1.5と1半は別ルールです。")
    st.write("追加確認済み: 同点・0.2もらいは2分勝ち。100,000ポイントなら100,000×0.2×0.9＝18,000ポイント。0.2出しの同点は20,000ポイント減です。")
    st.write("プラス分のポイント付与率は従来の90%を維持。部分勝敗の割合を適用し、1ポイント単位で四捨五入します。")
    st.write("確認済み得点は2026年9月1〜6日。9月7日に再取得した7件のハンデは元履歴と別に適用し、履歴に保存値・適用値・出典を表示します。")
    st.write("0.8・1.1・1.6は指定された比例配分ルールで補足しています。範囲外の得点や未対応のハンデは要確認です。")
    st.write("元記録が未確定なら自動確定しません。中止は得点判定しません。")
    st.caption("旧画面の円表示・最終得点による集計とは別の仮想ポイント表示です。")

if not originals:
    st.info("現在のアカウントには履歴がありません。")
    st.page_link("pages/BET入力.py", label="入力ページを開く")

months = month_options(all_rows)
period = st.selectbox("集計期間", ["全期間", *months])
rows = all_rows if period == "全期間" else [r for r in all_rows if str(r.get("date") or "").startswith(period + "-")]
summary = summarize(rows)
st.metric("確認済み分の増減", f"{summary['points']:+,} pt" if summary["calculated"] else "—")
cols = st.columns(3)
cols[0].metric("計算済み", f"{summary['calculated']} 件")
cols[1].metric("要確認", f"{summary['review']} 件")
cols[2].metric("未確定 / 中止", f"{summary['pending']} / {summary['cancelled']} 件")
if summary["review"] or summary["pending"]:
    st.warning("要確認・未確定の記録はポイント集計から除外しています。表示値は全記録の確定合計ではありません。")
overview, history, review = st.tabs(["推移・日別カレンダー", "全履歴", "要確認一覧"])
with overview:
    render_accuracy(rows, originals, calendar_predictions)
    st.subheader("累積ポイント")
    st.caption("選択期間の開始を0として、計算できた記録だけを日付順に積み上げます。保有残高ではありません。")
    if summary["series"]:
        st.line_chart(summary["series"], x="日付", y="累積ポイント", height=280)
    else:
        st.info("この期間に計算済みの記録はありません。")
    if months:
        default_month = months.index(edit_day[:7]) if edit_day and edit_day[:7] in months else 0
        calendar_month = period if period != "全期間" else st.selectbox("表示月", months, index=default_month)
        st.caption("チーム左の記号：1・2・3…＝その日のAI勝率順位（高い順・同率は同順位）｜M＝手動入力・手動編集｜—＝試合前のAI勝率が未確認で順位なし。チーム右の％＝AI勝率です。")
        st.markdown(calendar_html(rows, calendar_month, calendar_predictions), unsafe_allow_html=True)
        st.caption("＋ / −は当日のポイント増減。—は計算済み記録なし。要確認・未確定・中止は別記です。")
    if edit_day:
        render_day_editor(edit_day, originals, all_rows, bets_path)
with history:
    st.caption("選択期間の全状態を表示します。元記録の点数・金額は上書きしていません。")
    if rows:
        st.dataframe(history_rows(rows), hide_index=True, width="stretch")
    else:
        st.info("表示する履歴はありません。")
with review:
    unresolved = [r for r in rows if r["status"] == "review"]
    if unresolved:
        st.dataframe(history_rows(unresolved), hide_index=True, width="stretch")
        st.info("元のハンデ表記や9回時点の公式得点を確認するまで、推測で判定しません。")
        original_by_id = {r['id']: r for r in originals}
        for result in unresolved:
            with st.expander(f"承認確認：{result['date']} {result['team']} vs {result['opponent']} · {result['id'][-6:]}"):
                render_approval(original_by_id[result['id']], result, bets_path, 'list')
    else:
        st.success("この期間に要確認の記録はありません。")
st.download_button("全期間の元履歴・再計算結果を保存（JSON）",
                   data=json.dumps(report, ensure_ascii=False, indent=2),
                   file_name="virtual-points-history.json", mime="application/json")
