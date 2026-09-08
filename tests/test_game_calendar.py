from datetime import date, datetime, timezone

from game_calendar import pending_status_label


def test_pending_label_respects_scheduled_start_in_japan():
    game = {"date": "2026-09-06", "time": "13:00"}
    assert pending_status_label(game, datetime(2026, 9, 6, 2, tzinfo=timezone.utc)) == "開始前"
    assert pending_status_label(game, datetime(2026, 9, 6, 4, tzinfo=timezone.utc)) == "結果確認中"
    assert pending_status_label({"date": "2026-09-05", "time": "--:--"}) == "結果確認中"

from game_calendar import (
    attach_handicaps,
    attach_hawks_history_results,
    load_npb_schedule_day,
    merge_game_sources,
    parse_handicap_html,
    parse_npb_schedule_html,
)


def test_load_schedule_day_prefers_persisted_current_data(tmp_path, monkeypatch):
    cache_path = tmp_path / "npb_today.json"
    cache_path.write_text(
        """
        {
          "date": "2026-09-05",
          "games": [
            {"date": "2026-09-04", "home": "広島", "away": "巨人"},
            {"date": "2026-09-05", "home": "ソフトバンク", "away": "西武", "time": "14:00"}
          ]
        }
        """,
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "game_calendar.fetch_npb_schedule_day",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("network should not be used")),
    )

    games = load_npb_schedule_day(date(2026, 9, 5), (cache_path,))

    assert games == [{
        "date": "2026-09-05",
        "home": "ソフトバンク",
        "away": "西武",
        "time": "14:00",
    }]


def test_load_schedule_day_uses_official_fetch_when_cache_has_no_target(tmp_path, monkeypatch):
    cache_path = tmp_path / "npb_today.json"
    cache_path.write_text('{"games": []}', encoding="utf-8")
    expected = [{"date": "2026-09-06", "home": "楽天", "away": "日本ハム"}]
    monkeypatch.setattr(
        "game_calendar.fetch_npb_schedule_day",
        lambda target_date, timeout: expected if target_date == date(2026, 9, 6) and timeout == 4 else [],
    )

    games = load_npb_schedule_day(date(2026, 9, 6), (cache_path,), timeout=4)

    assert games == expected


def test_parse_official_schedule_keeps_rowspan_date_and_schedule_details():
    markup = """
    <table>
      <tr><td rowspan="2">9/5（土）</td><td>ソフトバンク - 西武</td><td>みずほPayPay 14:00</td></tr>
      <tr><td>オリックス - ロッテ</td><td>京セラD大阪 14:00</td></tr>
      <tr><td>9/6（日）</td><td>楽天 5 - 2 日本ハム</td><td>楽天モバイル 13:00</td></tr>
    </table>
    """
    games = parse_npb_schedule_html(markup, 2026, 9)

    assert [(game["date"], game["home"], game["away"]) for game in games] == [
        ("2026-09-05", "ソフトバンク", "西武"),
        ("2026-09-05", "オリックス", "ロッテ"),
        ("2026-09-06", "楽天", "日本ハム"),
    ]
    assert games[0]["time"] == "14:00"
    assert games[0]["venue"] == "みずほPayPay"
    assert games[2]["status"] == "final"
    assert (games[2]["home_score"], games[2]["away_score"]) == (5, 2)


def test_parse_official_schedule_marks_inning_score_as_live():
    markup = """
    <table>
      <tr><td>9/5（土）</td><td>ソフトバンク 1 - 0 西武</td><td>みずほPayPay 2回</td></tr>
    </table>
    """

    game = parse_npb_schedule_html(markup, 2026, 9)[0]

    assert game["status"] == "live"
    assert (game["home_score"], game["away_score"]) == (1, 0)


def test_parse_official_schedule_merges_compact_live_score_link():
    markup = """
    <table>
      <tr><td>9/5（土）</td><td>ソフトバンク - 西武</td><td>みずほPayPay 14:00</td></tr>
    </table>
    <a href="/scores/2026/0905/h-l-22/">1-0 （みずほPayPay） 1回裏</a>
    """

    game = parse_npb_schedule_html(markup, 2026, 9)[0]

    assert game["status"] == "live"
    assert game["result_source"] == "NPB公式速報"
    assert (game["home_score"], game["away_score"]) == (1, 0)


