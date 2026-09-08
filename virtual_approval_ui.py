"""Per-record review and explicit approval, never automatic approval."""
import streamlit as st
from bet_store import BetStoreError
from virtual_approval import validate_approval
from virtual_editor import save_virtual_approval
from virtual_replay import load_verified_scores


def render_approval(record, result, path, prefix):
    key = f'{prefix}_approval_{record["id"]}'
    if record.get('virtual_approval'):
        st.caption('手動承認履歴あり：' + record['virtual_approval']['saved_at'])
    if result.get('status') != 'review':
        return
    active = {**record, **record.get('virtual_edit', {})}
    amount = active.get('bet_amount')
    if amount is None:
        amount = abs(float(active.get('bet_units') or 0)) * 10000
    st.write(f"承認対象：{record.get('date')} {active.get('team')} vs {active.get('opponent')}／仮想ポイント {amount:,.0f}")
    st.warning(result.get('reason', '要確認'))
    st.caption('仮想ポイント専用。公式得点が未登録の場合は確認した9回得点を入力してください。未定義ルールはこの1件だけの手動判定として記録します。')
    own = st.number_input('対象チームの9回得点', min_value=0, max_value=999, value=result.get('team_score_9'), step=1, key=key+'_own')
    other = st.number_input('相手チームの9回得点', min_value=0, max_value=999, value=result.get('opponent_score_9'), step=1, key=key+'_other')
    token = st.text_input('承認する元ハンデ（出し＋／もらい−）', value=str(result.get('handicap_raw') or ''), key=key+'_h')
    fraction = st.text_input('判定割合（丸勝ち1／2分勝ち0.2／勝負なし0／丸負け-1）', key=key+'_fraction')
    evidence = st.text_area('確認根拠（得点・元ハンデの出典、判定理由）', max_chars=2000, key=key+'_evidence')
    values = dict(team_score_9=own, opponent_score_9=other, handicap_raw=token, fraction=fraction, evidence=evidence)
    try:
        checked = validate_approval(record, values, load_verified_scores())
    except (ValueError, TypeError) as exc:
        st.info(str(exc))
        ready = False
    else:
        active = {**record, **record.get('virtual_edit', {})}
        st.write(f"確認：{active.get('team')} {own}対{other} {active.get('opponent')}／ハンデ {token}／判定割合 {fraction}")
        st.write(f"承認後の増減：{checked['points_delta']:+,}（勝ち分90%）")
        if checked['manual_rule']:
            st.warning('現在のルール表にない判定です。この1件のみ手動承認します。')
        ready = True
    confirmed = st.checkbox('得点・ハンデ・判定割合・重複の有無を確認しました', key=key+'_confirm')
    if st.button('承認して再計算', key=key+'_save', disabled=not (ready and confirmed), type='primary'):
        try:
            save_virtual_approval(path, record, values, confirmed=confirmed)
        except (BetStoreError, ValueError) as exc:
            st.error(str(exc))
        else:
            st.session_state['virtual_edit_saved'] = record.get('date')
            st.rerun()
