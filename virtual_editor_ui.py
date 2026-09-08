"""Per-day virtual record editor; only saves on explicit form submission."""
import streamlit as st
from bet_store import BetStoreError
from virtual_editor import TEAMS, save_virtual_edit, set_virtual_deleted
from virtual_approval_ui import render_approval


def render_day_editor(day, originals, results, bets_path):
    st.markdown('<div id="day-editor"></div>', unsafe_allow_html=True)
    st.subheader(f"{day} の内容を編集")
    st.caption("仮想ポイント・対象チーム・ハンデ・状態・メモを編集できます。元記録は残し、仮想集計だけに適用します。9回得点は公式記録を使用します。")
    daily = [r for r in originals if r.get("date") == day]
    if not daily:
        st.info("この日の登録済み履歴はありません。")
        st.page_link("pages/BET入力.py", label="入力ページで新しく登録")
        return
    calculated = {r["id"]: r for r in results}
    for record in daily:
        active = {**record, **record.get("virtual_edit", {})}
        if record.get("virtual_deleted"):
            with st.expander(f"削除済み：{active.get('team')} vs {active.get('opponent')} · {record['id'][-6:]}"):
                st.caption("カレンダー・仮想集計から削除済み。元記録は保持されています。")
                if st.button("この記録を復元", key=f"restore_{record['id']}"):
                    try:
                        set_virtual_deleted(bets_path, record, False)
                    except (BetStoreError, ValueError) as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["virtual_edit_saved"] = day
                        st.rerun()
            continue
        result = calculated.get(record["id"], {})
        with st.expander(f"{active.get('team')} vs {active.get('opponent')} · {record['id'][-6:]}", expanded=len(daily) <= 2):
            render_approval(record, result, bets_path, 'day')
            with st.form(f"virtual_edit_{record['id']}"):
                c1, c2 = st.columns(2)
                team = c1.selectbox("対象チーム", TEAMS, index=TEAMS.index(active["team"]) if active.get("team") in TEAMS else 0)
                opponent = c2.selectbox("対戦相手", TEAMS, index=TEAMS.index(active["opponent"]) if active.get("opponent") in TEAMS else 1)
                amount = active.get("bet_amount")
                if amount is None:
                    amount = abs(float(active.get("bet_units") or 0)) * 10000
                points = st.number_input("仮想ポイント（20万なら200000）", min_value=1, max_value=10**12, value=max(1, min(10**12, int(amount))), step=10000)
                token = result.get("handicap_raw") or active.get("handicap_raw") or str(active.get("handicap", ""))
                handicap = st.text_input("ハンデ（出しは正、もらいは負）", value=token)
                st.caption("例：0.8出し＝0.8、1.1もらい＝-1.1。1.5と1半は別ルールです。保存すると入力値を再取得値より優先します。")
                status = st.selectbox("状態", ["pending", "final"], index=1 if active.get("status") == "final" else 0, format_func=lambda x: "確定" if x == "final" else "未確定")
                memo = st.text_area("メモ", value=str(active.get("memo") or ""), max_chars=2000)
                submitted = st.form_submit_button("保存して再計算", type="primary")
            if submitted:
                try:
                    save_virtual_edit(bets_path, record, dict(team=team, opponent=opponent,
                        bet_amount=points, handicap_raw=handicap, status=status, memo=memo))
                except (BetStoreError, ValueError) as exc:
                    st.error(str(exc))
                else:
                    st.session_state["virtual_edit_saved"] = day
                    st.rerun()
            with st.form(f"virtual_delete_{record['id']}"):
                st.caption(f"{day} {active.get('team')} vs {active.get('opponent')} を仮想集計から削除します。元記録は残り、復元できます。")
                confirmed = st.checkbox("この1件を削除することを確認しました")
                remove = st.form_submit_button("この1件を削除して再計算")
            if remove:
                if not confirmed:
                    st.warning("削除対象を確認してチェックしてください。")
                else:
                    try:
                        set_virtual_deleted(bets_path, record, True)
                    except (BetStoreError, ValueError) as exc:
                        st.error(str(exc))
                    else:
                        st.session_state["virtual_edit_saved"] = day
                        st.rerun()
