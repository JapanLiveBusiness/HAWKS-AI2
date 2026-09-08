"""Read-only, paired nine-inning accuracy; never backfill pregame predictions."""
from collections import defaultdict
from virtual_calendar_rank import probability


def is_manual(record):
    # Settlement approval and amount/handicap-only edits are not team selection.
    edit = record.get('virtual_edit') or {}
    return (record.get('source') in {'manual', 'manual-page'}
            or str(record.get('id') or '').startswith('manual-')
            or any(k in edit and edit[k] != record.get(k) for k in ('team', 'opponent')))


def compare_accuracy(rows, originals, predictions):
    original_by_id = {r.get('id'): r for r in originals}
    grouped = defaultdict(list)
    unknown = 0
    for row in rows:
        original = original_by_id.get(row.get('id'), {})
        if original.get('virtual_deleted') or row.get('virtual_deleted'):
            continue
        if not is_manual(original):
            unknown += 1
            continue
        if not row.get('team') or not row.get('opponent') or row['team'] == row['opponent']:
            unknown += 1
            continue
        key = (row.get('date'), *sorted((row['team'], row['opponent'])))
        grouped[key].append(row)
    details = []
    wins = losses = draws = excluded = ai_missing = 0
    manual_hits = ai_hits = paired = 0
    for key, entries in sorted(grouped.items()):
        # Repeated bets do not amplify accuracy. Opposite picks/conflicting scores
        # cannot represent one manual prediction and are excluded explicitly.
        signatures = {(r['team'], r.get('team_score_9'), r.get('opponent_score_9')) for r in entries}
        row = entries[0]
        own, other = row.get('team_score_9'), row.get('opponent_score_9')
        if (len(signatures) != 1 or any(r.get('status') != 'calculated' for r in entries)
                or not all(type(v) is int and v >= 0 for v in (own, other))):
            excluded += 1
            continue
        if own == other:
            draws += 1
            continue
        win = own > other
        wins += int(win)
        losses += int(not win)
        prob = probability(row, predictions)
        ai_pick = None if prob is None or prob == 50 else row['team'] if prob > 50 else row['opponent']
        ai_win = None
        if ai_pick is None:
            ai_missing += 1
        else:
            paired += 1
            manual_hits += int(win)
            ai_win = win if ai_pick == row['team'] else not win
            ai_hits += int(ai_win)
        details.append({'日付': key[0], '手動選定': row['team'], '対戦相手': row['opponent'],
                        '9回得点': f'{own}–{other}', '手動結果': '的中' if win else '不的中',
                        'AI仮想選定': ai_pick or '比較対象外',
                        'AI結果': '—' if ai_win is None else '的中' if ai_win else '不的中'})
    return dict(wins=wins, losses=losses, draws=draws, excluded=excluded,
                unknown=unknown, ai_missing=ai_missing, paired=paired,
                manual_hits=manual_hits, ai_hits=ai_hits,
                manual_rate=100 * wins / (wins + losses) if wins + losses else None,
                paired_manual_rate=100 * manual_hits / paired if paired else None,
                ai_rate=100 * ai_hits / paired if paired else None,
                difference=100 * (ai_hits - manual_hits) / paired if paired else None,
                details=details)


def render_accuracy(rows, originals, predictions):
    import streamlit as st
    result = compare_accuracy(rows, originals, predictions)
    st.subheader('手動選定とAIの的中率比較')
    st.caption('選択した集計期間が対象。AIは同じ対戦で試合前の勝率が高い側を選ぶ仮想比較です。実際のAI自動BET実績や日別上位3チームの検証ではありません。')
    cols = st.columns(3)
    for col, label, key in zip(cols, ['手動的中率（比較対象）', 'AI的中率（同じ試合）', '的中率差（AI − 手動）'],
                               ['paired_manual_rate', 'ai_rate', 'difference']):
        value = result[key]
        col.metric(label, '—' if value is None else f'{value:+.1f}ポイント' if key == 'difference' else f'{value:.1f}%')
    st.caption(f"比較対象 {result['paired']}試合｜手動的中 {result['manual_hits']}件｜AI的中 {result['ai_hits']}件")
    rate = '—' if result['manual_rate'] is None else f"{result['manual_rate']:.1f}%"
    st.write(f"手動選定全体：{rate}（{result['wins']}勝・{result['losses']}敗）")
    st.caption(f"除外：引き分け {result['draws']}試合／未確定・要確認・選定競合 {result['excluded']}試合／AI記録なし・同率 {result['ai_missing']}試合。手動選定と確認できない記録 {result['unknown']}件。")
    st.caption('的中率＝9回時点の勝ち÷勝敗確定試合数。延長・ハンデ・BET額は判定に使いません。同じ対戦への重複BETは1試合として集計。手動承認や金額だけの編集では選定者を変更しません。')
    if not result['paired']:
        st.info('比較可能な試合前AI記録がないため、AI的中率と差は未算出です。結果を見た後の予想で補完しません。')
    if result['details']:
        with st.expander('的中率の比較明細'):
            st.dataframe(result['details'], hide_index=True, width='stretch')
