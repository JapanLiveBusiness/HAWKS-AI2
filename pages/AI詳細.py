from datetime import date, datetime
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from ai_detail_summary import (
    build_final_history_record,
    calculate_context_adjustments,
    find_team_prediction,
    hawks_history_summary,
    hawks_probability,
    live_simulation_context,
    simulate_hawks_win_probability,
)
from daily_data import load_current_daily_json
from handicap_source import fetch_hawks_handicap
from npb_live import fetch_npb_live_game
from prediction_metrics import build_prediction_metrics
from storage.game_history import load_game_history, save_game_history
from studio_theme import (
    apply_studio_theme,
    render_hero,
    render_nav_links,
    render_section,
    render_topbar,
)

JST = ZoneInfo("Asia/Tokyo")
TODAY_JST = datetime.now(JST).date()
REPO_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
PROD_DATA_DIR = Path("/app/data")
DATA_DIR = PROD_DATA_DIR if PROD_DATA_DIR.exists() else REPO_DATA_DIR
SHARED_DATA_DIR = Path(
    os.getenv("AI_BASEBALL_SHARED_DATA_DIR", "/app/shared-data")
)

st.set_page_config(
    page_title="AI詳細 | MY AI BASEBALL",
    page_icon="⚾",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_studio_theme()
render_topbar("AI DETAIL")
render_hero(
    "AI詳細ダッシュボード",
    "試合情報・AI予測・公開ハンデ・検証成績を軽量な1画面に集約しました。",
    kicker="AI BASEBALL STUDIO / DEEP ANALYTICS",
    accent="AI詳細",
)
render_nav_links()


@st.cache_data(ttl=60, max_entries=12, show_spinner=False)
def load_json(path_text, fallback):
    try:
        return json.loads(Path(path_text).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return fallback


@st.cache_data(ttl=600, max_entries=4, show_spinner=False)
def load_live_handicap(date_value):
    return fetch_hawks_handicap(date_value, timeout=4)


@st.cache_data(ttl=15, max_entries=12, show_spinner=False)
def load_official_live_game(date_value, home, away):
    return fetch_npb_live_game(date_value, home, away)


schedule = load_current_daily_json("npb_today.json", {"games": []})
predictions = load_current_daily_json(
    "today_ai_predictions.json", {"games": []}
)
game = find_team_prediction(schedule, predictions)

# The daily file can lag behind during an upstream outage. Prefer today's game
# from the same persisted calendar cache used by the games page.
calendar_games = []
for calendar_path in (
    Path(__file__).resolve().parents[1] / "npb_schedule_fallback.json",
    PROD_DATA_DIR / "npb_schedule_cache.json",
):
    calendar_payload = load_json(str(calendar_path), {"games": []})
    calendar_games.extend(
        row
        for row in calendar_payload.get("games") or []
        if str(row.get("date") or "") == TODAY_JST.isoformat()
    )
today_game = find_team_prediction({"games": calendar_games}, predictions)
if today_game is not None:
    game = today_game


@st.fragment(run_every="30s")
def sync_official_live_game(current_game):
    if not current_game or str(current_game.get("date") or "") != TODAY_JST.isoformat():
        return
    home = str(current_game.get("home") or "")
    away = str(current_game.get("away") or "")
    if not home or not away:
        return
    lookup_key = f"{TODAY_JST.isoformat()}|{home}|{away}"
    update = load_official_live_game(TODAY_JST, home, away)
    if not update:
        return
    live_cache = st.session_state.setdefault("ai_detail_official_live", {})
    previous = live_cache.get(lookup_key)
    live_cache[lookup_key] = update
    if previous is not None and previous != update:
        st.rerun()


sync_official_live_game(game)
if game:
    game_lookup_key = (
        f"{game.get('date')}|{game.get('home')}|{game.get('away')}"
    )
    stored_live = st.session_state.get("ai_detail_official_live", {}).get(game_lookup_key, {})
    if stored_live:
        game.update(stored_live)
        game["opponent"] = game.get("away") if game.get("home") == "ソフトバンク" else game.get("home")

history_path = DATA_DIR / "game_history.json"
history = load_game_history(history_path)
official_history_record = build_final_history_record(game)
if official_history_record:
    existing_record = next(
        (
            row for row in history
            if row.get("game_id") == official_history_record["game_id"]
        ),
        None,
    )
    needs_save = existing_record is None or any(
        existing_record.get(key) != value
        for key, value in official_history_record.items()
    )
    if needs_save:
        save_game_history(history_path, official_history_record)
        history = load_game_history(history_path)
history_summary = hawks_history_summary(
    history
)
metrics = build_prediction_metrics(
    DATA_DIR,
    SHARED_DATA_DIR if SHARED_DATA_DIR.exists() else None,
)
try:
    handicap_date = date.fromisoformat(str(game.get("date") or ""))
except (AttributeError, ValueError):
    handicap_date = TODAY_JST
handicap = load_live_handicap(handicap_date)
game_opponent = str(game.get("opponent") or "") if game else ""
handicap_matches_game = bool(
    handicap.get("published")
    and (
        not game_opponent
        or str(handicap.get("opponent") or "") == game_opponent
    )
)

game_date = str(game.get("date") or "") if game else ""
if game_date == TODAY_JST.isoformat():
    game_section_title = "本日のホークス試合分析"
elif game_date > TODAY_JST.isoformat():
    game_section_title = "次戦のホークス試合分析"
else:
    game_section_title = "直近保存されたホークス試合分析"
render_section("LATEST GAME DATA", game_section_title)
if game:
    opponent = str(game.get("opponent") or "未定")
    matchup = f"ソフトバンク vs {opponent}"
    schedule_label = (
        f"{game.get('date') or schedule.get('date') or '--'} "
        f"{game.get('time') or '--:--'}｜{game.get('venue') or '会場未定'}"
    )
    st.subheader(matchup)
    st.caption(schedule_label)
else:
    st.info("ホークスの次戦情報を同期中です。履歴と検証成績は確認できます。")

cards = st.container(horizontal=True)
pick = str(game.get("pick") or "生成待ち") if game else "生成待ち"
probability = game.get("win_probability") if game else None
probability_label = (
    f"{float(probability):.1f}%"
    if isinstance(probability, (int, float))
    else "--"
)
cards.metric("AI PICK", pick, probability_label, border=True)
cards.metric(
    "予想スコア",
    str(game.get("predicted_score") or "--") if game else "--",
    border=True,
)
cards.metric(
    "信頼度",
    str(game.get("confidence") or "--") if game else "--",
    border=True,
)
handicap_label = "対象カードなし" if handicap.get("published") else "未掲載"
if handicap_matches_game:
    handicap_label = (
        f"{handicap.get('favored_team') or ''} {handicap.get('token') or ''}"
    ).strip()
cards.metric("公開ハンデ", handicap_label, border=True)

render_section("MODEL PERFORMANCE", "HAWKS AI検証成績")
performance = st.container(horizontal=True)
performance.metric("検証済み", f"{metrics['verified_count']}試合", border=True)
performance.metric("的中", f"{metrics['hits']}試合", border=True)
performance.metric(
    "的中率",
    f"{metrics['hit_rate']:.1f}%" if metrics["hit_rate"] is not None else "--",
    border=True,
)
performance.metric(
    "Brier Score",
    f"{metrics['brier_score']:.4f}"
    if metrics["brier_score"] is not None
    else "--",
    border=True,
)
st.caption(
    "Brier Scoreは予測確率の誤差です。0に近いほど確率予測が正確です。"
)

render_section("RECENT RESULTS", "ホークス直近5試合")
recent_rows = []
for row in history_summary["recent"]:
    recent_rows.append(
        {
            "日付": row.get("date") or "--",
            "対戦相手": row.get("opponent") or "--",
            "球場": row.get("stadium") or "--",
            "スコア": (
                f"{row.get('hawks_score', '-')} - "
                f"{row.get('opponent_score', '-')}"
            ),
            "結果": row.get("result") or "--",
            "試合前AI勝率": row.get("pregame_probability"),
        }
    )
if recent_rows:
    st.dataframe(
        pd.DataFrame(recent_rows),
        hide_index=True,
        column_config={
            "試合前AI勝率": st.column_config.NumberColumn(format="%.1f%%"),
        },
    )
    st.caption(
        f"保存済み {history_summary['played']}試合｜"
        f"{history_summary['wins']}勝 {history_summary['losses']}敗 "
        f"{history_summary['draws']}分"
    )
else:
    st.info("試合履歴を同期中です。")

render_section("LIVE SIMULATOR", "リアルタイム勝率シミュレーター")
st.caption(
    "V8の点差・イニング・アウト・走者補正を独立化した軽量版です。"
    "入力内容は保存されず、BET結果にも影響しません。"
)
simulator_mode = st.segmented_control(
    "分析モード",
    options=["試合前", "試合中"],
    default="試合中",
    key="ai_detail_simulator_mode",
)
base_probability = hawks_probability(game)
manual_scores = None
if simulator_mode == "試合前":
    published_handicap = (
        float(handicap.get("handicap_score") or 0.0)
        if handicap_matches_game
        else 0.0
    )
    simulator_handicap = st.number_input(
        "開始ハンデ（＋はホークス優位、－は相手優位）",
        min_value=-5.0,
        max_value=5.0,
        value=published_handicap,
        step=0.1,
        key="ai_detail_simulator_handicap",
    )
    simulation_options = {
        "mode": "pregame",
        "handicap_score": simulator_handicap,
    }
    simulator_inning = 1
else:
    official_context = live_simulation_context(game)
    use_official_live = st.toggle(
        "NPB公式速報を自動反映",
        value=official_context["available"],
        disabled=not official_context["available"],
        key="ai_detail_use_official_live",
        help="公式速報を30秒ごとに確認し、点差・イニング・アウト・走者を自動入力します。",
    )
    if use_official_live and official_context["available"]:
        runner_labels = [
            label
            for bit, label in ((1, "1塁"), (2, "2塁"), (4, "3塁"))
            if bit in official_context["runners"]
        ]
        st.success(
            "NPB公式速報を反映中｜"
            f"{official_context['hawks_score']} - {official_context['opponent_score']}｜"
            f"{official_context['inning']}回｜{official_context['attack_side']}｜"
            f"{official_context['outs']}アウト｜"
            f"走者 {'・'.join(runner_labels) if runner_labels else 'なし'}"
        )
        simulator_inning = official_context["inning"]
        simulation_options = {
            key: official_context[key]
            for key in (
                "mode",
                "hawks_score",
                "opponent_score",
                "inning",
                "attack_side",
                "outs",
                "runners",
            )
        }
    else:
        if not official_context["available"]:
            st.caption("公式速報は試合開始後に利用できます。現在は手動入力モードです。")
        score_left, score_right, inning_col = st.columns(3)
        hawks_score = score_left.number_input(
            "ホークス得点",
            min_value=0,
            max_value=30,
            value=0,
            step=1,
            key="ai_detail_hawks_score",
        )
        opponent_score = score_right.number_input(
            "相手得点",
            min_value=0,
            max_value=30,
            value=0,
            step=1,
            key="ai_detail_opponent_score",
        )
        manual_scores = (int(hawks_score), int(opponent_score))
        inning = inning_col.slider(
            "現在のイニング",
            min_value=1,
            max_value=9,
            value=1,
            key="ai_detail_inning",
        )
        attack_side = st.segmented_control(
            "現在の攻撃",
            options=["ホークス攻撃中", "相手攻撃中"],
            default="ホークス攻撃中",
            key="ai_detail_attack_side",
        )
        outs = st.segmented_control(
            "アウトカウント",
            options=[0, 1, 2],
            default=0,
            key="ai_detail_outs",
        )
        selected_runners = st.pills(
            "走者状況",
            options=["1塁", "2塁", "3塁"],
            selection_mode="multi",
            key="ai_detail_runners",
        )
        runner_bits = tuple(
            {"1塁": 1, "2塁": 2, "3塁": 4}[runner]
            for runner in (selected_runners or [])
        )
        simulator_inning = inning
        simulation_options = {
            "mode": "live",
            "hawks_score": hawks_score,
            "opponent_score": opponent_score,
            "inning": inning,
            "attack_side": attack_side,
            "outs": outs,
            "runners": runner_bits,
        }

context = {"total": 0.0}
use_context = st.toggle(
    "詳細状況補正を使用",
    value=False,
    key="ai_detail_use_context",
    help="球場・先発・勢い・相性・天候・終盤戦力を追加で評価します。",
)
if use_context:
    venue_default = (
        "ホーム" if game and game.get("home") == "ソフトバンク"
        else "ビジター" if game
        else "中立"
    )
    venue_setting = st.segmented_control(
        "球場条件",
        options=["ホーム", "ビジター", "中立"],
        default=venue_default,
        key="ai_detail_context_venue",
    )
    pitcher_left, pitcher_right, momentum_col = st.columns(3)
    hawks_era = pitcher_left.number_input(
        "ホークス先発 防御率",
        min_value=0.0,
        max_value=15.0,
        value=3.50,
        step=0.01,
        key="ai_detail_context_hawks_era",
    )
    opponent_era = pitcher_right.number_input(
        "相手先発 防御率",
        min_value=0.0,
        max_value=15.0,
        value=3.50,
        step=0.01,
        key="ai_detail_context_opponent_era",
    )
    recent_wins_default = sum(
        row.get("result") == "勝" for row in history_summary["recent"]
    )
    recent_wins = momentum_col.slider(
        "直近5試合の勝利数",
        min_value=0,
        max_value=5,
        value=recent_wins_default,
        key="ai_detail_context_recent_wins",
    )
    context_left, context_right = st.columns(2)
    compatibility = context_left.selectbox(
        "相手投手との相性",
        options=["非常に得意", "得意", "普通", "苦手", "天敵"],
        index=2,
        key="ai_detail_context_compatibility",
    )
    weather = context_right.selectbox(
        "球場環境",
        options=["通常", "追い風", "向かい風", "ルーフオープン"],
        key="ai_detail_context_weather",
    )
    bullpen = st.container(horizontal=True)
    reliever_8th = bullpen.checkbox(
        "8回勝ちパターン利用可",
        value=True,
        key="ai_detail_context_reliever_8th",
    )
    reliever_9th = bullpen.checkbox(
        "9回抑え利用可",
        value=True,
        key="ai_detail_context_reliever_9th",
    )
    reliever_fatigue = bullpen.checkbox(
        "救援陣に疲労あり",
        value=False,
        key="ai_detail_context_reliever_fatigue",
    )
    personnel = st.container(horizontal=True)
    keyman_available = personnel.checkbox(
        "主力選手が出場",
        value=True,
        key="ai_detail_context_keyman",
    )
    bench_boost = personnel.checkbox(
        "代打戦力が充実",
        value=False,
        key="ai_detail_context_bench",
    )
    context = calculate_context_adjustments(
        inning=simulator_inning,
        venue=venue_setting,
        hawks_era=hawks_era,
        opponent_era=opponent_era,
        recent_wins=recent_wins,
        compatibility=compatibility,
        weather=weather,
        reliever_8th=reliever_8th,
        reliever_9th=reliever_9th,
        reliever_fatigue=reliever_fatigue,
        keyman_available=keyman_available,
        bench_boost=bench_boost,
    )

simulation = simulate_hawks_win_probability(
    base_probability,
    context_adjustment=context["total"],
    **simulation_options,
)

sim_result, sim_score, sim_wpa, sim_context = st.columns(4)
sim_result.metric(
    "ホークス勝利予測",
    f"{simulation['final_probability']:.1f}%",
    f"基礎勝率 {simulation['base_probability']:.1f}%",
)
sim_score.metric(
    "点差・ハンデ補正",
    f"{simulation['score_adjustment']:+.1f}%",
)
sim_wpa.metric(
    "走者・アウト補正",
    f"{simulation['wpa_adjustment']:+.1f}%",
)
sim_context.metric(
    "詳細状況補正",
    f"{simulation['context_adjustment']:+.1f}%",
)
st.progress(simulation["final_probability"] / 100.0)
if use_context:
    st.caption(
        "詳細内訳: "
        f"球場 {context['venue']:+.1f}%｜"
        f"先発 {context['pitcher']:+.1f}%｜"
        f"勢い {context['momentum']:+.1f}%｜"
        f"相性 {context['compatibility']:+.1f}%｜"
        f"環境 {context['weather']:+.1f}%｜"
        f"救援 {context['reliever']:+.1f}%｜"
        f"主力 {context['keyman']:+.1f}%"
    )

render_section("RESULT STORAGE", "試合結果の保存")
if official_history_record:
    st.success(
        "NPB公式速報の確定結果を試合履歴へ保存済み｜"
        f"ソフトバンク {official_history_record['hawks_score']} - "
        f"{official_history_record['opponent_score']} {official_history_record['opponent']}"
    )
elif simulator_mode == "試合中" and game and manual_scores is not None:
    st.caption(
        "試合終了後は公式速報から自動保存します。速報を取得できない場合のみ、"
        "入力スコアを確認して手動保存してください。"
    )
    manual_confirmed = st.checkbox(
        "試合終了と入力スコアを確認しました",
        value=False,
        key="ai_detail_manual_result_confirmed",
    )
    if st.button(
        "入力スコアを試合履歴へ保存",
        icon=":material/save:",
        disabled=not manual_confirmed,
        key="ai_detail_manual_result_save",
    ):
        manual_game = dict(game)
        manual_game["status"] = "final"
        if manual_game.get("home") == "ソフトバンク":
            manual_game["home_score"], manual_game["away_score"] = manual_scores
        else:
            manual_game["away_score"], manual_game["home_score"] = manual_scores
        manual_record = build_final_history_record(
            manual_game,
            live_probability=simulation["final_probability"],
            source="AI詳細 手動保存",
        )
        if manual_record:
            save_game_history(history_path, manual_record)
            st.success("試合結果を保存しました。")
            st.rerun()
else:
    st.caption("試合情報の同期後、結果保存を利用できます。")

render_section("LEGACY ANALYSIS", "従来版の高度分析")
st.caption(
    "移行確認用として従来の全機能も残しています。"
    "通常は上の軽量シミュレーターをご利用ください。"
)
show_legacy = st.toggle(
    "従来版の高度分析を開く",
    value=False,
    key="show_legacy_ai_detail",
)

if show_legacy:
    st.warning(
        "高度分析を読み込んでいます。外部データ取得により数秒かかる場合があります。"
    )
    app_path = Path(__file__).resolve().parents[1] / "app.py"
    app_source = app_path.read_text(encoding="utf-8")
    fixed_assignment = "handicap_score = -2.0"
    if fixed_assignment not in app_source:
        st.error("高度分析の読み込み設定を確認できません。")
        st.stop()
    live_handicap_score = (
        float(handicap["handicap_score"])
        if handicap_matches_game
        and handicap.get("handicap_score") is not None
        else 0.0
    )
    app_source = app_source.replace(
        fixed_assignment,
        "handicap_score = live_handicap_score",
        1,
    )
    original_set_page_config = st.set_page_config
    original_file = globals().get("__file__")
    st.set_page_config = lambda *args, **kwargs: None
    globals()["__file__"] = str(app_path)
    try:
        try:
            exec(compile(app_source, str(app_path), "exec"), globals(), globals())
        except Exception as exc:
            st.error(
                "高度分析の一部を読み込めませんでした。"
                "上部のAI分析サマリーは引き続き利用できます。"
            )
            with st.expander("エラー情報"):
                st.code(f"{type(exc).__name__}: {exc}")
    finally:
        st.set_page_config = original_set_page_config
        globals()["__file__"] = original_file
