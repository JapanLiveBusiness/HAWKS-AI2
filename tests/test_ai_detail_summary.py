from ai_detail_summary import (
    build_final_history_record,
    calculate_context_adjustments,
    find_team_prediction,
    hawks_history_summary,
    hawks_probability,
    live_simulation_context,
    simulate_hawks_win_probability,
)


def test_build_final_history_record_maps_home_hawks_result():
    record = build_final_history_record({
        "status": "final",
        "date": "2026-09-05",
        "home": "ソフトバンク",
        "away": "西武",
        "home_score": 5,
        "away_score": 2,
        "venue": "みずほPayPay",
        "home_starter": "A",
        "away_starter": "B",
        "pick": "ソフトバンク",
        "win_probability": 54.5,
    })

    assert record["game_id"] == "2026-09-05_ソフトバンク_西武"
    assert record["result"] == "勝"
    assert record["hawks_score"] == 5
    assert record["opponent_score"] == 2
    assert record["pregame_probability"] == 54.5
    assert record["auto_saved"] is True


def test_build_final_history_record_maps_away_hawks_and_rejects_unfinished():
    record = build_final_history_record({
        "status": "試合終了",
        "date": "2026-09-06",
        "home": "西武",
        "away": "ソフトバンク",
        "home_score": 4,
        "away_score": 3,
        "pick": "西武",
        "win_probability": 60,
    }, live_probability=12.34, source="AI詳細 手動保存")

    assert record["result"] == "敗"
    assert record["hawks_score"] == 3
    assert record["pregame_probability"] == 40.0
    assert record["live_probability"] == 12.3
    assert record["auto_saved"] is False
    assert build_final_history_record({"status": "scheduled"}) is None


def test_find_team_prediction_merges_schedule_and_prediction():
    schedule = {
        "games": [{
            "date": "2026-09-05",
            "home": "ソフトバンク",
            "away": "西武",
            "time": "14:00",
        }]
    }
    predictions = {
        "games": [{
            "home": "ソフトバンク",
            "away": "西武",
            "pick": "ソフトバンク",
            "win_probability": 63.5,
        }]
    }

    game = find_team_prediction(schedule, predictions)

    assert game["opponent"] == "西武"
    assert game["pick"] == "ソフトバンク"
    assert game["win_probability"] == 63.5


def test_hawks_history_summary_orders_recent_results():
    history = [
        {"date": "2026-08-15", "result": "敗"},
        {"date": "2026-08-18", "result": "勝"},
        {"date": "2026-08-20", "result": "分"},
        {"date": "2026-08-16", "result": "勝"},
        {"date": "", "result": "未確定"},
    ]

    summary = hawks_history_summary(history)

    assert summary["played"] == 4
    assert (summary["wins"], summary["losses"], summary["draws"]) == (2, 1, 1)
    assert [row["date"] for row in summary["recent"]] == [
        "2026-08-20",
        "2026-08-18",
        "2026-08-16",
        "2026-08-15",
    ]


def test_hawks_probability_inverts_opponent_pick():
    assert hawks_probability({
        "pick": "ソフトバンク",
        "win_probability": 63.5,
    }) == 63.5
    assert hawks_probability({
        "pick": "西武",
        "win_probability": 58,
    }) == 42.0


def test_pregame_simulator_applies_handicap_value():
    result = simulate_hawks_win_probability(
        60,
        mode="pregame",
        handicap_score=-1.0,
    )

    assert result["score_adjustment"] == -8.0
    assert result["wpa_adjustment"] == 0.0
    assert result["final_probability"] == 52.0


def test_live_simulator_values_late_scoring_opportunity():
    hawks_attack = simulate_hawks_win_probability(
        50,
        hawks_score=3,
        opponent_score=3,
        inning=9,
        attack_side="ホークス攻撃中",
        outs=0,
        runners=(1, 2, 4),
    )
    opponent_attack = simulate_hawks_win_probability(
        50,
        hawks_score=3,
        opponent_score=3,
        inning=9,
        attack_side="相手攻撃中",
        outs=0,
        runners=(1, 2, 4),
    )

    assert hawks_attack["final_probability"] > 50
    assert opponent_attack["final_probability"] < 50


def test_live_simulator_clamps_extreme_scores():
    result = simulate_hawks_win_probability(
        90,
        hawks_score=20,
        opponent_score=0,
        inning=9,
    )

    assert result["score_adjustment"] == 55.0
    assert result["final_probability"] == 99.5


def test_live_context_maps_home_hawks_official_state():
    context = live_simulation_context({
        "status": "live",
        "home": "ソフトバンク",
        "away": "西武",
        "home_score": 4,
        "away_score": 3,
        "inning": 8,
        "inning_half": "裏",
        "outs": 1,
        "bases": {1: True, 2: False, 3: True},
    })

    assert context["available"] is True
    assert context["hawks_score"] == 4
    assert context["opponent_score"] == 3
    assert context["attack_side"] == "ホークス攻撃中"
    assert context["runners"] == (1, 4)


def test_live_context_maps_away_hawks_and_rejects_incomplete_data():
    context = live_simulation_context({
        "status": "試合中",
        "home": "西武",
        "away": "ソフトバンク",
        "home_score": 5,
        "away_score": 2,
        "inning": 6,
        "inning_half": "表",
        "outs": 0,
    })

    assert context["available"] is True
    assert context["hawks_score"] == 2
    assert context["opponent_score"] == 5
    assert context["attack_side"] == "ホークス攻撃中"
    assert live_simulation_context({"status": "scheduled"}) == {"available": False}
    assert live_simulation_context({
        "status": "live",
        "home": "ソフトバンク",
        "away": "西武",
        "home_score": 1,
        "away_score": 0,
    }) == {"available": False}


def test_context_adjustments_match_v8_rules():
    context = calculate_context_adjustments(
        inning=9,
        venue="ホーム",
        hawks_era=2.0,
        opponent_era=4.0,
        recent_wins=5,
        compatibility="得意",
        weather="追い風",
        reliever_8th=True,
        reliever_9th=True,
        reliever_fatigue=False,
        keyman_available=True,
        bench_boost=True,
    )

    assert context == {
        "venue": 3.0,
        "pitcher": 4.0,
        "momentum": 5.0,
        "compatibility": 3.0,
        "weather": 1.5,
        "reliever": 5.5,
        "keyman": 4.0,
        "total": 26.0,
    }


def test_simulator_limits_context_adjustment():
    result = simulate_hawks_win_probability(
        50,
        context_adjustment=40,
    )

    assert result["context_adjustment"] == 25.0
    assert result["final_probability"] == 75.0
