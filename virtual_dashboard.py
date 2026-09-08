"""Read-only aggregation and calendar for non-redeemable virtual points."""
import calendar
from datetime import date
from html import escape
from decimal import Decimal, InvalidOperation

TEAM_SHORT = {"巨人": "巨人", "阪神": "阪神", "DeNA": "横浜", "広島": "広島",
              "ヤクルト": "ヤク", "中日": "中日", "ソフトバンク": "ソフ",
              "日本ハム": "日ハ", "ロッテ": "ﾛｯﾃ", "楽天": "楽天", "オリックス": "オリ", "西武": "西武"}


def bet_amount_label(row):
    """Show stakes, not profit; unknown amounts must not look like zero."""
    try:
        amount = row.get("bet_amount")
        if amount is None:
            amount = abs(Decimal(str(row["bet_units"]))) * 10000
        amount = Decimal(str(amount))
        if not amount.is_finite() or amount <= 0:
            return "金額要確認"
        if amount % 10000 == 0:
            return f"{amount / 10000:,.0f}万"
        return f"{amount:,.0f}" if amount == amount.to_integral_value() else f"{amount:,f}"
    except (InvalidOperation, ValueError, TypeError, KeyError):
        return "金額要確認"


def handicap_side_badge(row):
    """Actual nine-inning result, independent of handicap and point profit."""
    own, other = row.get("team_score_9"), row.get("opponent_score_9")
    if row.get("status") == "cancelled":
        mark, label = "中止", "試合中止"
    elif not all(type(score) is int and score >= 0 for score in (own, other)):
        mark, label = "?", "9回時点の得点未確認"
    else:
        mark = "勝" if own > other else "負" if own < other else "分"
        label = f"9回時点：{own}対{other}（ハンデ適用前）"
    return f'<span class="vp-game-result" title="{label}" aria-label="{label}">{mark}</span>'


def summarize(rows):
    calculated = [r for r in rows if r.get("status") == "calculated" and isinstance(r.get("points_delta"), int)]
    daily = {}
    for row in calculated:
        try:
            day = date.fromisoformat(str(row.get("date"))).isoformat()
        except ValueError:
            continue
        daily[day] = daily.get(day, 0) + row["points_delta"]
    cumulative = 0
    series = []
    for day, delta in sorted(daily.items()):
        cumulative += delta
        series.append({"日付": day, "日別ポイント": delta, "累積ポイント": cumulative})
    return {"points": cumulative, "calculated": len(calculated),
            "review": sum(r.get("status") == "review" for r in rows),
            "pending": sum(r.get("status") == "pending" for r in rows),
            "cancelled": sum(r.get("status") == "cancelled" for r in rows),
            "daily": daily, "series": series}


def month_options(rows):
    months = set()
    for row in rows:
        try:
            months.add(date.fromisoformat(str(row.get("date"))).strftime("%Y-%m"))
        except ValueError:
            pass
    return sorted(months, reverse=True)


