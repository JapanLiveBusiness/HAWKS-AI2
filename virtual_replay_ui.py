"""A separate non-cash replay view; does not write to the original ledger."""
import json

import streamlit as st

from bet_store import BetStoreError, load_bets
from virtual_replay import load_verified_scores, load_verified_handicaps, replay_records


def render_virtual_replay(bets_file):
    with st.expander("仮想ポイント：全履歴を9回まで・画像ルールで再計算", expanded=False):
        st.info("換金・景品交換のない仮想ゲーム専用です。元の履歴・既存の集計は上書きしません。")
        st.caption("対象は過去の全記録です。確認済みの公式得点は2026年9月1〜6日分。"
                   "それ以外の日付や、元表記を区別できないハンデは要確認として扱います。"
                   "1.5と1半は別ルールです。未確定の記録は自動確定しません。")
        st.caption("プラス分は従来の付与率90%を維持し、部分勝敗の割合を適用します。"
                   "マイナス分はその割合を減算します。1ポイント単位で四捨五入します。")
        try:
            records = load_bets(bets_file)
            report = replay_records(records, load_verified_scores(), handicaps=load_verified_handicaps())
        except (BetStoreError, OSError, ValueError) as exc:
            st.error(f"仮想再計算を読み込めません: {exc}")
            return
        if not records:
            st.caption("現在のアカウントに再計算対象の履歴はありません。")
            return
        results = report["results"]
        calculated = [r for r in results if r["status"] == "calculated"]
        review = [r for r in results if r["status"] == "review"]
        c1, c2, c3 = st.columns(3)
        c1.metric("計算できた記録", len(calculated))
        c2.metric("要確認", len(review))
        c3.metric("計算済み分のポイント増減", f"{sum(r['points_delta'] for r in calculated):+,} pt")
        if review:
            st.warning("要確認の記録を含むため、この合計は全履歴の確定値ではありません。")
        labels = {"calculated": "計算済み", "review": "要確認", "cancelled": "中止", "pending": "未確定"}
        st.dataframe([{
            "日付": r["date"], "チーム": r["team"], "相手": r["opponent"],
            "状態": labels[r["status"]], "適用ハンデ": r.get("handicap_raw"),
            "元履歴ハンデ": r.get("stored_handicap"), "ハンデ出典": r.get("handicap_source", ""),
            "9回時点": (f"{r['team_score_9']}–{r['opponent_score_9']}" if "team_score_9" in r else None),
            "ポイント増減": r["points_delta"], "確認事項": r.get("reason", ""),
            "公式得点の出典": r.get("score_source", ""),
        } for r in results], hide_index=True, width="stretch")
        st.download_button("元記録と仮想再計算結果をJSONで保存", data=json.dumps(report, ensure_ascii=False, indent=2),
                           file_name="virtual-nine-innings-replay.json", mime="application/json",
                           key="virtual_replay_export")