def test_parse_official_schedule_merges_compact_final_score_link():
    markup = """
    <table>
      <tr><td>9/5（土）</td><td>オリックス - ロッテ</td><td>京セラD大阪 14:00</td></tr>
    </table>
    <a href="/scores/2026/0905/b-m-22/">7-6 （京セラD大阪） 試合終了</a>
    """

    game = parse_npb_schedule_html(markup, 2026, 9)[0]

    assert game["status"] == "final"
    assert game["result_source"] == "NPB公式速報"
    assert (game["home_score"], game["away_score"]) == (7, 6)


def test_parse_and_attach_daily_handicaps():
    markup = """
    <div class="game-detail2">
      <span class="detail-card-team">ヤクルト</span><span class="detail-card-team">阪神</span>
      <div>4-7</div>
      <div class="detail-single-studium-time"><span>18:00</span><span>神宮野球場</span></div>
      <table class="single-handi"><tr><td class="single-handi-handi"></td><td class="single-handi-handi">1.1</td></tr></table>
    </div>
    """
    handicaps = parse_handicap_html(markup, date(2026, 9, 3))
    games = [{
        "home": "ヤクルト",
        "away": "阪神",
        "home_score": 4,
        "away_score": 7,
        "status": "scheduled",
        "result_source": "NPB公式",
    }]
    result = attach_handicaps(games, handicaps)

    assert result[0]["home_handicap"] is None
    assert result[0]["away_handicap"] == "1.1"
    assert result[0]["status"] == "scheduled"
    assert result[0]["result_source"] == "NPB公式"
    assert handicaps[0]["status"] == "final"


def test_merge_sources_enriches_history_without_losing_official_time():
    official = [{"home": "中日", "away": "広島", "time": "18:00", "venue": "バンテリンドーム"}]
    history = [{"home": "中日", "away": "広島", "home_score": 2, "away_score": 5, "status": "final"}]

    result = merge_game_sources(official, history)

    assert result == [{
        "home": "中日",
        "away": "広島",
        "time": "18:00",
        "venue": "バンテリンドーム",
        "home_score": 2,
        "away_score": 5,
        "status": "final",
    }]


def test_merge_sources_does_not_downgrade_official_final_result():
    official = [{
        "home": "ヤクルト",
        "away": "中日",
        "home_score": 4,
        "away_score": 2,
        "status": "final",
        "result_source": "NPB公式",
    }]
    handicap_source = [{
        "home": "ヤクルト",
        "away": "中日",
        "status": "result_pending",
        "result_source": "ハンデの森",
        "away_handicap": "0.6",
    }]

    result = merge_game_sources(official, handicap_source)

    assert result[0]["status"] == "final"
    assert result[0]["home_score"] == 4
    assert result[0]["away_score"] == 2
    assert result[0]["result_source"] == "NPB公式"
    assert result[0]["away_handicap"] == "0.6"


def test_merge_sources_does_not_downgrade_live_game_with_daily_schedule():
    live = [{
        "home": "ソフトバンク",
        "away": "西武",
        "home_score": 1,
        "away_score": 0,
        "status": "live",
        "result_source": "NPB公式速報",
    }]
    daily_schedule = [{
        "home": "ソフトバンク",
        "away": "西武",
        "status": "scheduled",
        "result_source": "本番共有データ",
    }]

    result = merge_game_sources(live, daily_schedule)

    assert result[0]["status"] == "live"
    assert result[0]["home_score"] == 1
    assert result[0]["away_score"] == 0


def test_saved_hawks_final_overrides_regressed_schedule_status():
    games = [{
        "date": "2026-09-05",
        "time": "14:00",
        "home": "ソフトバンク",
        "away": "西武",
        "status": "scheduled",
        "home_score": None,
        "away_score": None,
    }]
    history = [{
        "date": "2026-09-05",
        "opponent": "西武",
        "hawks_score": 2,
        "opponent_score": 0,
        "source": "NPB公式速報",
    }]

    result = attach_hawks_history_results(games, history)

    assert result[0]["status"] == "final"
    assert (result[0]["home_score"], result[0]["away_score"]) == (2, 0)
    assert result[0]["result_source"] == "NPB公式速報"
    assert result[0]["result_source"] == "NPB公式速報"