def calendar_html(rows, month, predictions=()):
    rows = [r for r in rows if not r.get("virtual_deleted")]
    first = date.fromisoformat(month + "-01")
    summary = summarize(rows)
    states = {}
    bets = {}
    for row in rows:
        states.setdefault(str(row.get("date")), []).append(row.get("status"))
        bets.setdefault(str(row.get("date")), []).append(row)
    cells = []
    for week in calendar.Calendar(firstweekday=0).monthdayscalendar(first.year, first.month):
        for day in week[1:]:
            if day == 0:
                cells.append('<div class="vp-cell vp-empty"></div>')
                continue
            key = f"{month}-{day:02d}"
            delta = summary["daily"].get(key)
            status = states.get(key, [])
            color = "vp-positive" if delta is not None and delta > 0 else "vp-negative" if delta is not None and delta < 0 else ""
            value = f"{delta:+,}" if delta is not None else "—"
            notes = []
            for state, label in [("review", "要確認"), ("pending", "未確定"), ("cancelled", "中止")]:
                if state in status:
                    notes.append(f"{label} {status.count(state)}")
            from virtual_calendar_rank import ranked_bets
            details = ''.join(f'<span class="vp-bet" title="{escape(str(r.get("team") or "チーム未確認"), quote=True)}"><span class="vp-rank">{escape(mark)}</span> <span>{escape(TEAM_SHORT.get(r.get("team"), "不明"))}</span> <span class="vp-stake">{escape(bet_amount_label(r))}</span> {handicap_side_badge(r)}{f" <span>{prob:.0f}%</span>" if prob is not None else ""}</span>' for r, mark, prob in ranked_bets(bets.get(key, []), predictions))
            through_day = [v for d, v in summary["daily"].items() if d <= key]
            cumulative_value = f'{sum(through_day):+,}' if through_day else '—'
            cumulative = f'<span class="vp-cumulative">累積 {cumulative_value}</span>' if status else ''
            cells.append(f'<a class="vp-cell {color}" href="?edit_date={key}#day-editor" target="_self" aria-label="{key} の内容を編集"><span class="vp-day-header"><b>{day}</b><span class="vp-day-totals"><strong>{value}</strong>{cumulative}</span></span><span class="vp-bets">{details}</span><small>{escape(" / ".join(notes))}</small></a>')
    style = '<style>.vp-calendar{grid-template-columns:repeat(6,minmax(0,1fr))!important}.vp-calendar .vp-cell{min-height:150px}.vp-bets{display:block;margin-top:8px}.vp-bet{display:block;color:#253044;font-size:12px;line-height:1.5;overflow-wrap:anywhere;margin-top:6px}.vp-bet>span{display:block}.vp-stake{font-weight:600}@media(max-width:600px){.vp-calendar .vp-cell{min-height:130px}.vp-bet{font-size:10px;line-height:1.4}}</style>'
    style += '<style>.vp-cumulative{display:block;margin-top:8px;padding-top:6px;border-top:1px solid #dce3eb;font-size:12px;color:#475467;overflow-wrap:anywhere}@media(max-width:600px){.vp-cumulative{font-size:10px}}</style>'
    style += '<style>.vp-bet{white-space:nowrap;overflow-x:auto;overflow-wrap:normal}.vp-bet>span{display:inline}</style>'
    style += '<style>.vp-calendar{align-items:start}.vp-calendar .vp-cell{box-sizing:border-box;aspect-ratio:1;min-height:0;padding:7px}.vp-calendar .vp-cell strong{margin-top:3px;font-size:12px}.vp-calendar .vp-cumulative{border-top:0;border-bottom:1px solid #dce3eb;padding:2px 0 4px;margin-top:2px;font-size:10px}.vp-bets{margin-top:3px}.vp-calendar .vp-bet{margin-top:1px;font-size:11px;line-height:1.35}.vp-calendar .vp-cell small:empty{display:none}.vp-rank{font-weight:700;color:#667085}@media(max-width:600px){.vp-calendar .vp-cell{padding:4px}.vp-calendar .vp-bet{font-size:9px}.vp-calendar .vp-cell strong{font-size:10px}.vp-calendar .vp-cumulative{font-size:9px}}</style>'
    style += '<style>.vp-calendar{container-type:inline-size}.vp-calendar .vp-cell{aspect-ratio:auto;min-height:calc((100cqw - 30px)/6);height:auto}.vp-calendar .vp-bet{overflow:visible}@media(max-width:600px){.vp-calendar .vp-cell{min-height:calc((100cqw - 15px)/6)}}</style>'
    style += '<style>.vp-day-header{display:flex;align-items:flex-start;justify-content:flex-start;gap:5px;border-bottom:1px solid #dce3eb;padding-bottom:4px;text-align:left}.vp-day-header>b{flex:none;line-height:1.25}.vp-day-totals{display:block;min-width:0}.vp-calendar .vp-day-header strong{margin:0;font-size:11px;line-height:1.4}.vp-calendar .vp-day-header .vp-cumulative{border:0;margin:0;padding:0;font-size:9px;line-height:1.4}.vp-calendar .vp-day-header+.vp-bets{margin-top:4px}@media(max-width:600px){.vp-day-header{gap:3px}.vp-calendar .vp-day-header strong{font-size:9px}.vp-calendar .vp-day-header .vp-cumulative{font-size:8px}}</style>'
    style += '<style>.vp-calendar .vp-day-header{justify-content:space-between}.vp-calendar .vp-day-totals{margin-left:auto;text-align:right}.vp-calendar .vp-day-totals strong,.vp-calendar .vp-day-totals .vp-cumulative{text-align:right}</style>'
    return style + '<p style="font-size:12px;color:#667085">金額右：勝＝勝ち／負＝負け／分＝引き分け／?＝得点未確認。9回時点の実際の勝敗（延長・ハンデを除く）です。</p><div class="vp-calendar">' + ''.join(f'<div class="vp-weekday">{day}</div>' for day in "火水木金土日") + ''.join(cells) + '</div><p style="font-size:12px;color:#667085">累積収支：選択期間の初日を0とした計算済み収支の合計（非表示の月曜日を含む）。未確定・要確認は含みません。</p>'


def history_rows(rows):
    labels = {"calculated": "計算済み", "review": "要確認", "pending": "未確定", "cancelled": "中止"}
    return [{"日付": r.get("date"), "チーム": r.get("team"), "相手": r.get("opponent"),
             "状態": labels.get(r.get("status"), "要確認"), "適用ハンデ": r.get("handicap_raw"),
             "元履歴ハンデ": r.get("stored_handicap"),
             "再取得適用": "あり" if r.get("handicap_refetched") else "なし",
             "手動編集": "あり" if r.get("virtual_edited") else "なし",
             "手動承認": "あり" if r.get("manual_approved") else "なし",
             "承認日時": r.get("approved_at", ""),
             "9回時点": f"{r['team_score_9']}–{r['opponent_score_9']}" if "team_score_9" in r else None,
             "ポイント増減": r.get("points_delta"), "確認事項": r.get("reason", ""),
             "公式記録": r.get("score_source", ""),
             "ハンデ出典": r.get("handicap_source", "")} for r in sorted(rows, key=lambda r: str(r.get("date") or ""), reverse=True)]
