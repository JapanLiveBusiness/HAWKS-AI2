"""Single source of truth for feature readiness and implementation work."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Feature:
    key: str
    label: str
    route: str | None
    status: str
    summary: str
    next_step: str | None = None


FEATURES = (
    Feature("games", "本日の試合", "/試合", "live", "対戦カードとAI予測を表示"),
    Feature("predictions", "AI予測", "/本日のAI予想", "live", "当日の予測と信頼度を表示"),
    Feature("results", "予想結果", "/予想結果", "live", "全NPBの固定予測を終了スコアと自動照合"),
    Feature("bet_entry", "BET入力", "/BET入力", "live", "BETの登録・編集・削除・精算と利用者別保存に対応"),
    Feature("performance", "収支マップ", "/収支マップ", "live", "収支・ROI・Excel入出力を一元管理"),
    Feature("ai_detail", "AI詳細", "/AI詳細", "live", "軽量サマリー、最新共有予想、公式速報自動入力、状況・戦力補正対応の勝率シミュレーターを表示"),
    Feature("team_detail", "球団別詳細", "/球団別詳細", "live", "12球団の戦績・次戦・AI予測・直近成績を表示"),
)

STATUS_LABELS = {"live": "稼働中", "beta": "ベータ", "preview": "試験運用", "planned": "実装予定"}


def feature(key: str) -> Feature:
    return next(item for item in FEATURES if item.key == key)


def implementation_queue() -> tuple[Feature, ...]:
    """Return unfinished features in recommended implementation order."""
    order = {"bet_entry": 0, "performance": 1, "results": 2, "ai_detail": 3, "team_detail": 4}
    return tuple(sorted((item for item in FEATURES if item.next_step), key=lambda item: order.get(item.key, 999)))
