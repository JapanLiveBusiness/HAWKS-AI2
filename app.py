from pathlib import Path
import os
import textwrap
import streamlit as st
import streamlit.components.v1 as components
import urllib.request
from urllib.parse import urljoin
from bs4 import BeautifulSoup
import plotly.graph_objects as go
import re
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


# ページ設定
st.set_page_config(page_title="ホークス応援 AI勝率シミュレーター", page_icon="⚾", layout="wide")

# ===== HAWKS AI 試合履歴 永続保存 =====
from storage.game_history import (
    load_game_history as _load_game_history,
    save_game_history as _save_game_history,
)

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data")).expanduser().resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)
HISTORY_PATH = DATA_DIR / "game_history.json"


def load_game_history():
    return _load_game_history(HISTORY_PATH)


def save_game_history(game):
    _save_game_history(HISTORY_PATH, game)


components.html("""
<script>
try {
    const doc = window.parent.document;

    doc.documentElement.setAttribute("lang", "ja");
    doc.documentElement.setAttribute("translate", "no");
    doc.documentElement.classList.add("notranslate");

    if (!doc.querySelector('meta[name="google"][content="notranslate"]')) {
        const meta = doc.createElement("meta");
        meta.name = "google";
        meta.content = "notranslate";
        doc.head.appendChild(meta);
    }

    if (!doc.querySelector('meta[http-equiv="Content-Language"]')) {
        const lang = doc.createElement("meta");
        lang.httpEquiv = "Content-Language";
        lang.content = "ja";
        doc.head.appendChild(lang);
    }
} catch(e) {}
</script>
""", height=0)
st.markdown("""
    <meta name="google" content="notranslate">
    <style>

        /* ==========================================
           HAWKS AI COMPACT DASHBOARD
           ========================================== */

        .main {
            background:
                linear-gradient(
                    180deg,
                    #f6f8fb 0%,
                    #eef2f7 100%
                );
        }

        .block-container {
            max-width: 1480px !important;
            padding-top: 2.4rem !important;
            padding-bottom: 1rem !important;
        }

        /* ---------- 見出し ---------- */

        h1 {
            font-size: 1.65rem !important;
            font-weight: 800 !important;
            color: #14213d !important;
            margin-top: 0 !important;
            margin-bottom: 0.35rem !important;
            line-height: 1.15 !important;
        }

        h2 {
            font-size: 1.12rem !important;
            font-weight: 750 !important;
            margin-top: 0.55rem !important;
            margin-bottom: 0.20rem !important;
            line-height: 1.2 !important;
        }

        h3 {
            font-size: 1.02rem !important;
            font-weight: 750 !important;
            margin-top: 0.40rem !important;
            margin-bottom: 0.12rem !important;
            line-height: 1.2 !important;
            color: #16213e !important;
        }

        h4 {
            font-size: 0.95rem !important;
            margin-top: 0.30rem !important;
            margin-bottom: 0.12rem !important;
        }

        /* ---------- 全体の縦余白圧縮 ---------- */

        div[data-testid="stVerticalBlock"] {
            gap: 0.32rem !important;
        }

        div[data-testid="stHorizontalBlock"] {
            gap: 0.55rem !important;
        }

        .element-container {
            margin-bottom: 0.10rem !important;
        }

        hr {
            margin-top: 0.35rem !important;
            margin-bottom: 0.35rem !important;
            border-color: rgba(30, 50, 80, 0.12) !important;
        }

        p {
            margin-top: 0.10rem !important;
            margin-bottom: 0.18rem !important;
            line-height: 1.35 !important;
        }

        /* ---------- KPI / metric カード ---------- */

        div[data-testid="stMetric"] {
            background: rgba(255,255,255,0.94);
            border: 1px solid rgba(35,55,85,0.10);
            border-radius: 12px;
            padding: 0.48rem 0.70rem !important;
            min-height: 72px;
            box-shadow:
                0 2px 8px rgba(20,35,60,0.05);
        }

        div[data-testid="stMetricLabel"] {
            font-size: 0.76rem !important;
            font-weight: 700 !important;
            color: #627086 !important;
        }

        div[data-testid="stMetricValue"] {
            font-size: 1.25rem !important;
            font-weight: 800 !important;
            line-height: 1.1 !important;
            color: #17243a !important;
        }

        /* ---------- セクション別アクセント ---------- */

        div[data-testid="stAlert"] {
            border-radius: 10px !important;
            padding: 0.45rem 0.70rem !important;
            margin-top: 0.18rem !important;
            margin-bottom: 0.18rem !important;
        }

        div[data-baseweb="notification"] {
            padding: 0.42rem 0.70rem !important;
        }

        /* Success */
        div[data-testid="stAlert"]:has([data-testid="stMarkdownContainer"] p:first-child) {
            box-shadow: none;
        }

        /* ---------- 入力 ---------- */

        div[data-testid="stNumberInput"] input,
        div[data-testid="stTextInput"] input {
            min-height: 34px !important;
            height: 34px !important;
            font-size: 0.92rem !important;
            border-radius: 8px !important;
        }

        div[data-testid="stSelectbox"] > div,
        div[data-testid="stRadio"] {
            font-size: 0.90rem !important;
        }

        div[data-testid="stSlider"] {
            padding-top: 0 !important;
            padding-bottom: 0 !important;
        }

        /* ---------- ボタン ---------- */

        .stButton > button {
            border-radius: 9px !important;
            font-weight: 750 !important;
            font-size: 0.92rem !important;
            min-height: 36px !important;
            padding: 0.35rem 0.85rem !important;
            box-shadow: 0 2px 6px rgba(20,35,60,0.08);
        }

        /* ---------- Expander ---------- */

        div[data-testid="stExpander"] {
            border-radius: 10px !important;
            border: 1px solid rgba(40,55,80,0.10) !important;
            background: rgba(255,255,255,0.78) !important;
        }

        div[data-testid="stExpander"] details summary {
            padding-top: 0.40rem !important;
            padding-bottom: 0.40rem !important;
            font-weight: 700 !important;
        }

        /* ---------- AI系 ---------- */

        div[data-testid="stProgress"] {
            margin-top: 0.15rem !important;
            margin-bottom: 0.15rem !important;
        }

        /* ---------- Caption ---------- */

        div[data-testid="stCaptionContainer"] {
            font-size: 0.78rem !important;
            color: #718096 !important;
        }

        /* ---------- 色分けヘルパー ---------- */

        .hawks-blue {
            background: linear-gradient(
                135deg,
                #eaf3ff,
                #f5f9ff
            );
            border-left: 4px solid #2f80ed;
            border-radius: 10px;
            padding: 0.45rem 0.70rem;
        }

        .hawks-green {
            background: linear-gradient(
                135deg,
                #eafbf1,
                #f6fffa
            );
            border-left: 4px solid #27ae60;
            border-radius: 10px;
            padding: 0.45rem 0.70rem;
        }

        .hawks-yellow {
            background: linear-gradient(
                135deg,
                #fff8df,
                #fffdf4
            );
            border-left: 4px solid #f2c94c;
            border-radius: 10px;
            padding: 0.45rem 0.70rem;
        }

        .hawks-red {
            background: linear-gradient(
                135deg,
                #fff0f0,
                #fff8f8
            );
            border-left: 4px solid #eb5757;
            border-radius: 10px;
            padding: 0.45rem 0.70rem;
        }

        .hawks-purple {
            background: linear-gradient(
                135deg,
                #f4efff,
                #fbf9ff
            );
            border-left: 4px solid #8e5de7;
            border-radius: 10px;
            padding: 0.45rem 0.70rem;
        }

        /* ---------- PC ---------- */

        @media (min-width: 900px) {
            div[data-testid="stMetric"] {
                min-height: 68px;
            }
        }

        /* ---------- スマホ ---------- */

        @media (max-width: 700px) {

            .block-container {
                padding-left: 0.55rem !important;
                padding-right: 0.55rem !important;
            }

            h1 {
                font-size: 1.38rem !important;
            }

            h2, h3 {
                font-size: 1rem !important;
            }

            div[data-testid="stMetric"] {
                padding: 0.40rem 0.52rem !important;
                min-height: 64px;
            }

            div[data-testid="stMetricValue"] {
                font-size: 1.05rem !important;
            }

            div[data-testid="stVerticalBlock"] {
                gap: 0.24rem !important;
            }
        }

    </style>

<style>

.handicap-status,
.handicap-start {
    min-height: 38px;
    display: flex;
    align-items: center;
    box-sizing: border-box;
    border-radius: 9px;
    padding: 7px 11px;
    margin-top: 4px;
    font-weight: 800;
    font-size: 14px;
}

.handicap-minus {
    color: #a92828;
    background: linear-gradient(90deg,#ffe7e7,#fff6f6);
    border-left: 4px solid #eb5757;
}

.handicap-plus {
    color: #146c43;
    background: linear-gradient(90deg,#e5f8ed,#f6fdf9);
    border-left: 4px solid #27ae60;
}

.handicap-even {
    color: #315b8a;
    background: linear-gradient(90deg,#e7f1ff,#f5f9ff);
    border-left: 4px solid #2f80ed;
}

.handicap-start {
    color: #1557a0;
    background: linear-gradient(90deg,#e6f1ff,#f6faff);
    border-left: 4px solid #2f80ed;
    font-weight: 700;
}

@media (max-width: 700px) {
    .handicap-status,
    .handicap-start {
        margin-top: 4px;
        min-height: 34px;
        font-size: 13px;
        padding: 6px 9px;
    }
}

</style>


<style>

/* ==========================================
   HAWKS AI SECTION DESIGN
   ========================================== */

.section-head {
    width: 100%;
    box-sizing: border-box;
    padding: 7px 12px;
    margin: 5px 0 4px 0;

    border-radius: 9px;

    font-size: 15px;
    font-weight: 800;
    line-height: 1.2;

    letter-spacing: 0.01em;

    box-shadow:
        0 2px 6px rgba(20,35,60,.05);
}

/* 試合情報 */
.section-blue {
    color: #1557a0;
    background:
        linear-gradient(
            90deg,
            #e6f1ff 0%,
            #f5f9ff 100%
        );
    border-left: 4px solid #2f80ed;
}

/* AI */
.section-purple {
    color: #6436a3;
    background:
        linear-gradient(
            90deg,
            #f0e8ff 0%,
            #faf7ff 100%
        );
    border-left: 4px solid #8e5de7;
}

/* 勝率・ホークス有利 */
.section-green {
    color: #187548;
    background:
        linear-gradient(
            90deg,
            #e5f8ed 0%,
            #f6fdf9 100%
        );
    border-left: 4px solid #27ae60;
}

/* LIVE・重要 */
.section-red {
    color: #a83232;
    background:
        linear-gradient(
            90deg,
            #ffe8e8 0%,
            #fff7f7 100%
        );
    border-left: 4px solid #eb5757;
}

/* ハンディ・注意 */
.section-yellow {
    color: #896a12;
    background:
        linear-gradient(
            90deg,
            #fff4cf 0%,
            #fffdf4 100%
        );
    border-left: 4px solid #f2c94c;
}

/* 履歴 */
.section-gray {
    color: #45546a;
    background:
        linear-gradient(
            90deg,
            #e9edf2 0%,
            #f8f9fb 100%
        );
    border-left: 4px solid #718096;
}

.section-subhead {
    margin: 5px 0 3px 0;
    padding: 5px 9px;

    border-radius: 7px;

    font-size: 13px;
    font-weight: 750;

    color: #4b5563;
    background: rgba(235,239,245,.8);
}

/* ==========================================
   さらに縦方向を圧縮
   ========================================== */

div[data-testid="stMetric"] {
    min-height: 62px !important;
    padding-top: 7px !important;
    padding-bottom: 7px !important;
}

div[data-testid="stMetricLabel"] {
    margin-bottom: 0 !important;
}

div[data-testid="stMetricValue"] {
    line-height: 1.05 !important;
}

div[data-testid="stVerticalBlock"] {
    gap: 0.25rem !important;
}

div[data-testid="stHorizontalBlock"] {
    gap: 0.45rem !important;
}

/* number input */
div[data-testid="stNumberInput"] {
    margin-bottom: 0 !important;
}

/* radio */
div[data-testid="stRadio"] {
    margin-top: -2px !important;
    margin-bottom: -2px !important;
}

/* checkbox */
div[data-testid="stCheckbox"] {
    margin-top: -2px !important;
    margin-bottom: -2px !important;
}

/* caption */
div[data-testid="stCaptionContainer"] {
    margin-top: -2px !important;
    margin-bottom: 1px !important;
}

/* expander */
div[data-testid="stExpander"] {
    margin-top: 3px !important;
    margin-bottom: 3px !important;
}

/* ==========================================
   スマホ
   ========================================== */

@media (max-width: 700px) {

    .section-head {
        font-size: 14px;
        padding: 6px 9px;
        margin: 4px 0 3px 0;
    }

    div[data-testid="stMetric"] {
        min-height: 58px !important;
        padding: 6px 8px !important;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1rem !important;
    }
}

</style>

<style>
/* =========================================================
   HAWKS AI FINAL LAYOUT CLEAN
   ========================================================= */

html, body {
    background: #f5f7fb !important;
}

.block-container {
    max-width: 1380px !important;
    padding-top: 2.2rem !important;
    padding-left: 1.4rem !important;
    padding-right: 1.4rem !important;
    padding-bottom: 1.2rem !important;
}

/* ---------- タイトル ---------- */
h1 {
    font-size: 1.72rem !important;
    line-height: 1.15 !important;
    margin: 0 0 0.75rem 0 !important;
    padding: 0 !important;
}

/* ---------- 全体の行間 ---------- */
div[data-testid="stVerticalBlock"] {
    gap: 0.38rem !important;
}

div[data-testid="stHorizontalBlock"] {
    gap: 0.65rem !important;
    align-items: stretch !important;
}

.element-container {
    margin: 0 !important;
}

hr {
    margin: 0.55rem 0 !important;
}

/* ---------- セクションタイトル ---------- */
.section-head {
    display: flex !important;
    align-items: center !important;
    width: 100% !important;
    min-height: 34px !important;
    box-sizing: border-box !important;

    margin: 0.65rem 0 0.25rem 0 !important;
    padding: 7px 12px !important;

    border-radius: 9px !important;

    font-size: 0.95rem !important;
    font-weight: 800 !important;
    line-height: 1 !important;
}

/* ---------- Metricカード ---------- */
div[data-testid="stMetric"] {
    height: 100% !important;
    min-height: 82px !important;

    padding: 0.62rem 0.8rem !important;

    background: #ffffff !important;
    border: 1px solid #e1e6ee !important;
    border-radius: 11px !important;

    box-shadow: 0 2px 7px rgba(20, 35, 60, 0.05) !important;
}

div[data-testid="stMetricLabel"] {
    font-size: 0.78rem !important;
    margin-bottom: 0.18rem !important;
}

div[data-testid="stMetricValue"] {
    font-size: 1.28rem !important;
    line-height: 1.08 !important;
}

/* ---------- Number input ---------- */
div[data-testid="stNumberInput"] {
    width: 100% !important;
}

div[data-testid="stNumberInput"] label {
    margin-bottom: 0.2rem !important;
}

div[data-testid="stNumberInput"] input {
    min-height: 38px !important;
    height: 38px !important;
}

/* ---------- ハンディ ---------- */
.handicap-status,
.handicap-start {
    width: 100% !important;
    min-height: 38px !important;

    display: flex !important;
    align-items: center !important;

    box-sizing: border-box !important;

    margin: 0.18rem 0 !important;
    padding: 7px 12px !important;

    border-radius: 8px !important;

    font-size: 0.9rem !important;
    line-height: 1.1 !important;
}

/* ---------- Alert ---------- */
div[data-testid="stAlert"] {
    margin: 0.18rem 0 !important;
    padding: 0.5rem 0.75rem !important;
    border-radius: 9px !important;
}

/* ---------- Caption ---------- */
div[data-testid="stCaptionContainer"] {
    margin: 0.05rem 0 !important;
    font-size: 0.76rem !important;
    line-height: 1.25 !important;
}

/* ---------- Expander ---------- */
div[data-testid="stExpander"] {
    margin: 0.25rem 0 !important;
    border-radius: 9px !important;
}

/* ---------- 試合情報の列 ---------- */
div[data-testid="column"] {
    min-width: 0 !important;
}

/* ---------- ボタン ---------- */
.stButton > button {
    min-height: 36px !important;
    padding: 0.35rem 0.8rem !important;
    font-size: 0.9rem !important;
}

/* ---------- スマホ ---------- */
@media (max-width: 700px) {
    .block-container {
        padding-top: 1.8rem !important;
        padding-left: 0.65rem !important;
        padding-right: 0.65rem !important;
    }

    h1 {
        font-size: 1.35rem !important;
        margin-bottom: 0.55rem !important;
    }

    .section-head {
        min-height: 32px !important;
        padding: 6px 9px !important;
        font-size: 0.88rem !important;
    }

    div[data-testid="stMetric"] {
        min-height: 70px !important;
        padding: 0.5rem 0.6rem !important;
    }

    div[data-testid="stMetricValue"] {
        font-size: 1.05rem !important;
    }

    .handicap-status,
    .handicap-start {
        min-height: 34px !important;
        padding: 6px 9px !important;
        font-size: 0.82rem !important;
    }
}
</style>

<style>
/* =====================================================
   HAWKS AI FINAL OVERLAP / ALIGNMENT FIX
   文字重なり・行間・カード位置の最終補正
   ===================================================== */

/* 全体：詰めすぎを少し戻す */
div[data-testid="stVerticalBlock"] {
    gap: 0.52rem !important;
}

div[data-testid="stHorizontalBlock"] {
    gap: 0.75rem !important;
    align-items: stretch !important;
}

/* Markdown本文 */
div[data-testid="stMarkdownContainer"] {
    line-height: 1.35 !important;
}

div[data-testid="stMarkdownContainer"] p {
    margin-top: 0.12rem !important;
    margin-bottom: 0.28rem !important;
    line-height: 1.35 !important;
}

/* Caption
   以前のマイナスマージンを完全に解除 */
div[data-testid="stCaptionContainer"] {
    margin-top: 0.18rem !important;
    margin-bottom: 0.30rem !important;
    padding-top: 0 !important;
    padding-bottom: 0 !important;
    min-height: 18px !important;
    line-height: 1.35 !important;
}

div[data-testid="stCaptionContainer"] p {
    line-height: 1.35 !important;
    margin: 0 !important;
}

/* checkbox / radio の負マージン解除 */
div[data-testid="stCheckbox"],
div[data-testid="stRadio"] {
    margin-top: 0.08rem !important;
    margin-bottom: 0.18rem !important;
}

/* ハンディ判定 */
.handicap-status {
    margin-top: 0.30rem !important;
    margin-bottom: 0.22rem !important;
    min-height: 40px !important;
    padding: 8px 12px !important;
}

/* 開始ハンディ */
.handicap-start {
    margin-top: 0 !important;
    margin-bottom: 0.28rem !important;
    min-height: 40px !important;
    padding: 8px 12px !important;
}

/* ハンディ直後の説明文に空間を確保 */
.handicap-start + div,
.handicap-status + div {
    margin-top: 0.12rem !important;
}

/* セクションヘッダー */
.section-head {
    margin-top: 0.72rem !important;
    margin-bottom: 0.32rem !important;
    min-height: 34px !important;
    padding: 7px 12px !important;

    display: flex !important;
    align-items: center !important;

    line-height: 1.15 !important;
}

/* Metricカード */
div[data-testid="stMetric"] {
    min-height: 78px !important;
    padding: 0.62rem 0.78rem !important;
    overflow: visible !important;
}

div[data-testid="stMetricLabel"] {
    line-height: 1.25 !important;
    margin-bottom: 0.25rem !important;
}

div[data-testid="stMetricValue"] {
    line-height: 1.15 !important;
}

/* 青い投手カード等 */
div[data-testid="stAlert"] {
    margin-top: 0.22rem !important;
    margin-bottom: 0.28rem !important;
    padding: 0.52rem 0.78rem !important;
    line-height: 1.35 !important;
}

div[data-testid="stAlert"] p {
    margin: 0.08rem 0 !important;
    line-height: 1.35 !important;
}

/* Number input */
div[data-testid="stNumberInput"] {
    margin-bottom: 0.22rem !important;
}

div[data-testid="stNumberInput"] label {
    line-height: 1.25 !important;
    margin-bottom: 0.22rem !important;
}

/* divider の上下を均等化 */
hr {
    margin-top: 0.55rem !important;
    margin-bottom: 0.55rem !important;
}

/* 特に下部の細かい説明文同士を重ねない */
small,
[data-testid="stCaptionContainer"],
[data-testid="stMarkdownContainer"] {
    overflow: visible !important;
}

/* Expander */
div[data-testid="stExpander"] {
    margin-top: 0.35rem !important;
    margin-bottom: 0.35rem !important;
}

/* スマホ */
@media (max-width: 700px) {

    div[data-testid="stVerticalBlock"] {
        gap: 0.45rem !important;
    }

    .section-head {
        margin-top: 0.55rem !important;
        margin-bottom: 0.28rem !important;
    }

    .handicap-status,
    .handicap-start {
        min-height: 38px !important;
        padding: 7px 9px !important;
    }

    div[data-testid="stCaptionContainer"] {
        margin-top: 0.15rem !important;
        margin-bottom: 0.28rem !important;
    }

    div[data-testid="stMetric"] {
        min-height: 70px !important;
    }
}
</style>

<style>
/* =====================================================
   HAWKS AI SPACING BALANCE FINAL
   各カード・ボタン・入力欄の余白バランス調整
   ===================================================== */

.block-container {
    max-width: 1380px !important;
    padding-top: 2.2rem !important;
    padding-left: 1.6rem !important;
    padding-right: 1.6rem !important;
    padding-bottom: 1.6rem !important;
}

/* 全体の縦間隔 */
div[data-testid="stVerticalBlock"] {
    gap: 0.72rem !important;
}

/* 横並びカード間隔 */
div[data-testid="stHorizontalBlock"] {
    gap: 0.95rem !important;
    align-items: stretch !important;
}

/* セクションタイトル */
.section-head {
    margin-top: 0.9rem !important;
    margin-bottom: 0.45rem !important;
    min-height: 38px !important;
    padding: 8px 14px !important;
}

/* KPIカード */
div[data-testid="stMetric"] {
    min-height: 86px !important;
    padding: 0.75rem 0.9rem !important;
    border-radius: 12px !important;
}

div[data-testid="stMetricLabel"] {
    margin-bottom: 0.3rem !important;
}

div[data-testid="stMetricValue"] {
    line-height: 1.15 !important;
}

/* NumberInput */
div[data-testid="stNumberInput"] {
    margin-top: 0.2rem !important;
    margin-bottom: 0.45rem !important;
}

div[data-testid="stNumberInput"] input {
    min-height: 42px !important;
    height: 42px !important;
}

/* ハンディカード */
.handicap-status,
.handicap-start {
    min-height: 44px !important;
    margin: 0.28rem 0 !important;
    padding: 9px 14px !important;
}

/* Alert */
div[data-testid="stAlert"] {
    margin-top: 0.35rem !important;
    margin-bottom: 0.4rem !important;
    padding: 0.65rem 0.9rem !important;
}

/* Caption */
div[data-testid="stCaptionContainer"] {
    margin-top: 0.18rem !important;
    margin-bottom: 0.4rem !important;
    line-height: 1.4 !important;
}

/* ボタン */
.stButton > button {
    min-height: 42px !important;
    padding: 0.45rem 1rem !important;
    border-radius: 10px !important;
}

/* Expander */
div[data-testid="stExpander"] {
    margin-top: 0.4rem !important;
    margin-bottom: 0.45rem !important;
}

/* Divider */
hr {
    margin-top: 0.8rem !important;
    margin-bottom: 0.8rem !important;
}

/* スマホ */
@media (max-width: 700px) {

    .block-container {
        padding-left: 0.8rem !important;
        padding-right: 0.8rem !important;
    }

    div[data-testid="stVerticalBlock"] {
        gap: 0.55rem !important;
    }

    div[data-testid="stHorizontalBlock"] {
        gap: 0.55rem !important;
    }

    .section-head {
        min-height: 34px !important;
        padding: 7px 10px !important;
    }

    div[data-testid="stMetric"] {
        min-height: 74px !important;
        padding: 0.6rem 0.7rem !important;
    }

    .handicap-status,
    .handicap-start {
        min-height: 40px !important;
        padding: 8px 10px !important;
    }
}
</style>

<style>

/* ========================================================
   HAWKS AI V8 PREMIUM LIVE DESIGN
   ======================================================== */

.hawks-live-strip{
    width:100%;
    box-sizing:border-box;
    display:flex;
    justify-content:space-between;
    align-items:center;
    gap:12px;

    margin:8px 0 14px 0;
    padding:11px 15px;

    border:1px solid rgba(65,133,255,.25);
    border-radius:12px;

    background:
        linear-gradient(
            135deg,
            rgba(9,25,51,.98),
            rgba(7,15,29,.98)
        );

    box-shadow:
        0 8px 28px rgba(0,0,0,.22),
        inset 0 1px 0 rgba(255,255,255,.04);
}

.hawks-live-left,
.hawks-live-right{
    display:flex;
    align-items:center;
    gap:8px;
}

.hawks-live-title{
    font-size:.88rem;
    font-weight:800;
    color:#eaf2ff;
    letter-spacing:.02em;
}

.hawks-live-dot,
.hawks-red-dot{
    display:inline-block;
    width:8px;
    height:8px;
    border-radius:999px;
    background:#ff3b45;
    box-shadow:0 0 10px rgba(255,59,69,.8);
}

.hawks-live-badge{
    display:inline-flex;
    align-items:center;
    justify-content:center;
    min-height:25px;
    padding:3px 10px;
    border-radius:999px;
    font-size:.70rem;
    font-weight:900;
}

.hawks-live-badge.is-live{
    color:#ff696f;
    border:1px solid rgba(255,77,85,.35);
    background:rgba(255,55,65,.10);
}

.hawks-live-badge.is-finished{
    color:#9dd9ff;
    border:1px solid rgba(80,176,255,.28);
    background:rgba(41,137,216,.10);
}

.hawks-live-badge.is-waiting{
    color:#ffd977;
    border:1px solid rgba(255,201,75,.30);
    background:rgba(255,201,75,.08);
}

.hawks-live-refresh{
    color:#7f93ad;
    font-size:.68rem;
}


/* ===== GAME CARD ===== */

.hawks-game-card{
    position:relative;
    overflow:hidden;
    box-sizing:border-box;

    width:100%;
    margin:8px 0 18px 0;

    border-radius:18px;
    border:1px solid rgba(73,130,205,.22);

    background:
        radial-gradient(
            circle at 15% 0%,
            rgba(29,83,141,.18),
            transparent 35%
        ),
        linear-gradient(
            160deg,
            #0b1626 0%,
            #07101c 55%,
            #050b13 100%
        );

    box-shadow:
        0 18px 45px rgba(0,0,0,.30),
        inset 0 1px 0 rgba(255,255,255,.04);
}

.hawks-game-card::before{
    content:"";
    position:absolute;
    top:0;
    left:0;
    right:0;
    height:2px;

    background:
        linear-gradient(
            90deg,
            transparent,
            #d9b150,
            #ffe9a0,
            #d9b150,
            transparent
        );

    opacity:.85;
}

.hawks-game-card-head{
    display:flex;
    justify-content:space-between;
    align-items:center;

    padding:13px 17px 10px 17px;

    border-bottom:
        1px solid rgba(255,255,255,.055);
}

.hawks-game-card-title{
    display:flex;
    align-items:center;
    gap:8px;

    color:#f5f8fd;
    font-size:.93rem;
    font-weight:900;
}

.hawks-game-card-source{
    padding:4px 9px;

    border:1px solid rgba(76,145,235,.22);
    border-radius:999px;

    color:#7297c6;
    background:rgba(38,92,158,.08);

    font-size:.62rem;
    font-weight:800;
    letter-spacing:.08em;
}


/* ===== SCORE ===== */

.hawks-score-area{
    display:grid;
    grid-template-columns:1fr .78fr 1fr;
    align-items:center;

    min-height:190px;
    padding:18px 16px 15px 16px;
}

.hawks-team{
    min-width:0;
    text-align:center;
}

.hawks-team-icon{
    font-size:1.45rem;
    line-height:1;
    margin-bottom:7px;
}

.hawks-team-name{
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;

    color:#f5f8fc;
    font-size:.83rem;
    font-weight:900;
    letter-spacing:.04em;
}

.hawks-home .hawks-team-name{
    color:#f2ce69;
}

.hawks-team-sub{
    margin-top:2px;

    color:#62748d;
    font-size:.55rem;
    font-weight:700;
    letter-spacing:.08em;
}

.hawks-score-number{
    margin-top:8px;

    color:#ecf2fa;
    font-size:3.85rem;
    line-height:.95;
    font-weight:900;

    font-variant-numeric:tabular-nums;

    text-shadow:
        0 3px 18px rgba(0,0,0,.35);
}

.hawks-score-main{
    color:#f7d875;

    text-shadow:
        0 0 22px rgba(218,178,73,.12),
        0 3px 18px rgba(0,0,0,.38);
}


/* ===== CENTER ===== */

.hawks-vs-area{
    display:flex;
    flex-direction:column;
    justify-content:center;
    align-items:center;

    gap:9px;
}

.hawks-final-badge{
    padding:4px 10px;

    border-radius:999px;
    border:1px solid rgba(116,155,201,.17);

    background:rgba(42,77,117,.10);

    color:#8197b3;
    font-size:.58rem;
    font-weight:900;
    letter-spacing:.08em;
}

.hawks-vs{
    color:#52657d;
    font-size:.70rem;
    font-weight:900;
    letter-spacing:.14em;
}

.hawks-score-diff{
    width:max-content;
    max-width:100%;

    padding:6px 9px;

    border-radius:8px;

    font-size:.64rem;
    font-weight:900;
    white-space:nowrap;
}

.hawks-behind{
    color:#ff777d;
    border:1px solid rgba(255,83,92,.18);
    background:rgba(255,58,68,.075);
}

.hawks-leading{
    color:#7be9ad;
    border:1px solid rgba(61,217,134,.18);
    background:rgba(52,207,125,.07);
}

.hawks-tied{
    color:#f2d77d;
    border:1px solid rgba(239,197,83,.17);
    background:rgba(239,197,83,.07);
}


/* ===== FOOTER ===== */

.hawks-score-footer{
    display:flex;
    align-items:center;

    gap:7px;

    padding:10px 16px;

    border-top:
        1px solid rgba(255,255,255,.05);

    color:#6e819a;
    background:rgba(4,10,18,.40);

    font-size:.65rem;
    font-weight:600;
}

.hawks-sync-dot{
    width:6px;
    height:6px;

    flex:0 0 6px;

    border-radius:999px;

    background:#44d88e;

    box-shadow:
        0 0 8px rgba(68,216,142,.7);
}

.hawks-auto-badge{
    margin-left:auto;

    padding:2px 6px;

    border-radius:5px;

    color:#57c78f;
    background:rgba(54,204,130,.07);

    font-size:.52rem;
    font-weight:900;
    letter-spacing:.08em;
}


/* ========================================================
   MOBILE
   ======================================================== */

@media screen and (max-width:600px){

    .hawks-live-strip{
        margin-top:5px;
        margin-bottom:11px;

        padding:9px 11px;

        border-radius:10px;
    }

    .hawks-live-title{
        font-size:.77rem;
    }

    .hawks-live-refresh{
        display:none;
    }

    .hawks-game-card{
        border-radius:15px;
        margin-bottom:14px;
    }

    .hawks-game-card-head{
        padding:11px 12px 8px 12px;
    }

    .hawks-game-card-title{
        font-size:.82rem;
    }

    .hawks-score-area{
        grid-template-columns:
            minmax(0,1fr)
            68px
            minmax(0,1fr);

        min-height:160px;

        padding:15px 8px 13px 8px;
    }

    .hawks-team-icon{
        font-size:1.18rem;
        margin-bottom:5px;
    }

    .hawks-team-name{
        font-size:.72rem;
    }

    .hawks-team-sub{
        font-size:.46rem;
    }

    .hawks-score-number{
        margin-top:7px;
        font-size:3.25rem;
    }

    .hawks-vs-area{
        gap:7px;
    }

    .hawks-final-badge{
        padding:3px 7px;
        font-size:.50rem;
    }

    .hawks-vs{
        font-size:.59rem;
    }

    .hawks-score-diff{
        padding:5px 6px;
        font-size:.53rem;
    }

    .hawks-score-footer{
        padding:8px 11px;
        font-size:.56rem;
    }

}

</style>

<style id="hawks-full-premium-theme">

/* =========================================
   HAWKS AI V8 FULL PREMIUM THEME
   ========================================= */

.stApp{
    background:
        radial-gradient(
            circle at top,
            rgba(20,42,72,.75),
            transparent 38%
        ),
        linear-gradient(
            180deg,
            #07101c 0%,
            #09111d 35%,
            #0b1320 100%
        ) !important;
}

/* メインコンテナ */
.block-container{
    max-width:1180px !important;
    padding-top:1.2rem !important;
    padding-bottom:3rem !important;
}

/* 通常テキスト */
.stApp,
.stApp p,
.stApp span,
.stApp label{
    color:#d9e4f2;
}

/* タイトル */
h1,h2,h3,h4{
    color:#f6f8fb !important;
    letter-spacing:.01em;
}

/* 区切り線 */
hr{
    border-color:rgba(255,255,255,.08) !important;
}

/* =========================================
   SECTION HEAD
   ========================================= */

.section-head{
    margin:14px 0 10px 0 !important;
    padding:11px 15px !important;

    border-radius:12px !important;
    border:1px solid rgba(255,255,255,.08) !important;

    background:
        linear-gradient(
            135deg,
            rgba(13,28,48,.96),
            rgba(8,18,31,.96)
        ) !important;

    box-shadow:
        0 8px 28px rgba(0,0,0,.22),
        inset 0 1px 0 rgba(255,255,255,.03);

    color:#edf4ff !important;
    font-weight:900 !important;
}

/* 色別アクセント */
.section-blue{
    border-left:4px solid #4fa6ff !important;
}

.section-purple{
    border-left:4px solid #9c7cff !important;
}

.section-green{
    border-left:4px solid #36cf85 !important;
}

.section-red{
    border-left:4px solid #ff5961 !important;
}

.section-yellow{
    border-left:4px solid #e3bd57 !important;
}

/* =========================================
   STREAMLIT METRIC
   ========================================= */

[data-testid="stMetric"]{
    padding:14px 16px !important;

    border-radius:14px !important;

    border:
        1px solid rgba(102,143,190,.15) !important;

    background:
        linear-gradient(
            160deg,
            rgba(15,31,52,.96),
            rgba(8,17,29,.96)
        ) !important;

    box-shadow:
        0 10px 28px rgba(0,0,0,.20) !important;
}

[data-testid="stMetricLabel"]{
    color:#8fa5bf !important;
    font-size:.74rem !important;
    font-weight:700 !important;
}

[data-testid="stMetricValue"]{
    color:#f5f8fc !important;
    font-weight:900 !important;
    letter-spacing:-.02em !important;
}

[data-testid="stMetricDelta"]{
    font-weight:800 !important;
}

/* =========================================
   INPUTS
   ========================================= */

[data-testid="stNumberInput"],
[data-testid="stSelectbox"],
[data-testid="stSlider"],
[data-testid="stRadio"],
[data-testid="stCheckbox"]{
    border-radius:12px;
}

/* Number input */
[data-testid="stNumberInput"] input{
    color:#f0f5fb !important;
    background:#0c1726 !important;
    border-color:rgba(91,133,181,.18) !important;
}

/* Select */
[data-baseweb="select"] > div{
    background:#0c1726 !important;
    border-color:rgba(91,133,181,.18) !important;
}

/* =========================================
   ALERT BOX
   ========================================= */

[data-testid="stAlert"]{
    border-radius:12px !important;
    border:1px solid rgba(255,255,255,.08) !important;

    background:
        linear-gradient(
            145deg,
            rgba(18,34,54,.96),
            rgba(11,22,37,.96)
        ) !important;

    box-shadow:
        0 8px 22px rgba(0,0,0,.15);
}

/* =========================================
   EXPANDER
   ========================================= */

[data-testid="stExpander"]{
    border-radius:13px !important;

    border:
        1px solid rgba(96,137,184,.16) !important;

    background:
        rgba(9,20,34,.78) !important;

    overflow:hidden;
}

/* =========================================
   BUTTON
   ========================================= */

.stButton > button{
    border-radius:10px !important;

    border:
        1px solid rgba(225,188,89,.35) !important;

    background:
        linear-gradient(
            135deg,
            #1a2534,
            #0e1724
        ) !important;

    color:#f1d982 !important;

    font-weight:800 !important;

    transition:.2s ease;
}

.stButton > button:hover{
    border-color:#e3c15f !important;
    box-shadow:
        0 0 20px rgba(227,193,95,.16);
}

/* =========================================
   CAPTION
   ========================================= */

[data-testid="stCaptionContainer"],
.stCaption{
    color:#7589a3 !important;
}

/* =========================================
   PROGRESS BAR
   ========================================= */

[data-testid="stProgress"] > div > div{
    background:
        linear-gradient(
            90deg,
            #d9b74c,
            #f0d978
        ) !important;
}

/* =========================================
   DATAFRAME / TABLE
   ========================================= */

[data-testid="stDataFrame"]{
    border-radius:12px !important;
    overflow:hidden;

    border:
        1px solid rgba(89,132,181,.14) !important;
}

/* =========================================
   SIDEBAR
   ========================================= */

section[data-testid="stSidebar"]{
    background:
        linear-gradient(
            180deg,
            #08111e,
            #0d1624
        ) !important;
}

section[data-testid="stSidebar"] *{
    color:#dbe6f2 !important;
}

/* =========================================
   COLUMNS GAP
   ========================================= */

[data-testid="stHorizontalBlock"]{
    gap:.8rem !important;
}

/* =========================================
   HIDE STREAMLIT CHROME
   ========================================= */

#MainMenu{
    visibility:hidden;
}

footer{
    visibility:hidden;
}

/* =========================================
   MOBILE
   ========================================= */

@media screen and (max-width:600px){

    .block-container{
        padding-left:.65rem !important;
        padding-right:.65rem !important;
        padding-top:.5rem !important;
    }

    .section-head{
        font-size:.82rem !important;
        padding:9px 11px !important;
    }

    [data-testid="stMetric"]{
        padding:11px 12px !important;
        border-radius:11px !important;
    }

    [data-testid="stMetricValue"]{
        font-size:1.45rem !important;
    }

    [data-testid="stMetricLabel"]{
        font-size:.66rem !important;
    }

}

</style>
<style id="hawks-v8-web-final">
:root{
  --hawks-navy:#07101c;--hawks-navy-2:#0d1b30;--hawks-gold:#d9b150;
  --hawks-red:#d91f2a;--hawks-green:#0d9b50;--hawks-text:#17233a;
  --hawks-muted:#7c899a;--hawks-border:#dde5ee;--hawks-page:#f7f9fc;
}
.stApp{background:linear-gradient(180deg,#f7f9fc 0%,#fff 28%,#fff 100%)!important;color:var(--hawks-text)!important}
.block-container{max-width:1180px!important;padding:0 1.2rem 4rem!important}

.hawks-live-strip{display:flex;justify-content:space-between;align-items:center;gap:12px;margin:0 -1.2rem 18px;padding:15px 20px;border:1px solid rgba(120,151,193,.35);border-radius:0 0 16px 16px;background:linear-gradient(135deg,#0d1b30,#081426);color:#fff;box-shadow:0 10px 24px rgba(11,25,44,.15)}
.hawks-live-left,.hawks-live-right{display:flex;align-items:center;gap:10px}
.hawks-live-dot{width:9px;height:9px;border-radius:50%;background:#ff3b45;box-shadow:0 0 10px rgba(255,59,69,.75)}
.hawks-live-title{font-weight:900}
.hawks-live-refresh{color:#9badc3;font-size:.78rem}
.hawks-live-badge{padding:5px 10px;border-radius:999px;font-size:.72rem;font-weight:900}
.hawks-live-badge.is-live{color:#ff757a;background:rgba(255,58,68,.1);border:1px solid rgba(255,58,68,.22)}
.hawks-live-badge.is-finished{color:#b7dfff;background:rgba(69,145,214,.1);border:1px solid rgba(69,145,214,.22)}
.hawks-live-badge.is-waiting{color:#f4d477;background:rgba(218,176,67,.1);border:1px solid rgba(218,176,67,.22)}

.hawks-game-card{overflow:hidden;margin:18px 0;border:1px solid rgba(217,31,42,.32);border-left:5px solid var(--hawks-red);border-radius:18px;background:#fff;box-shadow:0 10px 26px rgba(143,46,52,.08)}
.hawks-game-card-head{display:flex;justify-content:space-between;align-items:center;padding:16px 18px;border-bottom:1px solid rgba(217,31,42,.1)}
.hawks-game-card-title{display:flex;align-items:center;gap:9px;color:#c6262f;font-size:1.03rem;font-weight:950}
.hawks-red-dot{width:12px;height:12px;border-radius:50%;background:#e01f2b}
.hawks-game-card-source{padding:5px 9px;border-radius:999px;color:#bd343a;background:#fff2f3;border:1px solid rgba(224,63,69,.16);font-size:.68rem;font-weight:900}
.hawks-score-area{display:grid;grid-template-columns:1fr .72fr 1fr;align-items:center;min-height:210px;padding:22px 20px}
.hawks-team{text-align:center}.hawks-team-icon{font-size:2rem}.hawks-team-name{margin-top:6px;color:#17233a;font-weight:950}.hawks-team-sub{margin-top:2px;color:#7e8a9b;font-size:.68rem}
.hawks-score-number{margin-top:10px;color:#0f1a31;font-size:4.8rem;line-height:.9;font-weight:950}.hawks-score-main{color:#e3232c}
.hawks-vs-area{display:flex;flex-direction:column;align-items:center;gap:10px}.hawks-final-badge{padding:5px 11px;border-radius:999px;color:#0f8d49;background:rgba(19,164,88,.08);border:1px solid rgba(19,164,88,.16);font-size:.68rem;font-weight:900}.hawks-vs{color:#a0a9b5;font-size:.72rem;font-weight:900;letter-spacing:.12em}
.hawks-score-diff{padding:7px 10px;border-radius:9px;font-size:.72rem;font-weight:950;white-space:nowrap}.hawks-leading{color:#0d9b50;background:#eef9f2}.hawks-behind{color:#d32630;background:#fff2f3}.hawks-tied{color:#9a7000;background:#fff9e8}
.hawks-score-footer{display:flex;align-items:center;gap:8px;padding:10px 16px;border-top:1px solid rgba(43,64,91,.07);background:#fafbfd;color:#7d8999;font-size:.67rem}.hawks-sync-dot{width:7px;height:7px;border-radius:50%;background:#44d88e}.hawks-auto-badge{margin-left:auto;padding:3px 6px;border-radius:5px;color:#0d9b50;background:#eef9f2;font-size:.56rem;font-weight:900}

.hawks-ai-card{margin:20px 0;border:1px solid rgba(13,155,80,.28);border-left:5px solid var(--hawks-green);border-radius:18px;background:#fff;box-shadow:0 10px 28px rgba(18,115,66,.07)}
.hawks-ai-head{display:flex;align-items:center;gap:12px;padding:16px 18px;color:#0d9b50;font-weight:950;font-size:1.08rem}
.hawks-ai-icon{display:grid;place-items:center;width:48px;height:48px;border-radius:50%;background:#0d9b50;color:#fff}
.hawks-ai-body{display:grid;grid-template-columns:.9fr 1.4fr;gap:28px;align-items:center;margin:0 18px 18px;padding:22px;border:1px solid #e1e8ef;border-radius:14px}
.hawks-ai-label{font-size:.9rem}.hawks-ai-value{margin-top:6px;color:#0d9b50;font-size:3.8rem;line-height:.95;font-weight:950}.hawks-ai-value span{font-size:1.5rem}
.hawks-ai-track{height:14px;border-radius:999px;background:#e9edf2;overflow:hidden}.hawks-ai-fill{height:100%;border-radius:inherit;background:linear-gradient(90deg,#0d9b50,#42bf79)}.hawks-ai-caption{margin-top:10px;color:#0d9b50;font-weight:850;font-size:.8rem}

.hawks-info-card{display:flex;align-items:center;gap:12px;margin:18px 0;padding:16px 18px;border:1px solid rgba(217,177,80,.55);border-radius:14px;background:#fffaf0}
.hawks-info-title{color:#a87700;font-weight:950}.hawks-info-text{margin-left:8px;color:#42506a;font-size:.8rem}.hawks-info-arrow{margin-left:auto;color:#b2871a;font-size:1.7rem}

@media(max-width:600px){
  .block-container{padding:0 .65rem 5rem!important}
  .hawks-live-strip{margin:0 -.65rem 14px;padding:12px 14px}
  .hawks-score-area{grid-template-columns:1fr 64px 1fr;min-height:175px;padding:16px 8px}
  .hawks-score-number{font-size:3.6rem}.hawks-team-icon{font-size:1.5rem}.hawks-team-name{font-size:.76rem}.hawks-team-sub{font-size:.55rem}
  .hawks-score-diff{padding:5px 7px;font-size:.56rem}
  .hawks-ai-body{grid-template-columns:1fr 1.2fr;gap:16px;padding:16px}.hawks-ai-value{font-size:3rem}
  .hawks-info-text{display:none}
}

/* =====================================================
   HAWKS AI V8 READABILITY FIX
   ===================================================== */

/* 通常本文 */
.stApp,
.stApp p,
.stApp label,
.stApp span {
    color: #17233a;
}

/* キャプション */
div[data-testid="stCaptionContainer"],
div[data-testid="stCaptionContainer"] p {
    color: #7c899a !important;
}

/* Metric */
div[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1px solid #dde5ee !important;
    border-radius: 14px !important;
    box-shadow: 0 4px 14px rgba(20,35,60,.06) !important;
}

div[data-testid="stMetricLabel"] p {
    color: #718096 !important;
    font-weight: 700 !important;
}

div[data-testid="stMetricValue"] {
    color: #17233a !important;
    font-weight: 900 !important;
}

/* セクションタイトル */
.section-head {
    background: linear-gradient(
        135deg,
        #132238 0%,
        #0c1828 100%
    ) !important;

    color: #ffffff !important;

    border-radius: 12px !important;
    padding: 12px 16px !important;
    font-weight: 900 !important;

    box-shadow:
        0 8px 20px rgba(8,20,38,.12) !important;
}

/* セクション内文字は白 */
.section-head,
.section-head * {
    color: #ffffff !important;
}

/* 今日の試合カード */
div[data-testid="stHorizontalBlock"] div[data-testid="stMetric"] {
    color: #17233a !important;
}

/* 入力フォーム */
div[data-testid="stNumberInput"] input {
    background: #ffffff !important;
    color: #17233a !important;
    border: 1px solid #dce4ed !important;
}

/* ラジオ・チェック */
div[data-testid="stRadio"] label,
div[data-testid="stCheckbox"] label {
    color: #17233a !important;
}

/* LIVEバーは白文字を維持 */
.hawks-live-strip,
.hawks-live-strip *,
.hawks-live-title,
.hawks-live-refresh {
    color: #ffffff !important;
}

/* スコアカード */
.hawks-game-card,
.hawks-game-card * {
    color: #17233a;
}

.hawks-game-card-title {
    color: #d91f2a !important;
}

.hawks-score-main {
    color: #e3232c !important;
}

.hawks-leading {
    color: #0d9b50 !important;
}

.hawks-behind {
    color: #d32630 !important;
}

/* AIカード */
.hawks-ai-head,
.hawks-ai-value,
.hawks-ai-caption {
    color: #0d9b50 !important;
}


/* =====================================================
   TOP HEADER TEXT VISIBILITY FIX
   ===================================================== */

/* Streamlitタイトル */
h1,
h2,
h3,
h4,
h5,
h6,
[data-testid="stMarkdownContainer"] h1,
[data-testid="stMarkdownContainer"] h2,
[data-testid="stMarkdownContainer"] h3,
[data-testid="stMarkdownContainer"] h4 {
    color: #14213d !important;
    opacity: 1 !important;
    visibility: visible !important;
}

/* 上部Markdown本文 */
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] strong,
[data-testid="stMarkdownContainer"] b {
    color: #17233a !important;
    opacity: 1 !important;
}

/* 通常ラベル */
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span {
    color: #526176 !important;
}

/* Metric文字 */
[data-testid="stMetricLabel"] *,
[data-testid="stMetricValue"] * {
    color: #17233a !important;
}

/* セクション見出しだけ白文字を維持 */
.section-head,
.section-head *,
.hawks-live-strip,
.hawks-live-strip * {
    color: #ffffff !important;
}

/* 試合カードタイトルは赤 */
.hawks-game-card-title,
.hawks-game-card-title * {
    color: #d91f2a !important;
}

/* AIカードタイトルは緑 */
.hawks-ai-head,
.hawks-ai-head * {
    color: #0d9b50 !important;
}


/* ================================
   PITCHER CARD TEXT FIX
   ================================ */

[data-testid="stAlert"]{
    background:#16304f !important;
    border:1px solid rgba(255,255,255,.06) !important;
}

[data-testid="stAlert"] p,
[data-testid="stAlert"] strong,
[data-testid="stAlert"] span,
[data-testid="stAlert"] div{
    color:#ffffff !important;
}


</style>

<style id="hawks-hero-final">

.hawks-hero {
  min-height: 260px;
  background-size: 108% auto;
  background-position: 71% 77%;
  background-repeat: no-repeat;
}

.hawks-hero::before {
  background: linear-gradient(90deg,
    rgba(0, 0, 0, 0.5) 0%,
    rgba(0, 0, 0, 0) 68%
  );
}

@media (max-width: 600px) {
  .hawks-hero {
    min-height: 190px;
    background-size: cover;
    background-position: 50% 50%;
    overflow: hidden;
  }

  .hawks-hero::before {
    background: linear-gradient(90deg,
      rgba(0, 0, 0, 0.6) 0%,
      rgba(0, 0, 0, 0) 82%
    );
  }
}

.hawks-hero::after{
    content:"";
    position:absolute;
    inset:0;

    pointer-events:none;

    background:
        repeating-linear-gradient(
            115deg,
            transparent 0,
            transparent 28px,
            rgba(255,255,255,.012) 29px,
            transparent 30px
        );
}

.hawks-hero-kicker{
    position:relative;
    z-index:1;

    color:#fff !important;

    font-size:1rem;
    font-weight:800;
    letter-spacing:.01em;
}

.hawks-hero-mainrow{
    position:relative;
    z-index:1;

    display:flex;
    align-items:center;
    justify-content:space-between;

    gap:20px;

    margin-top:10px;
}

.hawks-hero-title{
    display:flex;
    align-items:center;
    gap:14px;

    color:#fff !important;

    font-size:4rem;
    line-height:.95;

    font-weight:950;
    letter-spacing:-.045em;
}

.hawks-v8-badge{
    display:inline-flex;
    align-items:center;
    justify-content:center;

    padding:5px 12px 7px;

    border:2px solid #d9b150;
    border-radius:9px;

    color:#f3d97a !important;

    font-size:1.65rem;
    font-weight:950;
    letter-spacing:-.02em;

    box-shadow:
        inset 0 0 15px rgba(217,177,80,.05);
}

.hawks-hero-actions{
    display:flex;
    align-items:center;
    gap:14px;
}

.hawks-update-pill{
    display:flex;
    align-items:center;

    padding:11px 16px;

    border:1px solid rgba(255,255,255,.38);
    border-radius:999px;

    background:rgba(4,11,21,.58);

    color:#fff !important;

    font-size:.88rem;
    font-weight:850;

    backdrop-filter:blur(5px);
}

.hawks-menu-icon{
    color:#fff !important;

    font-size:2.35rem;
    line-height:1;
    font-weight:300;
}

.hawks-hero-sub{
    position:relative;
    z-index:1;

    margin-top:14px;

    color:#fff !important;

    font-size:1.08rem;
    font-weight:850;
}

/* ===== PCの左寄りを改善 ===== */

.block-container{
    max-width:1180px !important;
    margin-left:auto !important;
    margin-right:auto !important;
}

/* ===== 先発投手カードの文字を白に ===== */

div[data-testid="stAlert"]{
    color:#17233a !important;
}

div[data-testid="stAlert"] p,
div[data-testid="stAlert"] strong,
div[data-testid="stAlert"] span{
    color:#17233a !important;
}

/* ===== 先発投手カード ===== */
.pitcher-card{
    background:#ffffff;
    border:1px solid #dce4ee;
    border-radius:14px;
    padding:16px 18px;
    min-height:78px;
    box-shadow:0 6px 18px rgba(15,35,60,.06);
    color:#17233a !important;
}

.pitcher-card *{
    color:#17233a !important;
}

.pitcher-card .pitcher-name{
    font-size:1.08rem;
    font-weight:900;
    margin-bottom:8px;
    line-height:1.25;
}

.pitcher-card .pitcher-stats{
    display:flex;
    align-items:center;
    gap:9px;
    flex-wrap:wrap;
    font-size:.86rem;
    font-weight:700;
    color:#607087 !important;
}

.pitcher-card .pitcher-stats span{
    color:#607087 !important;
}

.pitcher-card .pitcher-era{
    color:#0877d8 !important;
    font-weight:900;
}

.pitcher-card .pitcher-grade{
    display:inline-flex;
    align-items:center;
    padding:3px 9px;
    border-radius:999px;
    background:#eef7ff;
    color:#0877d8 !important;
    font-size:.78rem;
    font-weight:850;
}

@media screen and (max-width:600px){
    .pitcher-card{
        padding:13px 14px;
        min-height:72px;
    }

    .pitcher-card .pitcher-name{
        font-size:1rem;
    }

    .pitcher-card .pitcher-stats{
        gap:6px;
        font-size:.78rem;
    }
}

/* ===== MOBILE ===== */

@media screen and (max-width:600px){

    .hawks-hero{
        margin-left:-.65rem;
        margin-right:-.65rem;

        padding:24px 16px 24px;

        min-height:205px;

        border-radius:0;
    }

    .hawks-hero-kicker{
        font-size:.83rem;
    }

    .hawks-hero-mainrow{
        align-items:flex-start;
        gap:8px;
    }

    .hawks-hero-title{
        gap:8px;

        font-size:2.7rem;
    }

    .hawks-v8-badge{
        padding:4px 8px 5px;

        font-size:1.08rem;
    }

    .hawks-hero-actions{
        gap:7px;
    }

    .hawks-update-pill{
        padding:7px 10px;

        font-size:.69rem;
    }

    .hawks-menu-icon{
        font-size:1.8rem;
    }

    .hawks-hero-sub{
        margin-top:10px;

        font-size:.88rem;
    }
}



/* ===== FINAL PC HERO VISUAL ===== */
@media screen and (min-width:601px){

    .hawks-hero{
        min-height:260px !important;
        padding:28px 28px 24px !important;
        background-size:cover !important;
        background-position:center center !important;
    }

    .hawks-hero-kicker{
        font-size:.90rem !important;
    }

    .hawks-hero-title{
        font-size:3.25rem !important;
    }

    .hawks-hero-sub{
        font-size:.95rem !important;
    }
}
/* ===== /FINAL PC HERO VISUAL ===== */

</style>















""", unsafe_allow_html=True)


# =========================================================
# HAWKS AI 試合前予測 固定保存
# =========================================================
from storage.pregame_predictions import (
    get_pregame_probability as _get_pregame_probability,
    load_pregame_predictions as _load_pregame_predictions,
    save_pregame_prediction as _save_pregame_prediction,
)

PREGAME_PREDICTION_FILE = DATA_DIR / "pregame_predictions.json"


def load_pregame_predictions():
    return _load_pregame_predictions(PREGAME_PREDICTION_FILE)


def save_pregame_prediction(date_value, opponent, probability_value, model="V8 FINAL"):
    return _save_pregame_prediction(
        PREGAME_PREDICTION_FILE,
        date_value,
        opponent,
        probability_value,
        model,
    )


def get_pregame_probability(date_value, opponent):
    return _get_pregame_probability(PREGAME_PREDICTION_FILE, date_value, opponent)

# =========================================================
# HAWKS AI PREMIUM TOP DASHBOARD (PC / MOBILE)
st.markdown(r"""
<style id="hawks-premium-top-v9">
.hawks-premium-shell{margin-top:0;padding:12px 18px 18px;border-radius:0 0 20px 20px;background:linear-gradient(145deg,#06090d,#0c1218 68%,#05080b);box-shadow:0 18px 44px rgba(5,12,20,.24);color:#fff}
.hawks-premium-news{display:flex;align-items:center;gap:18px;min-height:54px;padding:0 20px;border:1px solid rgba(219,177,59,.75);border-radius:15px;background:rgba(4,8,11,.86);font-weight:850}
.hawks-premium-news .dot{width:12px;height:12px;border-radius:50%;background:#ef2632;box-shadow:0 0 12px rgba(239,38,50,.55)}
.hawks-premium-news .source{padding-right:18px;border-right:1px solid rgba(255,255,255,.18)}
.hawks-premium-news .auto{margin-left:auto;padding:7px 13px;border:1px solid #d8ae34;border-radius:10px;color:#f4cc55;font-size:.78rem}
.hawks-premium-card{overflow:hidden;margin-top:8px;border-radius:20px;background:#fff;color:#10151d;box-shadow:0 12px 34px rgba(0,0,0,.28)}
.hawks-premium-score{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;min-height:155px;padding:26px 38px 18px}
.hawks-premium-team{display:flex;align-items:center;gap:18px}.hawks-premium-team.right{justify-content:flex-end;text-align:right}
.hawks-premium-logo{display:block;flex:0 0 auto;width:82px;height:82px;border:1px solid #edf0f3;border-radius:50%;background-color:#fff;background-image:none;background-size:400% 300%;background-repeat:no-repeat;box-shadow:0 6px 20px rgba(14,26,42,.14)}
.logo-hanshin{background-position:0 0}.logo-giants{background-position:33.333% 0}.logo-dragons{background-position:66.667% 0}.logo-carp{background-position:100% 0}
.logo-baystars{background-position:0 50%}.logo-swallows{background-position:33.333% 50%}.logo-hawks{background-position:66.667% 50%}.logo-marines{background-position:100% 50%}
.logo-eagles{background-position:0 100%}.logo-fighters{background-position:33.333% 100%}.logo-lions{background-position:66.667% 100%}.logo-buffaloes{background-position:100% 100%}
.logo-generic{background-image:none;position:relative}.logo-generic::after{content:'NPB';display:grid;place-items:center;height:100%;color:#17233a;font-weight:950}
.hawks-premium-team-name{font-size:1.45rem;font-weight:950}.hawks-premium-team-sub{margin-top:4px;color:#687383;font-size:.74rem;font-weight:750}
.hawks-premium-scoreline{text-align:center;padding:0 28px}.hawks-premium-scoreline .numbers{font-size:3.9rem;line-height:1;font-weight:950;letter-spacing:.04em}.hawks-premium-scoreline .hawks-num{color:#d51e2a}.hawks-premium-status{display:inline-flex;margin-top:12px;padding:6px 13px;border-radius:999px;background:#0a0e13;color:#fff;font-size:.74rem;font-weight:900}
.hawks-premium-result{display:flex;justify-content:center;gap:24px;padding:13px;border-top:1px solid #eef0f2;color:#1b2028;font-weight:900}.hawks-premium-result .diff{padding:5px 13px;border-radius:999px;background:#ffe8e8;color:#e12631}
.hawks-premium-ai{display:grid;grid-template-columns:auto 220px 1fr auto;align-items:center;gap:18px;margin:18px;padding:24px;border:1px solid #e7eaee;border-radius:16px;box-shadow:0 5px 20px rgba(10,25,42,.05)}
.hawks-premium-bot{display:grid;place-items:center;width:64px;height:64px;border-radius:50%;background:#075c37;color:#fff;font-size:1.8rem}.hawks-premium-ai-label{font-weight:850}.hawks-premium-prob{color:#2daf68;font-size:2.8rem;font-weight:950;line-height:1.05}.hawks-premium-track{height:15px;overflow:hidden;border-radius:999px;background:#e0e4e9}.hawks-premium-track>span{display:block;height:100%;border-radius:inherit;background:linear-gradient(90deg,#28b563,#54c883)}.hawks-premium-confidence{text-align:center;font-weight:850}.hawks-premium-confidence b{display:block;color:#27ae65;font-size:1.5rem}
.hawks-premium-detail-title{margin:0 18px;padding:18px 22px;border-radius:14px 14px 0 0;background:#070b0f;color:#fff;font-weight:900}.hawks-premium-details{display:grid;grid-template-columns:repeat(4,1fr);margin:0 18px 18px;border:1px solid #e5e8ec;border-top:0;border-radius:0 0 14px 14px}.hawks-premium-detail{padding:18px;border-right:1px solid #e8ebee}.hawks-premium-detail:last-child{border-right:0}.hawks-premium-detail small{display:block;margin-bottom:9px;color:#677383;font-weight:750}.hawks-premium-detail b{font-size:1rem}.hawks-premium-detail .green{color:#20a95e}
.hawks-premium-foot{display:flex;justify-content:space-between;padding:4px 8px 2px;color:#aab2bc;font-size:.74rem}
/* 旧速報カードは新しい統合カードに置き換える */
.hawks-live-strip,.hawks-game-card{display:none!important}

</style>
""", unsafe_allow_html=True)

# =========================================================
# HAWKS AI V8 HERO HEADER
# ===== Dynamic HERO Banner : WIN / HOME / AWAY / weekday =====
import json

_now_dt_jst = datetime.now(ZoneInfo("Asia/Tokyo"))
_now_jst = _now_dt_jst.strftime("%H:%M")

# 試合がない場合は固定のOFFバナー
_banner_filename = "banner_off.webp"
_banner_mode = "off"

try:
    _npb_today_path = Path("/app/data/npb_today.json")

    if _npb_today_path.exists():
        _npb_today = json.loads(
            _npb_today_path.read_text(encoding="utf-8")
        )

        _hawks_game = next(
            (
                g for g in _npb_today.get("games", [])
                if g.get("home") == "ソフトバンク"
                or g.get("away") == "ソフトバンク"
            ),
            None
        )

        if _hawks_game:
            _hawks_home = _hawks_game.get("home") == "ソフトバンク"

            _home_score = _hawks_game.get("home_score")
            _away_score = _hawks_game.get("away_score")

            _hawks_score = _home_score if _hawks_home else _away_score
            _opp_score = _away_score if _hawks_home else _home_score

            if (
                _hawks_game.get("status") == "final"
                and _hawks_score is not None
                and _opp_score is not None
                and _hawks_score > _opp_score
            ):
                _banner_filename = "banner_win.webp"
                _banner_mode = "win"

            elif _hawks_home:
                _banner_filename = "banner_home.webp"
                _banner_mode = "home"

            else:
                _banner_filename = "banner_away.webp"
                _banner_mode = "away"

except Exception as _banner_error:
    print("HERO BANNER SELECT ERROR:", _banner_error)

# 状態別の固定バナーを選択
_pc_banner_filename = _banner_filename

# スマホも同じ状態別バナーを中央トリミングで表示
_mobile_banner_filename = None

_pc_banner_path = (
    Path("/app/static/banners/pc") / _pc_banner_filename
)
_pc_banner_url = (
    f"app/static/banners/pc/{_pc_banner_filename}"
)

if _mobile_banner_filename:
    _mobile_banner_url = (
        f"app/static/banners/mobile/{_mobile_banner_filename}"
    )
else:
    _mobile_banner_url = _pc_banner_url

try:
    if _pc_banner_path.exists():

        st.markdown(
            f"""
<style id="hawks-dynamic-banner-final">

.hawks-hero {{
    background-image:
        linear-gradient(
            90deg,
            rgba(0,0,0,.34) 0%,
            rgba(0,0,0,.16) 40%,
            rgba(0,0,0,.06) 100%
        ),
        url("{_pc_banner_url}") !important;

    background-size:cover !important;
    background-position:center center !important;
    background-repeat:no-repeat !important;
}}

@media (max-width: 768px) {{
    .hawks-hero {{
        background-image:
            linear-gradient(
                90deg,
                rgba(0,0,0,.28) 0%,
                rgba(0,0,0,.12) 55%,
                rgba(0,0,0,.04) 100%
            ),
            url("{_mobile_banner_url}") !important;

        background-size:cover !important;
        background-position:center center !important;
        background-repeat:no-repeat !important;
    }}
}}

/* 新バナーを見せるため既存の暗幕を弱くする */
.hawks-hero::after {{
    background:linear-gradient(
        90deg,
        rgba(0,0,0,.18),
        rgba(0,0,0,.02)
    ) !important;
}}

/* PC */
@media screen and (min-width:601px) {{
    .hawks-hero {{
        min-height:230px !important;
        background-size:cover !important;
        background-position:center center !important;
    }}
}}

/* スマホ */
@media screen and (max-width:600px) {{
    .hawks-hero {{
        min-height:205px !important;
        background-size:cover !important;
        background-position:center center !important;
    }}

    .hawks-hero-kicker,
    .hawks-hero-sub {{
        text-shadow:0 2px 8px rgba(0,0,0,.95);
    }}

    .hawks-hero-title {{
        text-shadow:0 3px 12px rgba(0,0,0,.95);
    }}
}}

</style>
""",
            unsafe_allow_html=True
        )

        print(
            "HERO BANNER:",
            _banner_mode,
            _banner_filename
        )

    else:
        print("HERO BANNER FILE NOT FOUND:", _pc_banner_path)

except Exception as _banner_render_error:
    print("HERO BANNER RENDER ERROR:", _banner_render_error)

st.markdown(
    f"""<div class="hawks-hero">
<div class="hawks-hero-kicker">福岡ソフトバンクホークスをAIが徹底分析</div>
<div class="hawks-hero-mainrow">
<div class="hawks-hero-title">HAWKS AI <span class="hawks-v8-badge">V8</span></div>
<div class="hawks-hero-actions">
<div class="hawks-update-pill">◷ {_now_jst} 更新</div>
<div class="hawks-menu-icon">☰</div>
</div>
</div>
<div class="hawks-hero-sub">最新データで勝利を予測</div>
</div>""",
    unsafe_allow_html=True
)

# データ計算後に内容を入れても、表示位置はHero直下に維持される
premium_top_slot = st.empty()

# ===== HAWKS AI v2.0 ハンディ計算 =====
# 操作UIは非表示。
# handicap_score は上部プレミアム表示・AI計算・勝敗判定で使用するため維持。
handicap_score = -2.0


# ===== PREMIUM HANDICAP DISPLAY =====
# 表示上はマイナスを出さない。
# ハンデ対象チームだけ数値を表示し、基準側は0。
# handicap_score < 0 : ホークス側にハンデ
# handicap_score > 0 : 相手側にハンデ
premium_hawks_handicap = 0.0
premium_opp_handicap = 0.0

if handicap_score < 0:
    premium_hawks_handicap = abs(float(handicap_score))

elif handicap_score > 0:
    premium_opp_handicap = abs(float(handicap_score))

def format_premium_handicap(value):
    if value is None:
        return "未発表"

    try:
        value = float(value)
    except (TypeError, ValueError):
        return "－"

    if value == 0:
        return "0"

    if value.is_integer():
        return str(int(value))

    return f"{value:.1f}"

# ===== HANDICAP UI HIDDEN =====
# handicap_score / premium_opp_handicap / premium_hawks_handicap は
# 上部プレミアム表示・AI計算・ハンデ判定で引き続き使用。


st.caption(
    "＋ = ホークスリード　／　0 = 同点　／　－ = ホークスビハインド"
)

# ===== HAWKS AI v2.0 NPB自動取得 =====

def fetch_next_hawks_game_from_npb():
    from datetime import datetime
    from zoneinfo import ZoneInfo
    import re
    import requests
    from bs4 import BeautifulSoup

    now = datetime.now(ZoneInfo("Asia/Tokyo"))
    year = now.year

    team_names = [
        "日本ハム", "楽天", "西武", "ロッテ",
        "オリックス", "ソフトバンク",
        "巨人", "阪神", "広島", "DeNA",
        "中日", "ヤクルト",
    ]

    stadium_alias = {
        "エスコンＦ": "エスコンフィールド",
        "みずほPayPay": "みずほPayPayドーム",
        "神　宮": "神宮球場",
        "横　浜": "横浜スタジアム",
    }

    # 今月＋翌月まで確認
    months = [now.month]
    next_month = 1 if now.month == 12 else now.month + 1
    if next_month != now.month:
        months.append(next_month)

    for month in months:
        target_year = year + (1 if now.month == 12 and month == 1 else 0)

        url = (
            f"https://npb.jp/games/{target_year}/"
            f"schedule_{month:02d}_detail.html"
        )

        try:
            r = requests.get(
                url,
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=15,
            )
            r.raise_for_status()

            # r.textではなくbytesを渡してcharsetを自動判定
            soup = BeautifulSoup(r.content, "html.parser")
        except Exception:
            continue

        current_date = None

        for tr in soup.find_all("tr"):
            text = " ".join(tr.get_text(" ", strip=True).split())

            # 行内の日付を更新
            dm = re.search(r"(\d{1,2})/(\d{1,2})", text)

            if dm:
                m, d = map(int, dm.groups())

                try:
                    current_date = datetime(
                        target_year,
                        m,
                        d,
                        tzinfo=ZoneInfo("Asia/Tokyo"),
                    )
                except ValueError:
                    current_date = None

            if current_date is None:
                continue

            # 今日より前は除外
            if current_date.date() < now.date():
                continue

            if "ソフトバンク" not in text:
                continue

            opponent = "-"

            for team in team_names:
                if team != "ソフトバンク" and team in text:
                    opponent = team
                    break

            tm = re.search(r"(\d{1,2}:\d{2})", text)
            game_time = tm.group(1) if tm else "-"

            stadium = "-"

            if tm:
                before_time = text[:tm.start()]

                # 日付・チーム名・記号を除去
                cleaned = re.sub(
                    r"\d{1,2}/\d{1,2}[（(][^）)]*[）)]",
                    " ",
                    before_time,
                )

                for team in team_names:
                    cleaned = cleaned.replace(team, " ")

                cleaned = cleaned.replace("-", " ")
                cleaned = " ".join(cleaned.split())

                if cleaned:
                    # 最後に残った語を球場として使用
                    stadium = cleaned.split()[-1]

            stadium = stadium_alias.get(stadium, stadium)

            return {
                "ok": True,
                "opponent": opponent,
                "stadium": stadium,
                "time": game_time,
                "game_date": current_date.strftime("%Y-%m-%d"),
                "game_date_label": current_date.strftime("%m/%d"),
                "is_today": current_date.date() == now.date(),
                "game_label": (
                    "今日の試合"
                    if current_date.date() == now.date()
                    else "次の試合"
                ),
            }

    return {"ok": False}



@st.cache_data(ttl=900)
def fetch_hawks_announced_starters(opponent_name, stadium_name, game_time):
    """
    NPB公式「予告先発投手」から
    ソフトバンク戦の2投手を取得する。
    """
    result = {
        "ok": False,
        "hawks_starter": "-",
        "opp_starter": "-",
    }

    try:
        import urllib.request
        from bs4 import BeautifulSoup

        url = "https://npb.jp/announcement/starter/"

        req = urllib.request.Request(
            url,
            headers={
                "User-Agent":
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )

        html = urllib.request.urlopen(
            req,
            timeout=10
        ).read()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # NPBの予告先発ページでは、
        # 1試合につき「球団・投手」×2 + 球場/時刻という構造。
        # リンクテキストから選手名を取得する。
        rows = []

        for a in soup.find_all("a", href=True):
            text = a.get_text(" ", strip=True)

            if not text:
                continue

            href = a.get("href", "")

            # 選手個人ページへのリンクだけ候補にする
            if "/bis/players/" in href:
                rows.append({
                    "name": text,
                    "node": a,
                })

        # 2人ずつペアとして確認
        for i in range(0, len(rows) - 1, 2):
            p1 = rows[i]
            p2 = rows[i + 1]

            # 2人のリンク周辺のテキストを取得
            parent1 = p1["node"].find_parent(
                ["li", "div", "td"]
            )
            parent2 = p2["node"].find_parent(
                ["li", "div", "td"]
            )

            ctx1 = (
                parent1.get_text(" ", strip=True)
                if parent1 else ""
            )
            ctx2 = (
                parent2.get_text(" ", strip=True)
                if parent2 else ""
            )

            context = f"{ctx1} {ctx2}"

            # 球団名または球場名で対象試合を判定
            if (
                "ソフトバンク" not in context
                and "ホークス" not in context
                and str(stadium_name) not in context
            ):
                continue

            n1 = p1["name"].strip()
            n2 = p2["name"].strip()

            # 周辺の球団表記で左右判定
            if "ソフトバンク" in ctx1 or "ホークス" in ctx1:
                result["hawks_starter"] = n1
                result["opp_starter"] = n2
            elif "ソフトバンク" in ctx2 or "ホークス" in ctx2:
                result["hawks_starter"] = n2
                result["opp_starter"] = n1
            else:
                # 球場一致だけの場合は、
                # opponent_name の周辺判定
                if str(opponent_name) in ctx1:
                    result["opp_starter"] = n1
                    result["hawks_starter"] = n2
                else:
                    result["hawks_starter"] = n1
                    result["opp_starter"] = n2

            result["ok"] = True
            return result

    except Exception:
        pass

    return result


@st.cache_data(ttl=900)
def fetch_hawks_npb_data():
    result = {
        "ok": False,
        "opponent": "取得中",
        "stadium": "-",
        "time": "-",
        "hawks_starter": "-",
        "opp_starter": "-",
        "rank": "-",
        "wins": "-",
        "losses": "-",
        "draws": "-",
        "pct": "-",
        "recent5": [],
        "game_date": "-",
        "game_date_label": "-",
        "is_today": True,
        "game_label": "今日の試合",
    }

    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        # --- パ・リーグTOP：今日の試合 / 順位 / 予告先発 ---
        req = urllib.request.Request(
            "https://npb.jp/pl/",
            headers=headers
        )
        html = urllib.request.urlopen(req, timeout=10).read()
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        # 順位
        m = re.search(
            r"福岡ソフトバンク(?:ホークス)?\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\.\d+)",
            text
        )
        if m:
            games, wins, losses, draws, pct = m.groups()
            result["rank"] = "1"
            result["wins"] = wins
            result["losses"] = losses
            result["draws"] = draws
            result["pct"] = pct

        # 今日の試合がなければ、次のホークス戦を自動取得
        try:
            from datetime import datetime, timedelta
            from zoneinfo import ZoneInfo
            import requests

            now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))

            found_game = False

            # 今日を含めて未来7日まで検索
            for day_offset in range(0, 8):

                target_dt = now_jst + timedelta(days=day_offset)
                target_ymd = target_dt.strftime("%Y%m%d")

                game_url = f"https://handenomori.com/jpb/{target_ymd}/"

                try:
                    r = requests.get(
                        game_url,
                        headers=headers,
                        timeout=10
                    )
                    r.raise_for_status()
                except Exception:
                    continue

                game_soup = BeautifulSoup(
                    r.text,
                    "html.parser"
                )

                hawks_game = None

                for game in game_soup.select(".game-detail2"):
                    teams = [
                        x.get_text(" ", strip=True)
                        for x in game.select(".detail-card-team")
                    ]

                    if any(
                        "ソフトバンク" in x
                        for x in teams
                    ):
                        hawks_game = game
                        break

                if hawks_game is None:
                    continue

                teams = [
                    x.get_text(" ", strip=True)
                    for x in hawks_game.select(".detail-card-team")
                ]

                if len(teams) >= 2:
                    if "ソフトバンク" in teams[0]:
                        result["opponent"] = teams[1]
                    else:
                        result["opponent"] = teams[0]

                # ===== ハンデの森 実ハンデ取得 =====
                # teams[0] = ホーム / teams[1] = ビジター
                result["hawks_handicap"] = None
                result["opp_handicap"] = None

                handi_cells = hawks_game.select(
                    "table.single-handi td.single-handi-handi"
                )

                if len(handi_cells) >= 2 and len(teams) >= 2:
                    home_text = handi_cells[0].get_text(
                        " ",
                        strip=True
                    )
                    visitor_text = handi_cells[1].get_text(
                        " ",
                        strip=True
                    )

                    def _parse_handi(v):
                        v = str(v).strip()

                        # 空欄は「0点」と決めつけず未取得扱い
                        if not v:
                            return None

                        v = (
                            v.replace("＋", "+")
                             .replace("−", "-")
                             .replace("－", "-")
                             .replace("点", "")
                             .strip()
                        )

                        try:
                            return float(v)
                        except (TypeError, ValueError):
                            return None

                    home_handi = _parse_handi(home_text)
                    visitor_handi = _parse_handi(visitor_text)

                    if "ソフトバンク" in teams[0]:
                        result["hawks_handicap"] = home_handi
                        result["opp_handicap"] = visitor_handi
                    else:
                        result["hawks_handicap"] = visitor_handi
                        result["opp_handicap"] = home_handi

                info = hawks_game.select(
                    ".detail-single-studium-time span"
                )

                if len(info) >= 2:
                    result["time"] = info[0].get_text(
                        " ",
                        strip=True
                    )
                    result["stadium"] = info[1].get_text(
                        " ",
                        strip=True
                    )

                pitchers = hawks_game.select(
                    ".detail-team-pitcher"
                )

                if len(pitchers) >= 2:
                    p1 = pitchers[0].get_text(" ", strip=True)
                    p2 = pitchers[1].get_text(" ", strip=True)

                    if len(teams) >= 2 and "ソフトバンク" in teams[0]:
                        result["hawks_starter"] = p1
                        result["opp_starter"] = p2
                    else:
                        result["hawks_starter"] = p2
                        result["opp_starter"] = p1

                # 表示対象の日付も保存
                result["game_date"] = target_dt.strftime("%Y-%m-%d")
                result["game_date_label"] = target_dt.strftime("%m/%d")
                result["is_today"] = (day_offset == 0)
                result["game_label"] = (
                    "今日の試合"
                    if day_offset == 0
                    else "次の試合"
                )

                found_game = True
                break

            if not found_game:
                # ハンデの森に未来試合がまだ無い場合、
                # NPB公式日程から次戦を取得
                next_game = fetch_next_hawks_game_from_npb()

                if next_game.get("ok"):
                    result["opponent"] = next_game["opponent"]
                    result["stadium"] = next_game["stadium"]
                    result["time"] = next_game["time"]
                    result["game_date"] = next_game["game_date"]
                    result["game_date_label"] = next_game["game_date_label"]
                    result["is_today"] = next_game["is_today"]
                    result["game_label"] = next_game["game_label"]

                    # 予告先発未発表時
                    result["hawks_starter"] = "-"
                    result["opp_starter"] = "-"
                else:
                    result["game_date"] = "-"
                    result["game_date_label"] = "-"
                    result["is_today"] = False
                    result["game_label"] = "次の試合"

        except Exception:
            pass

        # --- ホークス試合結果：直近5試合 ---
        req2 = urllib.request.Request(
            "https://npb.jp/bis/teams/results_h_index.html",
            headers=headers
        )
        html2 = urllib.request.urlopen(req2, timeout=10).read()
        soup2 = BeautifulSoup(html2, "html.parser")
        text2 = soup2.get_text(" ", strip=True)

        outcomes = re.findall(r"\s([○●△])\s", text2)
        if outcomes:
            result["recent5"] = outcomes[-5:]

        result["ok"] = True

    except Exception as e:
        result["error"] = str(e)

    return result



# ===== HAWKS AI v2.2 チーム・投手成績自動取得 =====

def normalize_name(name):
    name = str(name)
    name = name.replace("　", "")
    name = name.replace(" ", "")
    name = name.replace("*", "")
    name = name.replace("^", "")
    name = name.replace("{", "")
    name = name.replace("}", "")
    return name.strip()


@st.cache_data(ttl=900)
def fetch_team_standings():
    result = {}

    try:
        req = urllib.request.Request(
            "https://npb.jp/bis/2026/stats/std_p.html",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        html = urllib.request.urlopen(req, timeout=10).read()
        soup = BeautifulSoup(html, "html.parser")

        aliases = {
            "ソフトバンク": ["福岡ソフトバンク", "ソフトバンク"],
            "楽天": ["東北楽天", "楽天"],
            "西武": ["埼玉西武", "西武"],
            "日本ハム": ["北海道日本ハム", "日本ハム"],
            "オリックス": ["オリックス"],
            "ロッテ": ["千葉ロッテ", "ロッテ"],
        }

        rank = 0

        for tr in soup.find_all("tr"):
            cells = [
                c.get_text(" ", strip=True)
                for c in tr.find_all(["th", "td"])
            ]

            if len(cells) < 6:
                continue

            row = " ".join(cells)

            for key, names in aliases.items():
                if key in result:
                    continue

                if any(name in row for name in names):
                    try:
                        games = int(cells[1])
                        wins = int(cells[2])
                        losses = int(cells[3])
                        draws = int(cells[4])
                        pct = float(cells[5])

                        if games >= 50:
                            rank += 1

                            result[key] = {
                                "rank": rank,
                                "games": games,
                                "wins": wins,
                                "losses": losses,
                                "draws": draws,
                                "pct": pct,
                            }

                    except (ValueError, IndexError):
                        pass

    except Exception:
        pass

    return result



# ===== PITCHER IMAGE AUTO SELECT =====
def get_pitcher_image(pitcher_name, team_key):
    import base64
    import mimetypes
    from pathlib import Path

    def norm(v):
        return (
            str(v or "")
            .replace(" ", "")
            .replace("　", "")
            .replace("\t", "")
            .strip()
        )

    target = norm(pitcher_name)

    team_folder_map = {
        "ソフトバンク": "福岡ソフトバンクホークス",
        "楽天": "東北楽天ゴールデンイーグルス",
        "西武": "埼玉西武ライオンズ",
        "日本ハム": "北海道日本ハムファイターズ",
        "オリックス": "オリックス・バファローズ",
        "ロッテ": "千葉ロッテマリーンズ",
        "巨人": "読売ジャイアンツ",
        "阪神": "阪神タイガース",
        "広島": "広島東洋カープ",
        "DeNA": "横浜DeNAベイスターズ",
        "中日": "中日ドラゴンズ",
        "ヤクルト": "東京ヤクルトスワローズ",
    }

    roots = [
        Path("/app/static/pitchers"),
        Path("/opt/hawks-ai/static/pitchers"),
    ]

    # 球団別 npb_all_players を最優先
    folder_name = team_folder_map.get(str(team_key))

    if folder_name:
        for root in roots:
            team_dir = root / "npb_all_players" / folder_name

            if not team_dir.exists():
                continue

            for candidate in team_dir.rglob("*"):
                if (
                    candidate.is_file()
                    and candidate.suffix.lower() in
                    (".jpg", ".jpeg", ".png", ".webp")
                    and norm(candidate.stem) == target
                ):
                    mime = (
                        mimetypes.guess_type(str(candidate))[0]
                        or "image/jpeg"
                    )
                    encoded = base64.b64encode(
                        candidate.read_bytes()
                    ).decode("ascii")
                    return f"data:{mime};base64,{encoded}"

    # 球団フォルダで見つからない場合のみ全体検索
    for root in roots:
        if not root.exists():
            continue

        for candidate in root.rglob("*"):
            if (
                candidate.is_file()
                and candidate.suffix.lower() in
                (".jpg", ".jpeg", ".png", ".webp")
                and norm(candidate.stem) == target
            ):
                mime = (
                    mimetypes.guess_type(str(candidate))[0]
                    or "image/jpeg"
                )
                encoded = base64.b64encode(
                    candidate.read_bytes()
                ).decode("ascii")
                return f"data:{mime};base64,{encoded}"

    return ""
# ===== END PITCHER IMAGE AUTO SELECT =====


TEAM_PITCHER_CODES = {
    "ソフトバンク": "h",
    "楽天": "e",
    "西武": "l",
    "日本ハム": "f",
    "オリックス": "b",
    "ロッテ": "m",
}


@st.cache_data(ttl=900)
def fetch_pitcher_stats(team_key, pitcher_name):
    result = {
        "ok": False,
        "games": None,
        "wins": None,
        "losses": None,
        "era": None,
        "grade": "標準"
    }

    code = TEAM_PITCHER_CODES.get(team_key)

    if not code or not pitcher_name or pitcher_name == "-":
        return result

    try:
        url = f"https://npb.jp/bis/2026/stats/idp1_{code}.html"

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        html = urllib.request.urlopen(req, timeout=10).read()
        soup = BeautifulSoup(html, "html.parser")

        target = normalize_name(pitcher_name)

        for tr in soup.find_all("tr"):
            cells = [
                c.get_text(" ", strip=True)
                for c in tr.find_all(["th", "td"])
            ]

            if len(cells) < 10:
                continue

            row_name = normalize_name(cells[0])

            if target not in row_name and row_name not in target:
                continue

            # NPB投手成績表の列を直接読む
            # 0=選手名 1=登板 2=勝 3=敗 ... 最終列=防御率
            try:
                result["games"] = int(cells[1])
                result["wins"] = int(cells[2])
                result["losses"] = int(cells[3])
                result["era"] = float(cells[-1])
            except (ValueError, IndexError):
                continue

            era = result["era"]

            if era is not None:
                if era <= 2.25:
                    result["grade"] = "エース"
                elif era <= 3.50:
                    result["grade"] = "好投手"
                elif era <= 4.50:
                    result["grade"] = "標準"
                else:
                    result["grade"] = "不調"

            result["ok"] = True
            break

    except Exception:
        pass

    return result



# ===== HAWKS AI v2.3 LIVE =====
@st.cache_data(ttl=15)
def fetch_hawks_live_status():
    now_jst = datetime.now(ZoneInfo("Asia/Tokyo"))

    year = now_jst.year
    mm = now_jst.strftime("%m")
    mmdd = now_jst.strftime("%m%d")
    date_iso = now_jst.strftime("%Y-%m-%d")

    result = {
        "ok": False,
        "status": "取得中",

        "url": None,
        "play_url": None,
        "game_id": None,
        "date": date_iso,

        "hawks_score": None,
        "opp_score": None,

        "inning": None,
        "half": None,
        "attack_side": None,

        "outs": None,
        "base1": None,
        "base2": None,
        "base3": None,

        "live_context_ready": False,
        "last_batter": None,
        "last_count": None,
        "last_result": None,
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        # =====================================================
        # 今日の試合URLを月間日程から自動取得
        # =====================================================
        schedule_url = (
            f"https://npb.jp/games/{year}/"
            f"schedule_{mm}_detail.html"
        )

        req = urllib.request.Request(
            schedule_url,
            headers=headers
        )

        html = urllib.request.urlopen(
            req,
            timeout=8
        ).read()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        score_url = None

        for a in soup.find_all("a", href=True):
            href = a.get("href", "")

            if f"/scores/{year}/{mmdd}/" not in href:
                continue

            # リンク直近のtdでは球団名が取れないため
            # 試合カード全体のtrを優先して取得する
            parent = a.find_parent("tr")

            if parent is None:
                parent = a.find_parent(
                    ["li", "div"]
                )

            context = (
                parent.get_text(" ", strip=True)
                if parent
                else a.get_text(" ", strip=True)
            )

            # NPB日程ページでは球団名がリンク周辺に無い場合がある。
            # URL内の球団コード h（ソフトバンク）で判定する。
            game_path = href.strip("/").split("/")

            game_code = (
                game_path[-1]
                if game_path
                else ""
            )

            teams = game_code.split("-")

            is_hawks_game = (
                "h" in teams
            )

            if (
                is_hawks_game
                or "ソフトバンク" in context
                or "福岡ソフトバンク" in context
            ):
                score_url = urljoin(
                    schedule_url,
                    href
                )

                if not score_url.endswith("box.html"):
                    score_url = (
                        score_url.rstrip("/")
                        + "/box.html"
                    )

                break

        # 開始前は速報リンクがまだ無いことがある
        if not score_url:
            result["status"] = "試合開始前"
            result["ok"] = True
            return result

        result["url"] = score_url

        result["play_url"] = score_url.replace(
            "/box.html",
            "/playbyplay.html"
        )

        result["game_id"] = (
            score_url
            .split("/scores/")[-1]
            .replace("/box.html", "")
            .strip("/")
        )

        # =====================================================
        # BOX SCORE
        # =====================================================
        req = urllib.request.Request(
            score_url,
            headers=headers
        )

        html = urllib.request.urlopen(
            req,
            timeout=8
        ).read()

        box_soup = BeautifulSoup(
            html,
            "html.parser"
        )

        text = box_soup.get_text(
            " ",
            strip=True
        )

        if "試合終了" in text:
            result["status"] = "試合終了"

        elif "試合開始前" in text:
            result["status"] = "試合開始前"

        else:
            result["status"] = "試合中"

        # =====================================================
        # スコア表
        # =====================================================
        score_table = None

        for table in box_soup.find_all("table"):
            table_text = table.get_text(
                " ",
                strip=True
            )

            if "ソフトバンク" in table_text:
                score_table = table
                break

        if score_table is not None:

            rows = score_table.find_all("tr")

            if len(rows) >= 3:

                row1 = [
                    c.get_text(" ", strip=True)
                    for c in rows[1].find_all(
                        ["th", "td"]
                    )
                ]

                row2 = [
                    c.get_text(" ", strip=True)
                    for c in rows[2].find_all(
                        ["th", "td"]
                    )
                ]

                if (
                    row1
                    and "ソフトバンク" in row1[0]
                ):
                    hawks_cells = row1
                    opp_cells = row2
                else:
                    hawks_cells = row2
                    opp_cells = row1

                # 0=球団名
                # 1～9=イニング
                # 10=計
                if (
                    len(hawks_cells) >= 11
                    and len(opp_cells) >= 11
                ):

                    try:
                        if hawks_cells[10] != "":
                            result["hawks_score"] = int(
                                hawks_cells[10]
                            )
                    except Exception:
                        pass

                    try:
                        if opp_cells[10] != "":
                            result["opp_score"] = int(
                                opp_cells[10]
                            )
                    except Exception:
                        pass

        # =====================================================
        # PLAY BY PLAY
        #
        # 回 / 表裏 / 攻撃側
        # アウト / 塁上
        # =====================================================
        if result["status"] in (
            "試合中",
            "試合終了"
        ):

            req = urllib.request.Request(
                result["play_url"],
                headers=headers
            )

            play_html = urllib.request.urlopen(
                req,
                timeout=8
            ).read()

            play_soup = BeautifulSoup(
                play_html,
                "html.parser"
            )

            inning_pattern = re.compile(
                r"(\d+)回(表|裏)"
                r"（([^）]+)の攻撃）"
            )

            inning_headers = []

            for tag in play_soup.find_all(
                ["h3", "h4", "h5", "h6"]
            ):
                heading_text = tag.get_text(
                    " ",
                    strip=True
                )

                m = inning_pattern.search(
                    heading_text
                )

                if m:
                    inning_headers.append(
                        (tag, m)
                    )

            if inning_headers:

                current_heading, m = (
                    inning_headers[-1]
                )

                current_inning = int(
                    m.group(1)
                )

                current_half = m.group(2)
                attacking_team = m.group(3)

                result["inning"] = (
                    current_inning
                )

                result["half"] = (
                    current_half
                )

                if "ソフトバンク" in attacking_team:
                    result["attack_side"] = (
                        "ホークス攻撃中"
                    )
                else:
                    result["attack_side"] = (
                        "相手攻撃中"
                    )

                # =============================================
                # 現在イニングの打席行を取得
                # =============================================
                play_rows = []

                cursor = current_heading.find_next()

                while cursor is not None:

                    # 次のイニング見出しに到達したら終了
                    if cursor.name in (
                        "h3",
                        "h4",
                        "h5",
                        "h6"
                    ):
                        cursor_text = cursor.get_text(
                            " ",
                            strip=True
                        )

                        if inning_pattern.search(
                            cursor_text
                        ):
                            break

                    if cursor.name == "tr":

                        cells = [
                            c.get_text(
                                " ",
                                strip=True
                            )
                            for c in cursor.find_all(
                                ["th", "td"]
                            )
                        ]

                        if (
                            len(cells) >= 5
                            and re.match(
                                r"^[0-2]アウト$",
                                cells[0]
                            )
                        ):
                            play_rows.append(
                                cells
                            )

                    cursor = cursor.find_next()

                # =============================================
                # LIVE中の現在打席行
                #
                # 結果欄が空の行があれば、
                # その行のアウト・走者を現在状態として採用
                # =============================================
                current_row = None

                for cells in reversed(play_rows):

                    result_text = (
                        cells[4].strip()
                        if len(cells) > 4
                        else ""
                    )

                    batter_text = (
                        cells[2].strip()
                        if len(cells) > 2
                        else ""
                    )

                    # 現在打席とみなせる行
                    if (
                        batter_text
                        and result_text == ""
                    ):
                        current_row = cells
                        break

                if current_row is not None:

                    outs_text = current_row[0]
                    bases_text = current_row[1]

                    out_match = re.search(
                        r"([0-2])アウト",
                        outs_text
                    )

                    if out_match:
                        result["outs"] = int(
                            out_match.group(1)
                        )

                    # ランナー
                    if "満塁" in bases_text:
                        result["base1"] = True
                        result["base2"] = True
                        result["base3"] = True

                    else:
                        result["base1"] = (
                            "1塁" in bases_text
                        )

                        result["base2"] = (
                            "2塁" in bases_text
                        )

                        result["base3"] = (
                            "3塁" in bases_text
                        )

                    result["last_batter"] = (
                        current_row[2]
                    )

                    result["last_count"] = (
                        current_row[3]
                    )

                    result["last_result"] = (
                        current_row[4]
                    )

                    result[
                        "live_context_ready"
                    ] = True

        result["ok"] = True

    except Exception as e:

        result["status"] = "取得失敗"
        result["error"] = str(e)

    return result


npb = fetch_hawks_npb_data()

# ===== PREMIUM HANDICAP FROM HANDENOMORI =====
# 試合カード/ハンデデータが無い場合は None → 「－」表示
premium_hawks_handicap = npb.get("hawks_handicap")
premium_opp_handicap = npb.get("opp_handicap")

# ===== NPB OFFICIAL ANNOUNCED STARTERS =====
_announced = fetch_hawks_announced_starters(
    npb.get("opponent", "-"),
    npb.get("stadium", "-"),
    npb.get("time", "-"),
)

if _announced.get("ok"):
    _ann_hawks = str(
        _announced.get("hawks_starter", "-")
    ).strip()

    _ann_opp = str(
        _announced.get("opp_starter", "-")
    ).strip()

    # NPB公式で実際の投手名が取れた場合のみ上書き。
    # 未発表時はハンデの森等ですでに取得した値を残す。
    if _ann_hawks not in ("", "-", "None"):
        npb["hawks_starter"] = _ann_hawks

    if _ann_opp not in ("", "-", "None"):
        npb["opp_starter"] = _ann_opp

standings = fetch_team_standings()

hawks_team_stats = standings.get("ソフトバンク", {})

opp_key = "楽天"
opp_text_v22 = str(npb.get("opponent", ""))

for k in ["楽天", "西武", "日本ハム", "オリックス", "ロッテ"]:
    if k in opp_text_v22:
        opp_key = k
        break

opponent_team_stats = standings.get(opp_key, {})

# ===== PREMIUM SCOREBOARD TEAM DATA =====
_premium_team_full_names = {
    "日本ハム": "北海道日本ハムファイターズ",
    "楽天": "東北楽天ゴールデンイーグルス",
    "西武": "埼玉西武ライオンズ",
    "オリックス": "オリックス・バファローズ",
    "ロッテ": "千葉ロッテマリーンズ",
}

_premium_opp_full_name = _premium_team_full_names.get(
    opp_key,
    str(npb.get("opponent", opp_key))
)

_premium_opp_rank = opponent_team_stats.get("rank", "-")
_premium_hawks_rank = hawks_team_stats.get("rank", "-")

_premium_opp_wins = opponent_team_stats.get("wins", "-")
_premium_opp_losses = opponent_team_stats.get("losses", "-")
_premium_opp_draws = opponent_team_stats.get("draws", "-")

_premium_hawks_wins = hawks_team_stats.get("wins", "-")
_premium_hawks_losses = hawks_team_stats.get("losses", "-")
_premium_hawks_draws = hawks_team_stats.get("draws", "-")

hawks_pitcher_stats = fetch_pitcher_stats(
    "ソフトバンク",
    npb.get("hawks_starter", "-")
)

opp_pitcher_stats = fetch_pitcher_stats(
    opp_key,
    npb.get("opp_starter", "-")
)



# ===== HAWKS AI V8 FINAL CARD =====
try:
    v8_context_path = Path("/app/data/hawks_games_context.json")

    if v8_context_path.exists():
        with v8_context_path.open(encoding="utf-8") as f:
            v8_games = json.load(f)

        v8_games = sorted(v8_games, key=lambda x: x["date"])

        if v8_games and npb.get("opponent"):
            v8_opponent = npb.get("opponent", "-")
            v8_hawks_starter = npb.get("hawks_starter", "-")
            v8_opp_starter = npb.get("opp_starter", "-")

            h5_rows = [
                g for g in v8_games
                if g.get("date", "") < datetime.now().strftime("%Y-%m-%d")
            ][-5:]

            h5_wins = sum(g.get("result") == "win" for g in h5_rows)
            h5_decided = sum(g.get("result") in {"win", "loss"} for g in h5_rows)
            h5_pct = (h5_wins / h5_decided) if h5_decided else 0.5
            h5_rd = (
                sum(g.get("run_diff", 0) for g in h5_rows) / len(h5_rows)
                if h5_rows else 0
            )

            opp_rows = [
                g for g in v8_games
                if g.get("opponent") == v8_opponent
                and g.get("date", "") < datetime.now().strftime("%Y-%m-%d")
            ][-5:]

            opp_wins = sum(g.get("result") == "loss" for g in opp_rows)
            opp_decided = sum(g.get("result") in {"win", "loss"} for g in opp_rows)
            opp_pct = (opp_wins / opp_decided) if opp_decided else 0.5
            opp_rd = (
                -sum(g.get("run_diff", 0) for g in opp_rows) / len(opp_rows)
                if opp_rows else 0
            )

            hs_hist = [
                g for g in v8_games
                if g.get("hawks_starter") == v8_hawks_starter
                and g.get("date", "") < datetime.now().strftime("%Y-%m-%d")
                and g.get("result") in {"win", "loss"}
            ]

            os_hist = [
                g for g in v8_games
                if g.get("opponent") == v8_opponent
                and g.get("opponent_starter") == v8_opp_starter
                and g.get("date", "") < datetime.now().strftime("%Y-%m-%d")
                and g.get("result") in {"win", "loss"}
            ]

            hs_win = (
                sum(g.get("result") == "win" for g in hs_hist) / len(hs_hist)
                if hs_hist else 0.5
            )

            os_hawks_win = (
                sum(g.get("result") == "win" for g in os_hist) / len(os_hist)
                if os_hist else 0.5
            )

            hs_rd = (
                sum(g.get("run_diff", 0) for g in hs_hist) / len(hs_hist)
                if hs_hist else 0
            )

            os_rd = (
                sum(g.get("run_diff", 0) for g in os_hist) / len(os_hist)
                if os_hist else 0
            )

            opp_starter_strength = 1.0 - os_hawks_win
            starter_adv = hs_win - os_hawks_win
            starter_rd_adv = hs_rd - os_rd
            rd5 = h5_rd - opp_rd

            v8_home_away = "home" if npb.get("stadium", "") in [
                "PayPayドーム", "みずほPayPayドーム", "北九州"
            ] else "away"

            p1 = (
                v8_home_away == "away"
                and opp_starter_strength >= 0.60
                and starter_rd_adv < 0
            )

            p2 = (
                v8_home_away == "away"
                and starter_rd_adv < 0
            )

            p3 = (
                opp_starter_strength >= 0.60
                and rd5 < 0
            )

            p7 = (
                starter_adv <= -0.20
                and rd5 < 0
            )

            probability = 0.634
            risk = "通常"
            icon = "🟢"
            patterns = []

            if p1:
                patterns.append("P1")
            if p2:
                patterns.append("P2")
            if p3:
                patterns.append("P3")
            if p7:
                patterns.append("P7")

            if p3:
                probability = 0.42
                risk = "危険"
                icon = "🔴"
            elif p1 or p7:
                probability = 0.50
                risk = "注意"
                icon = "🟡"
            elif p2:
                probability = 0.56
                risk = "注意"
                icon = "🟡"

            # =============================================
            # 試合前V8予測を固定保存
            # =============================================
            pregame_probability = save_pregame_prediction(
                datetime.now(
                    ZoneInfo("Asia/Tokyo")
                ).strftime("%Y-%m-%d"),
                v8_opponent,
                probability * 100.0,
                "V8 FINAL",
            )

            # 保存済み試合前予測を正式値として表示
            probability = (
                pregame_probability / 100.0
            )

            # =============================================
            # V8 FINAL 正式予測値
            # 画面表示は上部プレミアムカード1か所に統一
            # =============================================
            v8_final_probability = probability

            # risk / patterns / icon 等は内部判定用として保持


except Exception as e:
    st.caption(f"V8 FINAL表示準備中: {e}")



# =========================================================
# TODAY / TOMORROW 2 COLUMN DASHBOARD
# =========================================================
# 今日の試合は常に横幅100%
# =========================================================
# TODAY DASHBOARD REMOVED
# 今日の試合情報は上部プレミアムカードへ統合
# =========================================================

tomorrow_col = st.container()

with tomorrow_col:
    # =====================================================
    # 🔮 明日の HAWKS AI V8 予想
    # =====================================================
    try:
        tomorrow = (
            datetime.now(ZoneInfo("Asia/Tokyo"))
            .date()
            + timedelta(days=1)
        )

        tomorrow_iso = tomorrow.strftime("%Y-%m-%d")
        tomorrow_ymd = tomorrow.strftime("%Y%m%d")

        url = (
            f"https://handenomori.com/jpb/"
            f"{tomorrow_ymd}/"
        )

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        html = urllib.request.urlopen(
            req,
            timeout=10
        ).read()

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        game = None

        for card in soup.select(".game-detail2"):

            teams = [
                x.get_text(" ", strip=True)
                for x in card.select(".detail-card-team")
            ]

            if "ソフトバンク" not in teams:
                continue

            info = card.select_one(
                ".detail-single-studium-time"
            )

            info_spans = (
                info.find_all("span")
                if info else []
            )

            pitchers = [
                x.get_text(" ", strip=True)
                for x in card.select(
                    ".detail-team-pitcher"
                )
            ]

            if teams[0] == "ソフトバンク":
                opponent = teams[1]
                hawks_starter = (
                    pitchers[0]
                    if len(pitchers) >= 1
                    else "-"
                )
                opp_starter = (
                    pitchers[1]
                    if len(pitchers) >= 2
                    else "-"
                )
                home_away = "home"
            else:
                opponent = teams[0]
                hawks_starter = (
                    pitchers[1]
                    if len(pitchers) >= 2
                    else "-"
                )
                opp_starter = (
                    pitchers[0]
                    if len(pitchers) >= 1
                    else "-"
                )
                home_away = "away"

            game = {
                "opponent": opponent,
                "time": (
                    info_spans[0].get_text(strip=True)
                    if len(info_spans) >= 1
                    else "-"
                ),
                "stadium": (
                    info_spans[1].get_text(strip=True)
                    if len(info_spans) >= 2
                    else "-"
                ),
                "hawks_starter": hawks_starter,
                "opp_starter": opp_starter,
                "home_away": home_away,
            }

            break

        st.markdown(
            '<div class="section-head section-purple">'
            '🔮 明日の HAWKS AI V8 予想'
            '</div>',
            unsafe_allow_html=True
        )

        if game is None:
            st.info(
                f"{tomorrow_iso} のホークス戦は"
                "まだ取得できていません。"
            )

        else:
            # 現行V8ルールを流用
            probability = 0.634
            risk = "通常"
            icon = "🟢"
            patterns = []

            tc1, tc2, tc3, tc4 = st.columns(4)

            tc1.metric(
                "対戦相手",
                game["opponent"]
            )

            tc2.metric(
                "球場",
                game["stadium"]
            )

            tc3.metric(
                "開始",
                game["time"]
            )

            tc4.metric(
                "勝利期待度",
                f"{probability:.1%}"
            )

            pc1, pc2 = st.columns(2)

            with pc1:
                st.info(
                    f'🦅 ホークス先発：'
                    f'{game["hawks_starter"]}'
                )

            with pc2:
                st.info(
                    f'⚾ 相手先発：'
                    f'{game["opp_starter"]}'
                )

            st.caption(
                f'{icon} リスク判定：{risk}'
                f' ｜ 危険パターン：'
                f'{"・".join(patterns) if patterns else "該当なし"}'
            )

    except Exception as e:
        print("TOMORROW PREDICTION WAIT:", e)

st.divider()


st.caption("戦況・勝利の方程式・キーマン・相性・勢い・風向き・WPA期待値をリアルタイム全自動分析")

# --- 1. アプリ起動時の自動データ取得ロジック ---
@st.cache_data(ttl=1800)
def auto_fetch_npb():
    info = {"status": False, "msg": "手動設定モード"}
    try:
        url = "https://npb.jp/announcement/starter/"
        req = urllib.request.Request(
            url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        html = urllib.request.urlopen(req, timeout=3).read().decode('utf-8')
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text()

        if "ソフトバンク" in text or "PayPay" in text or "福岡" in text:
            info = {"status": True, "msg": "本日/明日の予告先発・試合情報を自動取得・適用完了"}
    except Exception:
        pass
    return info

auto_data = auto_fetch_npb()

if auto_data["status"]:
    st.toast(f"✅ {auto_data['msg']}", icon="⚾")
else:
    st.caption("ℹ️ NPB公式自動同期動作中（数値・条件を変更すると下部に自動反映されます）")

st.divider()

# --- 2. 試合状況・詳細補正設定 ---

# =========================================================
# NPB自動取得値をアプリ内部の基本値へ反映
# =========================================================

# 対戦相手
opp_text = str(npb.get("opponent", ""))

if "楽天" in opp_text:
    opponent = "楽天"
elif "オリックス" in opp_text:
    opponent = "オリックス"
elif "ロッテ" in opp_text:
    opponent = "ロッテ"
elif "西武" in opp_text:
    opponent = "西武"
elif "日本ハム" in opp_text:
    opponent = "日本ハム"
else:
    opponent = "セ・リーグ球団"

# 開催地
stadium_text = str(npb.get("stadium", ""))

if "みずほ" in stadium_text or "PayPay" in stadium_text:
    venue = "みずほPayPayドーム (ホーム)"
else:
    venue = "相手本拠地 (ビジター)"

# シーズン勝数
try:
    wins_sb_auto = int(npb.get("wins", 0))
except Exception:
    wins_sb_auto = 0

# 直近成績 → 表示用状態
recent5_auto = npb.get("recent5", [])

if recent5_auto:
    recent_wins_auto = recent5_auto.count("○")

    if recent_wins_auto >= 4:
        st_momentum_auto = "絶好調 (3連勝以上/勝ち越し中)"
    elif recent_wins_auto >= 3:
        st_momentum_auto = "勢いあり (直近勝ち越し)"
    elif recent_wins_auto == 2:
        st_momentum_auto = "通常 (五分)"
    elif recent_wins_auto == 1:
        st_momentum_auto = "やや不振 (直近負け越し)"
    else:
        st_momentum_auto = "スランプ (3連敗以上)"
else:
    st_momentum_auto = "通常 (五分)"


# =========================================================
# 試合中に頻繁に操作する項目だけ上位表示
# =========================================================
live = fetch_hawks_live_status()

# ===== HAWKS AI LIVE 自動更新 =====
# 試合中のみ15秒ごとに自動再実行
if live.get("status") == "試合中":
    import time
    time.sleep(15)
    st.rerun()


# =========================================================
# HAWKS AI PREMIUM LIVE STATUS
_live_status = str(live.get("status", "取得中"))
if _live_status == "試合中":
    _live_badge, _live_class = "● LIVE", "is-live"
elif _live_status == "試合終了":
    _live_badge, _live_class = "試合終了", "is-finished"
else:
    _live_badge, _live_class = "試合開始前", "is-waiting"

st.markdown(
    f"""
    <div class="hawks-live-strip">
      <div class="hawks-live-left">
        <span class="hawks-live-dot"></span>
        <span class="hawks-live-title">⚾ NPB公式速報：{_live_status}</span>
      </div>
      <div class="hawks-live-right">
        <span class="hawks-live-badge {_live_class}">{_live_badge}</span>
        <span class="hawks-live-refresh">自動確認 15秒キャッシュ</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True
)

# HAWKS AI v2.4 LIVE自動反映
# =========================================================

live_score_ready = (
    live.get("status") in ("試合中", "試合終了")
    and live.get("hawks_score") is not None
    and live.get("opp_score") is not None
)


# =========================================================
# HAWKS AI PREMIUM SCOREBOARD
if live_score_ready:
    hawks_score = int(live["hawks_score"])
    opponent_score = int(live["opp_score"])
else:
    score_c1, score_c2 = st.columns(2)
    with score_c1:
        hawks_score = st.number_input("🦅 ホークス得点", min_value=0, max_value=99, value=0, step=1, key="hawks_score")
    with score_c2:
        opponent_score = st.number_input("⚾ 相手得点", min_value=0, max_value=99, value=0, step=1, key="opponent_score")

score_diff = hawks_score - opponent_score
if score_diff > 0:
    score_status, score_status_class, score_icon = f"{score_diff}点リード", "hawks-leading", "🦅"
elif score_diff < 0:
    score_status, score_status_class, score_icon = f"{abs(score_diff)}点ビハインド", "hawks-behind", "🔥"
else:
    score_status, score_status_class, score_icon = "同点", "hawks-tied", "⚾"

# =========================================================
# HERO直下：PC / スマホ共通プレミアム統合速報
_premium_prob_raw = float(
    globals().get(
        "v8_final_probability",
        globals().get("probability", 0.634)
    )
)
_premium_prob = _premium_prob_raw * 100.0 if _premium_prob_raw <= 1.0 else _premium_prob_raw
_premium_prob = max(0.0, min(100.0, _premium_prob))
_premium_opponent = str(npb.get("opponent", "対戦相手"))

def _npb_logo_slug(team_name):
    name = str(team_name)
    logo_names = (
        (("阪神", "タイガース"), "hanshin"),
        (("巨人", "読売", "ジャイアンツ"), "giants"),
        (("中日", "ドラゴンズ"), "dragons"),
        (("広島", "カープ"), "carp"),
        (("DeNA", "ＤｅＮＡ", "横浜", "ベイスターズ"), "baystars"),
        (("ヤクルト", "スワローズ"), "swallows"),
        (("ソフトバンク", "ホークス"), "hawks"),
        (("ロッテ", "マリーンズ"), "marines"),
        (("楽天", "イーグルス"), "eagles"),
        (("日本ハム", "ファイターズ"), "fighters"),
        (("西武", "ライオンズ"), "lions"),
        (("オリックス", "バファローズ"), "buffaloes"),
    )
    for aliases, slug in logo_names:
        if any(alias in name for alias in aliases):
            return slug
    return "generic"

_TEAM_BADGE_STYLES = {
    "hanshin": ("#FFE100", "#111111", "#D4B900", "阪神"),
    "giants": ("#F15A24", "#FFFFFF", "#C94717", "巨人"),
    "dragons": ("#003E8F", "#FFFFFF", "#002B66", "中日"),
    "carp": ("#E60012", "#FFFFFF", "#B8000E", "広島"),
    "baystars": ("#0075C2", "#FFFFFF", "#005B98", "DeNA"),
    "swallows": ("#003087", "#FFFFFF", "#002261", "ヤクルト"),
    "hawks": ("#F5C400", "#111111", "#C9A000", "ソフトバンク"),
    "marines": ("#111827", "#FFFFFF", "#000000", "ロッテ"),
    "eagles": ("#870010", "#FFFFFF", "#65000C", "楽天"),
    "fighters": ("#006298", "#FFFFFF", "#004A73", "日本ハム"),
    "lions": ("#143D8D", "#FFFFFF", "#0E2C67", "西武"),
    "buffaloes": ("#7A0019", "#FFFFFF", "#560012", "オリックス"),
    "generic": ("#64748B", "#FFFFFF", "#475569", "球団"),
}


def _team_text_badge(team_name, slug=None, badge_class="npb-result-logo"):
    team_slug = slug or _npb_logo_slug(team_name)
    background, color, border, label = _TEAM_BADGE_STYLES.get(
        team_slug,
        _TEAM_BADGE_STYLES["generic"],
    )
    if team_slug == "generic":
        label = str(team_name)
    return (
        f'<div class="{badge_class} team-text-badge" '
        f'role="img" aria-label="{team_name}" '
        f'style="display:flex!important;align-items:center!important;'
        f'justify-content:center!important;text-align:center!important;'
        f'box-sizing:border-box!important;padding:6px!important;'
        f'border:2px solid {border}!important;border-radius:14px!important;'
        f'background:{background}!important;color:{color}!important;'
        f'font-size:clamp(.58rem,1vw,.82rem)!important;'
        f'font-weight:950!important;line-height:1.15!important;">'
        f'{label}</div>'
    )


_premium_opp_logo = _npb_logo_slug(_premium_opponent)

# Lightweight team-name badges replace logo image requests.
_premium_opp_badge = _team_text_badge(
    _premium_opponent,
    _premium_opp_logo,
    "hawks-premium-team-logo",
)
_premium_hawks_badge = _team_text_badge(
    "福岡ソフトバンクホークス",
    "hawks",
    "hawks-premium-team-logo",
)

_premium_stadium = str(npb.get("stadium", "-"))
_premium_time = str(npb.get("time", "-"))
_premium_hawks_starter = str(npb.get("hawks_starter", "-"))
_premium_opp_starter = str(npb.get("opp_starter", "-"))

# ===== PREMIUM STARTER PHOTOS =====
_premium_hawks_pitcher_image = get_pitcher_image(
    _premium_hawks_starter,
    "ソフトバンク"
)

_premium_opp_pitcher_image = get_pitcher_image(
    _premium_opp_starter,
    npb.get("opponent", "-")
)

_premium_hawks_pitcher_img = (
    f'<img class="hawks-premium-pitcher-photo" '
    f'src="{_premium_hawks_pitcher_image}" '
    f'alt="{_premium_hawks_starter}">'
    if _premium_hawks_pitcher_image
    else '<div class="hawks-premium-pitcher-fallback">⚾</div>'
)

_premium_opp_pitcher_img = (
    f'<img class="hawks-premium-pitcher-photo" '
    f'src="{_premium_opp_pitcher_image}" '
    f'alt="{_premium_opp_starter}">'
    if _premium_opp_pitcher_image
    else '<div class="hawks-premium-pitcher-fallback">⚾</div>'
)
_premium_date = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%Y.%m.%d（%a）")
_premium_now = datetime.now(ZoneInfo("Asia/Tokyo")).strftime("%H:%M")
_premium_status = str(live.get("status", "試合開始前"))
if _premium_status == "試合終了":
    _premium_status_label = "試合終了"
elif _premium_status == "試合中":
    _inning = live.get("inning")
    _half = str(live.get("half", ""))
    _premium_status_label = f"{_inning}回{_half}" if _inning else "LIVE"
else:
    _premium_status_label = "試合開始前"

if score_diff > 0:
    _premium_result = f"{score_diff}点リード"
elif score_diff < 0:
    _premium_result = f"{abs(score_diff)}点ビハインド"
else:
    _premium_result = "同点"

_recent = npb.get("recent5", []) or []
_recent_wins = _recent.count("○") if isinstance(_recent, list) else 0
_recent_losses = _recent.count("●") if isinstance(_recent, list) else 0
_recent_text = f"ホークス {_recent_wins}勝 {_recent_losses}敗" if _recent else "データ取得中"

import textwrap

premium_top_slot.markdown(
    textwrap.dedent(f"""
    <div class="hawks-premium-shell">
      <div class="hawks-premium-news">
        <span class="dot"></span><span class="source">NPB公式速報</span>
        <span>{_premium_date}</span><span class="premium-stadium-top">{_premium_stadium}</span>
        <span class="auto">↻ 自動更新（15秒）</span>
      </div>
      <div class="hawks-premium-card">
        <div class="hawks-premium-score">
          <div class="hawks-premium-team">
            <div class="hawks-premium-team-visual">
              {_premium_opp_badge}
              <div class="hawks-premium-handicap-box {'is-active' if (premium_opp_handicap or 0) > 0 else 'is-zero'}">
                <small>ハンデの森</small>
                <strong>{format_premium_handicap(premium_opp_handicap) + ("点" if premium_opp_handicap is not None else "")}</strong>
              </div>
            </div>

            <div class="hawks-premium-team-info">
              <div class="hawks-premium-team-name">{_premium_opponent}</div>
              <div class="hawks-premium-team-sub">{_premium_opp_full_name}</div>
              <div class="hawks-premium-team-meta">パ・リーグ　{_premium_opp_rank}位</div>
              <div class="hawks-premium-team-record">今季成績<br>{_premium_opp_wins}勝{_premium_opp_losses}敗{_premium_opp_draws}分</div>
            </div>
          </div>

          <div class="hawks-premium-scoreline">
            <div class="numbers">{opponent_score} − <span class="hawks-num">{hawks_score}</span></div>
            {f'<span class="hawks-premium-status">{_premium_status_label}</span>' if _premium_status_label != "試合開始前" else ""}
            <div class="hawks-premium-venue">{_premium_stadium}</div>
            <div class="hawks-premium-time">{_premium_time} 開始予定</div>
          </div>

          <div class="hawks-premium-team right">
            <div class="hawks-premium-team-info">
              <div class="hawks-premium-team-name">ソフトバンク</div>
              <div class="hawks-premium-team-sub">福岡ソフトバンクホークス</div>
              <div class="hawks-premium-team-meta">パ・リーグ　{_premium_hawks_rank}位</div>
              <div class="hawks-premium-team-record">今季成績<br>{_premium_hawks_wins}勝{_premium_hawks_losses}敗{_premium_hawks_draws}分</div>
            </div>

            <div class="hawks-premium-team-visual">
              {_premium_hawks_badge}
              <div class="hawks-premium-handicap-box right {'is-active' if (premium_hawks_handicap or 0) > 0 else 'is-zero'}">
                <small>ハンデの森</small>
                <strong>{format_premium_handicap(premium_hawks_handicap) + ("点" if premium_hawks_handicap is not None else "")}</strong>
              </div>
            </div>
          </div>
        </div>
        {"" if _premium_status_label == "試合開始前" else f'<div class="hawks-premium-result"><span class="diff">{_premium_result}</span><span>{_premium_status_label}</span></div>'}
        <div class="hawks-premium-ai">
          <div class="hawks-premium-bot">🤖</div>
          <div><div class="hawks-premium-ai-label">HAWKS AI 勝率予測</div><div class="hawks-premium-prob">{_premium_prob:.1f}%</div><small>ホークス勝利の可能性</small></div>
          <div class="hawks-premium-track"><span style="width:{_premium_prob:.1f}%"></span></div>
          <div class="hawks-premium-confidence">信頼度<b>{'高' if _premium_prob >= 50 else '中'}</b></div>
        </div>
        <div class="hawks-premium-detail-title">☷　詳細情報</div>
        <div class="hawks-premium-details premium-details-three">
          <div class="hawks-premium-detail">
            <small>対戦成績（直近5試合）</small>
            <b class="green">{_recent_text}</b>
          </div>

          <div class="hawks-premium-detail">
            <small>{'今日の球場' if npb.get('is_today') else '次の試合会場'}</small>
            <b>{_premium_stadium}</b>
          </div>

          <div class="hawks-premium-detail">
            <small>開始時間</small>
            <b>{_premium_time}</b>
          </div>
        </div>

        <div class="hawks-premium-starters">

          <div class="hawks-premium-starter-card opponent">
            <div class="hawks-premium-pitcher-photo-wrap">
              {_premium_opp_pitcher_img}
            </div>

            <div class="hawks-premium-starter-info">
              <div class="hawks-premium-starter-label">
                {_premium_opponent} 予告先発
              </div>
              <div class="hawks-premium-starter-name">
                {_premium_opp_starter}
              </div>
              <div class="hawks-premium-starter-meta">
                {opp_pitcher_stats.get("wins") if opp_pitcher_stats.get("wins") is not None else "－"}勝
                {opp_pitcher_stats.get("losses") if opp_pitcher_stats.get("losses") is not None else "－"}敗
                <span>｜</span>
                防御率 {opp_pitcher_stats.get("era") if opp_pitcher_stats.get("era") is not None else "－"}
              </div>
            </div>
          </div>

          <div class="hawks-premium-starter-vs">VS</div>

          <div class="hawks-premium-starter-card hawks">
            <div class="hawks-premium-pitcher-photo-wrap">
              {_premium_hawks_pitcher_img}
            </div>

            <div class="hawks-premium-starter-info">
              <div class="hawks-premium-starter-label">
                ソフトバンク 予告先発
              </div>
              <div class="hawks-premium-starter-name">
                {_premium_hawks_starter}
              </div>
              <div class="hawks-premium-starter-meta">
                {hawks_pitcher_stats.get("wins") if hawks_pitcher_stats.get("wins") is not None else "－"}勝
                {hawks_pitcher_stats.get("losses") if hawks_pitcher_stats.get("losses") is not None else "－"}敗
                <span>｜</span>
                防御率 {hawks_pitcher_stats.get("era") if hawks_pitcher_stats.get("era") is not None else "－"}
              </div>
            </div>
          </div>

        </div>

        <div class="hawks-live-under-pitchers">
          <div class="hawks-live-inning">
            {_premium_status_label}
          </div>
          <div class="hawks-live-batting">
            {'🟡 HAWKS 攻撃中' if str(live.get("batting_team", "")) in ("ソフトバンク", "ホークス", "HAWKS") else ''}
          </div>
        </div>

      </div>
      <div class="hawks-premium-foot"><span>※ データは5〜15分間隔で自動更新されています</span><span>最終更新：{_premium_now}</span></div>
    </div>
    """).replace("\n", ""),
    unsafe_allow_html=True,
)


# ============================================================
# TODAY NPB RESULTS
# ============================================================
try:
    _npb_today_path = Path("/app/data/npb_today.json")

    if _npb_today_path.exists():
        _npb_today_data = json.loads(
            _npb_today_path.read_text(encoding="utf-8")
        )

        _npb_today_games = _npb_today_data.get("games", []) or []

        # ホークス戦は上の大型カードに表示済みなので除外
        _npb_other_games = [
            g for g in _npb_today_games
            if "ソフトバンク" not in (
                str(g.get("home", "")),
                str(g.get("away", ""))
            )
        ]

        if _npb_other_games:

            # CSSだけ先に描画
            st.markdown("""
<style>
.npb-results-section{
    margin:18px 0 22px;
}

.npb-results-title{
    font-size:1.08rem;
    font-weight:950;
    color:#0b1726;
    margin:0 0 12px;
    display:flex;
    align-items:center;
    gap:8px;
}

.npb-results-grid{
    display:grid;
    grid-template-columns:repeat(3,minmax(0,1fr));
    gap:14px;
}

.npb-result-card{
    background:#fff;
    border:1px solid #e3e8ee;
    border-radius:16px;
    box-shadow:0 7px 20px rgba(0,0,0,.06);
    padding:18px 16px;
    display:grid;
    grid-template-columns:1fr 1.25fr 1fr;
    align-items:center;
    min-height:132px;
}

.npb-result-team{
    display:flex;
    flex-direction:column;
    align-items:center;
    justify-content:center;
    min-width:0;
}

.npb-result-logo{
    width:62px;
    height:62px;
    object-fit:contain;
    display:block;
}

.npb-result-name{
    margin-top:7px;
    font-size:.86rem;
    font-weight:900;
    color:#111c2a;
    text-align:center;
    white-space:nowrap;
}

.npb-result-center{
    text-align:center;
}

.npb-result-score{
    font-size:1.75rem;
    line-height:1;
    font-weight:950;
    color:#0a1420;
    white-space:nowrap;
}

.npb-result-score span{
    color:#8993a0;
    padding:0 4px;
}

.npb-result-final{
    display:inline-block;
    margin-top:9px;
    padding:4px 9px;
    border-radius:999px;
    background:#eef1f4;
    color:#56616e;
    font-size:.65rem;
    font-weight:900;
}

.npb-result-venue{
    margin-top:6px;
    color:#77818e;
    font-size:.66rem;
    font-weight:700;
    white-space:nowrap;
}

@media screen and (max-width:768px){
    .npb-results-section{
        margin:14px 0 18px;
    }

    .npb-results-grid{
        grid-template-columns:1fr;
        gap:10px;
    }

    .npb-result-card{
        min-height:105px;
        padding:13px 10px;
    }

    .npb-result-logo{
        width:48px;
        height:48px;
    }

    .npb-result-score{
        font-size:1.45rem;
    }

    .npb-result-name{
        font-size:.76rem;
    }

    .npb-result-venue{
        font-size:.60rem;
    }
}
</style>
""", unsafe_allow_html=True)

            _npb_cards = []

            for _g in _npb_other_games:
                _home = str(_g.get("home", "-"))
                _away = str(_g.get("away", "-"))

                _home_score = _g.get("home_score")
                _away_score = _g.get("away_score")

                _status = str(_g.get("status", "")).lower()
                _game_time = str(_g.get("time", "-"))
                _venue = str(_g.get("venue", "-"))

                if _status == "final":
                    _score_text = f"{_away_score} − {_home_score}"
                    _status_text = "試合終了"
                elif _status == "live":
                    if _away_score is not None and _home_score is not None:
                        _score_text = f"{_away_score} − {_home_score}"
                    else:
                        _score_text = "LIVE"
                    _status_text = "試合中"
                else:
                    _score_text = _game_time
                    _status_text = "試合開始前"

                _home_slug = _npb_logo_slug(_home)
                _away_slug = _npb_logo_slug(_away)

                _home_badge = _team_text_badge(_home, _home_slug)
                _away_badge = _team_text_badge(_away, _away_slug)

                _npb_cards.append(
                    f'<div class="npb-result-card">'
                    f'<div class="npb-result-team">'
                    f'{_away_badge}'
                    f'<div class="npb-result-name">{_away}</div>'
                    f'</div>'
                    f'<div class="npb-result-center">'
                    f'<div class="npb-result-score">{_score_text}</div>'
                    f'<div class="npb-result-final">{_status_text}</div>'
                    f'<div class="npb-result-venue">{_venue}</div>'
                    f'</div>'
                    f'<div class="npb-result-team">'
                    f'{_home_badge}'
                    f'<div class="npb-result-name">{_home}</div>'
                    f'</div>'
                    f'</div>'
                )

            _npb_html = (
                '<div class="npb-results-section">'
                '<div class="npb-results-title"><span>⚾</span>本日のNPB 試合結果</div>'
                '<div class="npb-results-grid">'
                + ''.join(_npb_cards)
                + '</div></div>'
            )

            st.markdown(
                _npb_html,
                unsafe_allow_html=True
            )

except Exception as _npb_today_error:
    pass


if live_score_ready:
    opponent_name = str(npb.get("opponent", "OPPONENT"))
    game_status = str(live.get("status", "-"))
    if game_status == "試合終了":
        status_text = "FINAL"
    elif game_status == "試合中":
        i = live.get("inning")
        h = live.get("half", "")
        status_text = f"{i}回{h}" if i else "LIVE"
    else:
        status_text = game_status

    st.markdown(
        f"""
        <div class="hawks-game-card">
          <div class="hawks-game-card-head">
            <div class="hawks-game-card-title"><span class="hawks-red-dot"></span>試合状況（NPB LIVE自動反映）</div>
            <div class="hawks-game-card-source">NPB LIVE</div>
          </div>
          <div class="hawks-score-area">
            <div class="hawks-team hawks-home">
              <div class="hawks-team-icon">🦅</div>
              <div class="hawks-team-name">HAWKS</div>
              <div class="hawks-team-sub">ソフトバンク</div>
              <div class="hawks-score-number hawks-score-main">{hawks_score}</div>
            </div>
            <div class="hawks-vs-area">
              <div class="hawks-final-badge">{status_text}</div>
              <div class="hawks-vs">VS</div>
              <div class="hawks-score-diff {score_status_class}">{score_icon} {score_status}</div>
            </div>
            <div class="hawks-team hawks-away">
              <div class="hawks-team-icon">⚾</div>
              <div class="hawks-team-name">{opponent_name}</div>
              <div class="hawks-team-sub">OPPONENT</div>
              <div class="hawks-score-number">{opponent_score}</div>
            </div>
          </div>
          <div class="hawks-score-footer">
            <span class="hawks-sync-dot"></span>
            NPB公式速報のスコアを自動使用中
            <span class="hawks-auto-badge">AUTO</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True
    )

# AI計算へ渡す点差
#
# LIVE時:
#   0-0でも実スコア0点差として扱う
#
# 手動時:
#   0-0なら上部ハンディを使用
# =========================================================
# =========================================================
# HAWKS AI v2.7
# 開始ハンディと実スコアを完全分離
# =========================================================
if live_score_ready:
    # NPB LIVE実スコア
    score_mode = "live"
    effective_score_diff = float(score_diff)

elif hawks_score != 0 or opponent_score != 0:
    # NPB取得失敗時などの手動実スコア
    score_mode = "manual_score"
    effective_score_diff = float(score_diff)

else:
    # 試合開始前のハンディ
    score_mode = "handicap"
    effective_score_diff = 0.0


game_finished = (
    live.get("status") == "試合終了"
)

if game_finished:
    pass

game_col1, game_col2 = st.columns([1.25, 1])

with game_col1:

    # -----------------------------------------------------
    # イニング
    # -----------------------------------------------------
    live_inning = live.get("inning")

    if game_finished:
        inning = (
            live_inning
            if isinstance(live_inning, int)
            else 9
        )

    elif (
        live_score_ready
        and isinstance(live_inning, int)
        and 1 <= live_inning <= 9
    ):
        inning = live_inning

        inning_text = f"{inning}回"

        if live.get("half") in ("表", "裏"):
            inning_text += live["half"]

        st.metric(
            "現在のイニング（NPB自動）",
            inning_text
        )

    else:
        inning = st.slider(
            "現在のイニング（回）",
            1,
            9,
            1
        )

    # -----------------------------------------------------
    # 攻撃側
    # -----------------------------------------------------
    live_attack = live.get("attack_side")

    if game_finished:
        attack_side = (
            live_attack
            if live_attack in (
                "ホークス攻撃中",
                "相手攻撃中"
            )
            else "ホークス攻撃中"
        )

    elif (
        live_score_ready
        and live_attack in (
            "ホークス攻撃中",
            "相手攻撃中"
        )
    ):
        attack_side = live_attack

        st.metric(
            "現在の攻撃（NPB自動）",
            attack_side
        )

    else:
        attack_side = st.radio(
            "現在の攻撃",
            [
                "ホークス攻撃中",
                "相手攻撃中"
            ],
            horizontal=True
        )


with game_col2:

    # -----------------------------------------------------
    # アウト・走者
    # 現在打席情報が取得できた時だけ自動
    # -----------------------------------------------------
    live_context_ready = bool(
        live.get("live_context_ready")
    )

    if game_finished:

        # 試合終了後はLIVE状況をAI計算へ影響させない
        outs = 0
        r1 = False
        r2 = False
        r3 = False

    elif live_context_ready:

        live_outs = live.get("outs")

        if isinstance(live_outs, int):
            outs = live_outs
        else:
            outs = 0

        r1 = bool(live.get("base1"))
        r2 = bool(live.get("base2"))
        r3 = bool(live.get("base3"))

        st.metric(
            "アウト（NPB自動）",
            f"{outs}アウト"
        )

        runners = []

        if r1:
            runners.append("1塁")

        if r2:
            runners.append("2塁")

        if r3:
            runners.append("3塁")

        runner_text = (
            "・".join(runners)
            if runners
            else "走者なし"
        )

        st.metric(
            "ランナー（NPB自動）",
            runner_text
        )

        if live.get("last_batter"):
            st.caption(
                f'現在打者：{live.get("last_batter")} '
                f'｜ カウント：{live.get("last_count", "-")}'
            )

    else:

        outs = st.radio(
            "アウトカウント",
            [0, 1, 2],
            horizontal=True
        )

        st.markdown("**🏃 ランナー状況**")

        rc1, rc2, rc3 = st.columns(3)

        r1 = rc1.checkbox("1塁")
        r2 = rc2.checkbox("2塁")
        r3 = rc3.checkbox("3塁")


# 旧計算互換用
handicap = max(0, -handicap_score)



# =========================================================
# HAWKS AI v2.1
# 詳細補正値を計算前に取得
# =========================================================

wins_sb = st.session_state.get(
    "wins_sb_ui",
    wins_sb_auto if wins_sb_auto > 0 else 15
)

wins_opp = st.session_state.get("wins_opp_ui", 10)

st_momentum = st.session_state.get(
    "st_momentum_ui",
    st_momentum_auto
)

p_sb = st.session_state.get(
    "p_sb_ui",
    "柱クラス (大関/スチュワートなど)"
)

p_opp = st.session_state.get(
    "p_opp_ui",
    "標準的な投手"
)

st_pitcher_hand = st.session_state.get(
    "pitcher_hand_ui",
    "右投げ (標準)"
)

st_pitcher_compat = st.session_state.get(
    "pitcher_compat_ui",
    "普通・データなし"
)

st_weather = st.session_state.get(
    "weather_ui",
    "ドーム・通常 (風なし)"
)

keyman_clean = st.session_state.get(
    "keyman_clean_ui",
    True
)

keyman_bench = st.session_state.get(
    "keyman_bench_ui",
    False
)

reliever_8th = st.session_state.get(
    "reliever_8th_ui",
    True
)

reliever_9th = st.session_state.get(
    "reliever_9th_ui",
    True
)

reliever_fatigue = st.session_state.get(
    "reliever_fatigue_ui",
    False
)

st.divider()

# --- 3. 全自動計算 ＆ リアルタイム描画 ---
total = wins_sb + wins_opp
if total == 0:
    st.warning("勝敗数を1試合以上入力してください。")
else:
    # =========================================================
    # HAWKS AI 勝率エンジン v2
    # =========================================================

    # 1. 基礎勝率
    # NPB公式のシーズン成績を優先し、取得できない場合だけ手動値を使用
    try:
        npb_wins = int(npb.get("wins", 0))
        npb_losses = int(npb.get("losses", 0))
        npb_games_decided = npb_wins + npb_losses
    except Exception:
        npb_wins = 0
        npb_losses = 0
        npb_games_decided = 0

    # HAWKS AI v2.2
    # ホークスと相手双方のシーズン勝率から対戦基礎勝率を計算
    hawks_pct = hawks_team_stats.get("pct")
    opp_pct = opponent_team_stats.get("pct")

    if hawks_pct is not None and opp_pct is not None:
        denominator = (
            hawks_pct
            + opp_pct
            - (2 * hawks_pct * opp_pct)
        )

        if denominator > 0:
            base_prob = (
                (
                    hawks_pct
                    - hawks_pct * opp_pct
                )
                / denominator
            ) * 100.0
        else:
            base_prob = hawks_pct * 100.0

    elif npb_games_decided > 0:
        base_prob = (npb_wins / npb_games_decided) * 100.0

    else:
        base_prob = (wins_sb / total) * 100.0

    # ---------------------------------------------------------
    # 2. 球場補正
    # ---------------------------------------------------------
    if "ホーム" in venue or "みずほ" in str(npb.get("stadium", "")):
        venue_mod = 3.0
    elif "ビジター" in venue:
        venue_mod = -3.0
    else:
        venue_mod = 0.0

    # ---------------------------------------------------------
    # 3. 先発投手補正 v2.2
    # NPB公式防御率を優先
    # ---------------------------------------------------------
    hawks_era = hawks_pitcher_stats.get("era")
    opp_era = opp_pitcher_stats.get("era")

    if hawks_era is not None and opp_era is not None:
        # 防御率差1.00につき約2%補正
        pitcher_mod = (opp_era - hawks_era) * 2.0
        pitcher_mod = max(-7.0, min(7.0, pitcher_mod))

    else:
        # データ取得失敗時は旧手動評価
        if "エース" in p_sb:
            p_sb_val = 5.0
        elif "柱" in p_sb:
            p_sb_val = 2.0
        else:
            p_sb_val = -4.0

        if "エース" in p_opp:
            p_opp_val = 5.0
        elif "標準" in p_opp:
            p_opp_val = 1.0
        else:
            p_opp_val = -3.0

        pitcher_mod = p_sb_val - p_opp_val

    # ---------------------------------------------------------
    # 4. 直近5試合の勢い
    # NPB自動取得を優先
    # ---------------------------------------------------------
    recent5 = npb.get("recent5", [])

    if recent5:
        recent_wins = recent5.count("○")

        momentum_table = {
            5: 5.0,
            4: 3.5,
            3: 1.5,
            2: -1.0,
            1: -3.0,
            0: -5.0,
        }

        momentum_mod = momentum_table.get(recent_wins, 0.0)

    else:
        momentum_mod = 0.0

        if "絶好調" in st_momentum:
            momentum_mod = 4.0
        elif "勢いあり" in st_momentum:
            momentum_mod = 2.0
        elif "やや不振" in st_momentum:
            momentum_mod = -2.0
        elif "スランプ" in st_momentum:
            momentum_mod = -4.0

    # ---------------------------------------------------------
    # 5. 左右・対戦相性
    # ---------------------------------------------------------
    if "左投げ (主力" in st_pitcher_hand:
        hand_mod = -1.5
    elif "左のワンポイント" in st_pitcher_hand:
        hand_mod = -2.5
    elif "得意なタイプ" in st_pitcher_hand:
        hand_mod = 2.0
    else:
        hand_mod = 0.0

    if "カモ" in st_pitcher_compat:
        compat_mod = 5.0
    elif "得意" in st_pitcher_compat:
        compat_mod = 3.0
    elif "天敵" in st_pitcher_compat:
        compat_mod = -5.0
    else:
        compat_mod = 0.0

    pitcher_compat_total = compat_mod + hand_mod

    # ---------------------------------------------------------
    # 6. 球場環境
    # ---------------------------------------------------------
    weather_mod = 0.0

    if "ルーフオープン" in st_weather:
        weather_mod = 1.0
    elif "追い風" in st_weather:
        weather_mod = 1.5
    elif "向かい風" in st_weather:
        weather_mod = -1.0

    # ---------------------------------------------------------
    # 7. 試合終盤ほどリリーフ・キーマンの重要度を上げる
    # ---------------------------------------------------------
    late_factor = max(
        0.0,
        min(1.0, (inning - 4) / 5.0)
    )

    reliever_raw = (
        (2.5 if reliever_8th else 0.0)
        + (3.0 if reliever_9th else 0.0)
        - (4.0 if reliever_fatigue else 0.0)
    )

    reliever_mod = reliever_raw * (0.35 + 0.65 * late_factor)

    keyman_raw = (
        (2.5 if keyman_clean else 0.0)
        + (1.5 if keyman_bench else 0.0)
    )

    keyman_mod = keyman_raw * (0.60 + 0.40 * late_factor)

    # ---------------------------------------------------------
    # 8. 点差補正
    #
    # handicap_score
    #  +3 = ホークス3点リード
    #   0 = 同点
    #  -2 = ホークス2点ビハインド
    #
    # 後半になるほど1点の価値を大きくする
    # ---------------------------------------------------------
    # =====================================================
    # HAWKS AI v2.6 点差エンジン
    #
    # ハンディは「開始想定スコア」として扱う
    # -2 = ホークス 0 - 2 相手
    # +2 = ホークス 2 - 0 相手
    #
    # LIVE開始後はNPB実スコアを使用
    # =====================================================

    # =====================================================
    # HAWKS AI v2.7
    # 開始ハンディ補正 / LIVE実点差補正
    # =====================================================

    if score_mode == "handicap":

        # 試合開始前専用。
        # イニングやアウト数とは連動させない。
        handicap_value = 8.0

        score_mod = (
            float(handicap_score)
            * handicap_value
        )

    else:

        # 実際に試合が進行している時の点差。
        # 後半ほど1点の価値を大きくする。
        point_value = (
            8.0
            + ((inning - 1) * 1.25)
        )

        out_pressure = 1.0

        if inning >= 7:
            out_pressure += outs * 0.10

        score_mod = (
            effective_score_diff
            * point_value
            * out_pressure
        )

    # 極端な値だけ制限
    score_mod = max(
        -55.0,
        min(55.0, score_mod)
    )

    # 既存グラフとの互換性のため名前を維持
    handicap_penalty = score_mod

    # ---------------------------------------------------------
    # 9. ランナー・アウト・攻撃側によるWPA局面補正
    # ---------------------------------------------------------
    runner_state = (
        (1 if r1 else 0)
        + (2 if r2 else 0)
        + (4 if r3 else 0)
    )

    base_wpa_map = {
        0: 0.0,
        1: 1.5,   # 1塁
        2: 2.5,   # 2塁
        3: 4.0,   # 1・2塁
        4: 3.5,   # 3塁
        5: 5.0,   # 1・3塁
        6: 6.0,   # 2・3塁
        7: 8.0,   # 満塁
    }

    raw_wpa = base_wpa_map.get(runner_state, 0.0)

    out_multipliers = [
        1.00,
        0.72,
        0.42,
    ]

    inning_wpa_factor = 0.65 + (0.70 * late_factor)

    wpa_bonus = (
        raw_wpa
        * out_multipliers[outs]
        * inning_wpa_factor
    )

    if attack_side == "相手攻撃中":
        wpa_bonus = -wpa_bonus

    # ---------------------------------------------------------
    # 10. 最終勝率
    # ---------------------------------------------------------
    total_raw = (
        base_prob
        + venue_mod
        + pitcher_mod
        + momentum_mod
        + pitcher_compat_total
        + weather_mod
        + reliever_mod
        + keyman_mod
        + handicap_penalty
        + wpa_bonus
    )

    final_sb = max(
        0.5,
        min(99.5, total_raw)
    )

    # =====================================================
    # HAWKS AI v2.1 結果表示
    # =====================================================

    st.markdown(
        '<div class="section-head section-green">🤖 HAWKS AI 勝利予測</div>',
        unsafe_allow_html=True
    )

    ai_col1, ai_col2 = st.columns([1, 2])

    with ai_col1:
        st.metric(
            label="ホークス勝利予測",
            value=f"{final_sb:.1f}%",
            delta=f"{total_raw - base_prob:+.1f}%（総合補正）"
        )

        st.progress(final_sb / 100.0)

    with ai_col2:
        if final_sb >= 70.0:
            st.success(
                "🦅 **勝利優勢**\n\n"
                "現在の戦況ではホークスがかなり有利です。"
            )
        elif final_sb >= 60.0:
            st.success(
                "🔥 **ホークス優勢**\n\n"
                "勝利期待値は高め。現在は勝ちパターンです。"
            )
        elif final_sb >= 45.0:
            st.info(
                "⚾ **接戦**\n\n"
                "次の得点や走者状況で勝率が大きく動きます。"
            )
        elif final_sb >= 25.0:
            st.warning(
                "⚠️ **やや劣勢**\n\n"
                "次の攻撃で得点できるかが重要です。"
            )
        else:
            st.error(
                "🔥 **厳しい展開**\n\n"
                "残りイニングと得点機会が重要です。"
            )

    st.caption(
        f"基礎勝率 {base_prob:.1f}% ｜ "
        f"総合補正 {total_raw - base_prob:+.1f}% ｜ "
        f"点差補正 {handicap_penalty:+.1f}%"
    )

    st.divider()

# =========================================================
# 普段触らない補正項目は折りたたむ
# =========================================================
with st.expander("⚙️ 詳細補正設定", expanded=False):

    st.caption(
        "NPB公式データを基本値として使用します。"
        "必要な場合だけ手動で補正してください。"
    )

    d1, d2 = st.columns(2)

    with d1:
        st.markdown("#### 📊 自動基本情報")

        st.text_input(
            "対戦相手",
            value=opponent,
            disabled=True
        )

        st.text_input(
            "開催地",
            value=venue,
            disabled=True
        )

        wins_sb = st.number_input(
            "ホークス勝利数",
            key="wins_sb_ui",
            min_value=0,
            value=wins_sb_auto if wins_sb_auto > 0 else 15
        )

        # NPB取得失敗時の旧ロジック用フォールバック
        wins_opp = st.number_input(
            "相手勝利数（予備値）",
            key="wins_opp_ui",
            min_value=0,
            value=10,
            help="NPB自動取得が使えない場合の予備値です"
        )

        momentum_options = [
            "通常 (五分)",
            "絶好調 (3連勝以上/勝ち越し中)",
            "勢いあり (直近勝ち越し)",
            "やや不振 (直近負け越し)",
            "スランプ (3連敗以上)",
        ]

        try:
            momentum_index = momentum_options.index(st_momentum_auto)
        except ValueError:
            momentum_index = 0

        st_momentum = st.selectbox(
            "直近チーム状態",
            momentum_options,
            index=momentum_index,
            key="st_momentum_ui"
        )

        st.markdown("#### 🥎 先発評価")

        p_sb = st.selectbox(
            f'ホークス先発：{npb.get("hawks_starter", "-")}',
            [
                "エース級 (モイネロ/有原)",
                "柱クラス (大関/スチュワートなど)",
                "谷間・リリーフ陣",
            ],
            index=1
        )

        p_opp = st.selectbox(
            f'相手先発：{npb.get("opp_starter", "-")}',
            [
                "相手エース級/守護神",
                "標準的な投手",
                "谷間・リリーフ陣",
            ],
            index=1
        )

    with d2:
        st.markdown("#### 🎯 相性・環境")

        st_pitcher_hand = st.selectbox(
            "相手投手の左右（利き腕）",
            [
                "右投げ (標準)",
                "左投げ (主力左打者に影響)",
                "左のワンポイント/刺客",
                "右投げ (得意なタイプ)",
            ],
            key="pitcher_hand_ui"
        )

        st_pitcher_compat = st.selectbox(
            "相手先発との野球相性",
            [
                "普通・データなし",
                "得意 (対チーム打率.280以上)",
                "カモ (.300超/攻略実績あり)",
                "天敵 (チーム打率.200未満/苦手)",
            ],
            key="pitcher_compat_ui"
        )

        st_weather = st.selectbox(
            "球場環境（風・屋根）",
            [
                "ドーム・通常 (風なし)",
                "PayPayドーム (ルーフオープン)",
                "屋外: 強い追い風 (打者有利)",
                "屋外: 強い向かい風 (投手有利)",
            ],
            key="weather_ui"
        )

        st.markdown("#### 🔥 攻撃陣")

        keyman_clean = st.checkbox(
            "クリーンナップ（近藤・山川等）に打順が回る",
            key="keyman_clean_ui",
            value=True
        )

        keyman_bench = st.checkbox(
            "代打の切り札（中村晃/川村等）が温存中",
            key="keyman_bench_ui",
            value=False
        )

        st.markdown("#### 🛡️ 勝利方程式")

        reliever_8th = st.checkbox(
            "8回男（ヘルナンデス/藤井）登板可能",
            key="reliever_8th_ui",
            value=True
        )

        reliever_9th = st.checkbox(
            "守護神（松本裕樹）登板可能",
            key="reliever_9th_ui",
            value=True
        )

        reliever_fatigue = st.checkbox(
            "リリーフ陣に連投疲労あり",
            key="reliever_fatigue_ui",
            value=False
        )

    st.divider()

    st.markdown(
        '<div class="section-head section-purple">📊 要素別の勝率インパクト</div>',
        unsafe_allow_html=True
    )

    categories = [
        "球場/開催地",
        "先発投手力",
        "チームの勢い",
        "対戦・左右相性",
        "風向き・屋根",
        "勝利方程式",
        "キーマン補正",
        "点差・残イニング",
        "WPA局面チャンス",
    ]

    values = [
        venue_mod,
        pitcher_mod,
        momentum_mod,
        pitcher_compat_total,
        weather_mod,
        reliever_mod,
        keyman_mod,
        handicap_penalty,
        wpa_bonus,
    ]

    text_labels = [
        f"{v:+.1f}%" if v != 0 else "±0.0%"
        for v in values
    ]

    colors = [
        "#2E7D32" if v > 0
        else ("#C62828" if v < 0 else "#757575")
        for v in values
    ]

    fig = go.Figure(
        go.Bar(
            x=values,
            y=categories,
            orientation="h",
            text=text_labels,
            textposition="auto",
            marker_color=colors,
        )
    )

    fig.update_layout(
        xaxis_title="勝率へのプラス/マイナス影響 (%)",
        yaxis=dict(autorange="reversed"),
        margin=dict(l=20, r=20, t=10, b=30),
        height=380,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )

    fig.add_vline(
        x=0,
        line_width=1.5,
        line_dash="dash",
        line_color="#333333"
    )

    st.plotly_chart(fig, width="stretch")



# =========================================================
# HAWKS AI v2.4 試合終了時の自動保存
# =========================================================

if (
    live.get("status") == "試合終了"
    and live.get("hawks_score") is not None
    and live.get("opp_score") is not None
):

    auto_hawks_score = int(live["hawks_score"])
    auto_opp_score = int(live["opp_score"])

    if auto_hawks_score > auto_opp_score:
        auto_result = "勝"
    elif auto_hawks_score < auto_opp_score:
        auto_result = "敗"
    else:
        auto_result = "分"

    auto_game_id = (
        live.get("game_id")
        or f'{live.get("date")}_{npb.get("opponent", "unknown")}'
    )

    auto_game = {
        "game_id": auto_game_id,
        "date": live.get("date"),
        "opponent": npb.get("opponent", "-"),
        "stadium": npb.get("stadium", "-"),

        "hawks_score": auto_hawks_score,
        "opponent_score": auto_opp_score,
        "result": auto_result,

        "hawks_starter": npb.get(
            "hawks_starter", "-"
        ),

        "opponent_starter": npb.get(
            "opp_starter", "-"
        ),

        "hawks_starter_wins":
            hawks_pitcher_stats.get("wins"),

        "hawks_starter_losses":
            hawks_pitcher_stats.get("losses"),

        "hawks_starter_era":
            hawks_pitcher_stats.get("era"),

        "opponent_starter_wins":
            opp_pitcher_stats.get("wins"),

        "opponent_starter_losses":
            opp_pitcher_stats.get("losses"),

        "opponent_starter_era":
            opp_pitcher_stats.get("era"),

        # 的中判定に使う正式な試合前予測
        "ai_probability": (
            get_pregame_probability(
                live.get("date"),
                npb.get("opponent", "-")
            )
            if get_pregame_probability(
                live.get("date"),
                npb.get("opponent", "-")
            ) is not None
            else round(float(final_sb), 1)
        ),

        # 試合中に変動するLIVE勝率は別項目
        "live_probability": round(
            float(final_sb), 1
        ),

        "base_probability": round(
            float(base_prob), 1
        ),

        "auto_saved": True,
        "source": "NPB公式速報",
    }

    save_game_history(auto_game)

    st.success(
        f'✅ 試合終了・自動保存済み\n\n'
        f'ソフトバンク {auto_hawks_score} - {auto_opp_score} '
        f'{npb.get("opponent", "-")}\n\n'
        f'AI最終予測 {float(final_sb):.1f}%'
    )

# =========================================================
# 📚 試合保存・履歴
# =========================================================

st.divider()
st.markdown(
        '<div class="section-head section-gray">📚 試合履歴</div>',
        unsafe_allow_html=True
    )

history_c1, history_c2 = st.columns([1, 2])

with history_c1:
    save_result = st.button(
        "💾 この試合結果を保存",
        use_container_width=True
    )

with history_c2:
    st.caption(
        "通常はNPB公式速報から自動保存されます。"
        "このボタンは自動取得できなかった場合の非常用です。"
    )

if save_result:

    game_date = datetime.now().strftime("%Y-%m-%d")

    final_hawks_score = int(
        st.session_state.get("hawks_score", 0)
    )

    final_opp_score = int(
        st.session_state.get("opponent_score", 0)
    )

    # 試合開始前の 0-0 を引き分けとして誤保存しない
    if final_hawks_score == 0 and final_opp_score == 0:
        st.error(
            "⚠️ 0-0のため保存しません。"
            "試合開始前またはスコア未取得の可能性があります。"
        )
        st.stop()

    if final_hawks_score > final_opp_score:
        game_result = "勝"
    elif final_hawks_score < final_opp_score:
        game_result = "敗"
    else:
        game_result = "分"

    game = {
        "game_id": (
            f'{game_date}_'
            f'{npb.get("opponent", "unknown")}'
        ),
        "date": game_date,
        "opponent": npb.get("opponent", "-"),
        "stadium": npb.get("stadium", "-"),
        "hawks_score": final_hawks_score,
        "opponent_score": final_opp_score,
        "result": game_result,

        "hawks_starter": npb.get(
            "hawks_starter",
            "-"
        ),

        "opponent_starter": npb.get(
            "opp_starter",
            "-"
        ),

        "hawks_starter_wins":
            hawks_pitcher_stats.get("wins"),

        "hawks_starter_losses":
            hawks_pitcher_stats.get("losses"),

        "hawks_starter_era":
            hawks_pitcher_stats.get("era"),

        "opponent_starter_wins":
            opp_pitcher_stats.get("wins"),

        "opponent_starter_losses":
            opp_pitcher_stats.get("losses"),

        "opponent_starter_era":
            opp_pitcher_stats.get("era"),

        # 正式な試合前AI予測
        "ai_probability": (
            get_pregame_probability(
                game_date,
                npb.get("opponent", "-")
            )
            if get_pregame_probability(
                game_date,
                npb.get("opponent", "-")
            ) is not None
            else round(float(final_sb), 1)
        ),

        # 保存時点のLIVE勝率
        "live_probability": round(
            float(final_sb),
            1
        ),

        "base_probability": round(
            float(base_prob),
            1
        ),
    }

    save_game_history(game)

    st.success(
        f'✅ {game_date} '
        f'{npb.get("opponent", "-")}戦を保存しました。'
    )


history = load_game_history()

if not history:
    st.info(
        "まだ保存された試合はありません。"
    )

else:
    total_games = len(history)

    win_count = sum(
        1 for g in history
        if g.get("result") == "勝"
    )

    loss_count = sum(
        1 for g in history
        if g.get("result") == "敗"
    )

    draw_count = sum(
        1 for g in history
        if g.get("result") == "分"
    )

    h1, h2, h3, h4 = st.columns(4)

    h1.metric(
        "保存試合",
        f"{total_games}試合"
    )

    h2.metric(
        "勝",
        win_count
    )

    h3.metric(
        "敗",
        loss_count
    )

    h4.metric(
        "分",
        draw_count
    )

    # =====================================================
    # 📊 HAWKS AI 予測成績
    # =====================================================
    st.markdown(
        '<div class="section-head section-purple">📊 HAWKS AI 予測成績</div>',
        unsafe_allow_html=True
    )

    # AI勝率が保存されている試合だけ対象
    ai_games = []

    for g in history:
        try:
            probability = float(g.get("ai_probability"))
        except (TypeError, ValueError):
            continue

        result_value = g.get("result")

        # 引き分けは予測的中率から除外
        if result_value not in ("勝", "敗"):
            continue

        predicted_result = (
            "勝"
            if probability >= 50.0
            else "敗"
        )

        hit = predicted_result == result_value

        ai_games.append({
            "date": g.get("date", ""),
            "result": result_value,
            "probability": probability,
            "predicted_result": predicted_result,
            "hit": hit,
        })

    ai_target_games = len(ai_games)

    hit_count = sum(
        1 for g in ai_games
        if g["hit"]
    )

    accuracy = (
        (hit_count / ai_target_games) * 100.0
        if ai_target_games > 0
        else 0.0
    )

    probabilities = []

    for g in history:
        try:
            probabilities.append(
                float(g.get("ai_probability"))
            )
        except (TypeError, ValueError):
            pass

    average_probability = (
        sum(probabilities) / len(probabilities)
        if probabilities
        else 0.0
    )

    a1, a2, a3, a4 = st.columns(4)

    a1.metric(
        "AI判定対象",
        f"{ai_target_games}試合"
    )

    a2.metric(
        "的中",
        f"{hit_count}試合"
    )

    a3.metric(
        "予測的中率",
        f"{accuracy:.1f}%"
        if ai_target_games > 0
        else "-"
    )

    a4.metric(
        "平均AI勝率",
        f"{average_probability:.1f}%"
        if probabilities
        else "-"
    )

    if ai_target_games > 0:

        # -------------------------------------------------
        # 月別集計
        # -------------------------------------------------
        monthly = {}

        for g in ai_games:
            date_value = str(g.get("date", ""))

            if len(date_value) >= 7:
                month = date_value[:7]
            else:
                month = "不明"

            if month not in monthly:
                monthly[month] = {
                    "games": 0,
                    "hits": 0,
                    "wins": 0,
                    "losses": 0,
                    "probabilities": [],
                }

            monthly[month]["games"] += 1

            if g["hit"]:
                monthly[month]["hits"] += 1

            if g["result"] == "勝":
                monthly[month]["wins"] += 1
            elif g["result"] == "敗":
                monthly[month]["losses"] += 1

            monthly[month]["probabilities"].append(
                g["probability"]
            )

        st.markdown(
        '<div class="section-subhead">📅 月別AI予測成績</div>',
        unsafe_allow_html=True
    )

        for month in sorted(
            monthly.keys(),
            reverse=True
        ):
            m = monthly[month]

            month_accuracy = (
                (m["hits"] / m["games"]) * 100.0
                if m["games"] > 0
                else 0.0
            )

            month_average = (
                sum(m["probabilities"])
                / len(m["probabilities"])
                if m["probabilities"]
                else 0.0
            )

            mc1, mc2, mc3, mc4 = st.columns(4)

            mc1.metric(
                month,
                f'{m["games"]}試合'
            )

            mc2.metric(
                "実績",
                f'{m["wins"]}勝 {m["losses"]}敗'
            )

            mc3.metric(
                "的中率",
                f"{month_accuracy:.1f}%"
            )

            mc4.metric(
                "平均AI勝率",
                f"{month_average:.1f}%"
            )

        # -------------------------------------------------
        # 直近AI判定
        # -------------------------------------------------
        with st.expander(
            "🎯 AI予測の判定履歴",
            expanded=False
        ):
            for g in ai_games[:20]:

                icon = "✅" if g["hit"] else "❌"

                st.write(
                    f'{icon} '
                    f'{g["date"]} ｜ '
                    f'AI {g["probability"]:.1f}% ｜ '
                    f'予測：{g["predicted_result"]} ｜ '
                    f'実際：{g["result"]}'
                )

    else:
        st.caption(
            "試合結果が保存されると、"
            "AI予測的中率を自動集計します。"
        )

    st.divider()

    for game in history:

        mark = {
            "勝": "🟢",
            "敗": "🔴",
            "分": "⚪",
        }.get(
            game.get("result"),
            "⚾"
        )

        title = (
            f'{mark} {game.get("date", "-")} '
            f'vs {game.get("opponent", "-")} '
            f'{game.get("hawks_score", "-")}'
            f' - '
            f'{game.get("opponent_score", "-")}'
        )

        with st.expander(title):

            c1, c2 = st.columns(2)

            with c1:
                st.markdown(
                    f'''
**結果：** {game.get("result", "-")}  
**球場：** {game.get("stadium", "-")}  
**AI予測勝率：** {game.get("ai_probability", "-")}%  
**基礎勝率：** {game.get("base_probability", "-")}%  
'''
                )

            with c2:
                st.markdown(
                    f'''
**ホークス先発：** {game.get("hawks_starter", "-")}  
{game.get("hawks_starter_wins", "-")}勝
{game.get("hawks_starter_losses", "-")}敗 /
防御率 {game.get("hawks_starter_era", "-")}

**相手先発：** {game.get("opponent_starter", "-")}  
{game.get("opponent_starter_wins", "-")}勝
{game.get("opponent_starter_losses", "-")}敗 /
防御率 {game.get("opponent_starter_era", "-")}
'''
                )

# ============================================================
# HAWKS AI FINAL DEVICE LAYOUT
# PC: 1920x1080 optimized
# Mobile: independent responsive layout
# ============================================================
st.markdown("""
<style>

/* =========================
   PC / LARGE SCREEN
   ========================= */
@media screen and (min-width: 1200px) {

    .block-container,
    [data-testid="stMainBlockContainer"] {
        width: calc(100vw - 240px) !important;
        max-width: 1600px !important;
        min-width: 0 !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        box-sizing: border-box !important;
    }

}

/* =========================
   TABLET / SMALL PC
   ========================= */
@media screen and (min-width: 769px) and (max-width: 1199px) {

    .block-container,
    [data-testid="stMainBlockContainer"] {
        width: calc(100vw - 40px) !important;
        max-width: none !important;
        margin-left: auto !important;
        margin-right: auto !important;
        padding-left: 0 !important;
        padding-right: 0 !important;
        box-sizing: border-box !important;
    }

}

/* =========================
   MOBILE
   ========================= */
@media screen and (max-width: 768px) {

    .block-container,
    [data-testid="stMainBlockContainer"] {
        width: 100% !important;
        max-width: 100% !important;
        margin: 0 !important;
        padding-left: 10px !important;
        padding-right: 10px !important;
        box-sizing: border-box !important;
    }

}

</style>
""", unsafe_allow_html=True)

# ============================================================
# HAWKS AI PC FINAL DESIGN
# 1920x1080 optimized / mobile untouched
# ============================================================
st.markdown("""
<style>

@media screen and (min-width:1200px){

    /* ===== Streamlit top blank space removal ===== */
    header[data-testid="stHeader"]{
        height:0 !important;
        min-height:0 !important;
        background:transparent !important;
    }

    [data-testid="stAppViewContainer"] > .main{
        padding-top:0 !important;
    }

    .block-container,
    [data-testid="stMainBlockContainer"]{
        width:calc(100vw - 80px) !important;
        max-width:1640px !important;
        padding-top:0 !important;
        padding-left:0 !important;
        padding-right:0 !important;
        margin:0 auto !important;
    }

    /* ===== HERO ===== */
    .hawks-hero,
    .hawks-premium-hero{
        width:100% !important;
        margin-top:0 !important;
        border-radius:18px 18px 0 0 !important;
        overflow:hidden !important;
    }

    /* ===== PREMIUM OUTER SHELL ===== */
    .hawks-premium-shell{
        width:100% !important;
        margin-top:0 !important;
        padding:0 18px 22px !important;
        box-sizing:border-box !important;
        border-radius:0 0 22px 22px !important;
    }

    /* ===== LIVE BAR ===== */
    .hawks-live-strip{
        min-height:58px !important;
        margin:12px 0 10px !important;
        padding:0 20px !important;
        border-radius:14px !important;
    }

    /* ===== SCOREBOARD ===== */
    .hawks-game-card{
        width:100% !important;
        margin:0 !important;
        border-radius:20px !important;
        background:#fff !important;
        border:1px solid #e7eaee !important;
        box-shadow:0 10px 30px rgba(0,0,0,.08) !important;
    }

    .hawks-score-area{
        display:grid !important;
        grid-template-columns:1fr .65fr 1fr !important;
        min-height:160px !important;
        padding:28px 34px 20px !important;
        align-items:center !important;
    }

    .hawks-team{
        display:flex !important;
        align-items:center !important;
        gap:20px !important;
        text-align:left !important;
    }

    .hawks-away{
        flex-direction:row-reverse !important;
        text-align:right !important;
    }

    .hawks-team-icon,
    .hawks-premium-logo{
        width:86px !important;
        height:86px !important;
        min-width:86px !important;
        flex:0 0 86px !important;
        margin:0 !important;
        display:flex !important;
        align-items:center !important;
        justify-content:center !important;
        border-radius:50% !important;
        background-color:#fff !important;
        background-position:center center !important;
        background-repeat:no-repeat !important;
        background-size:72% auto !important;
        box-sizing:border-box !important;
    }

    .hawks-team-name{
        font-size:1.35rem !important;
        color:#08111d !important;
        font-weight:900 !important;
        overflow:visible !important;
    }

    .hawks-team-sub{
        font-size:.72rem !important;
        color:#637083 !important;
        margin-top:4px !important;
    }

    .hawks-score-number{
        font-size:3.4rem !important;
        color:#07101a !important;
        margin-top:0 !important;
        line-height:1 !important;
    }

    .hawks-score-main{
        color:#df1f2d !important;
    }

    .hawks-vs-area{
        gap:8px !important;
    }

    .hawks-final-badge{
        background:#07101a !important;
        color:#37516f !important;
        border:none !important;
    }

    .hawks-score-diff{
        font-size:.80rem !important;
        padding:7px 12px !important;
        border-radius:999px !important;
    }

    /* ===== DETAIL / ANALYSIS CARDS ===== */
    .hawks-detail-card,
    .hawks-analysis-card{
        border-radius:16px !important;
    }
}

</style>
""", unsafe_allow_html=True)

# ============================================================
# HAWKS AI INDIVIDUAL TEAM LOGO FINAL
# ============================================================
st.markdown("""
<style>

/* Individual team logo */
.hawks-premium-team-logo{
    display:block !important;
    width:82px !important;
    height:82px !important;
    object-fit:contain !important;
    object-position:center !important;
    flex:0 0 82px !important;
    margin:0 !important;
    padding:0 !important;
    background:transparent !important;
}

/* PC 1920x1080 */
@media screen and (min-width:1200px){
    .hawks-premium-team-logo{
        width:92px !important;
        height:92px !important;
        flex-basis:92px !important;
    }
}

/* Smartphone */
@media screen and (max-width:768px){
    .hawks-premium-team-logo{
        width:56px !important;
        height:56px !important;
        flex-basis:56px !important;
    }
}

</style>
""", unsafe_allow_html=True)

# ===== HAWKS Dynamic Banner visual tuning =====
st.markdown("""

""", unsafe_allow_html=True)

# ===== HAWKS AI MOBILE ALIGN FINAL =====
st.markdown(r"""
<style id="hawks-mobile-align-final">

@media screen and (max-width:600px){

/* ==========================================
   1. PAGE
   ========================================== */

html,
body,
.stApp,
[data-testid="stAppViewContainer"]{
    width:100% !important;
    max-width:100% !important;
    overflow-x:hidden !important;
}

.block-container,
[data-testid="stMainBlockContainer"]{
    width:100% !important;
    max-width:100% !important;
    margin:0 !important;
    padding-left:0 !important;
    padding-right:0 !important;
    padding-top:0 !important;
    box-sizing:border-box !important;
}


/* ==========================================
   2. HERO
   ========================================== */

.hawks-hero{
    display:block !important;
    width:100% !important;
    max-width:100% !important;

    margin:0 !important;

    padding:18px 18px !important;

    min-height:190px !important;

    border-radius:0 !important;

    box-sizing:border-box !important;
    overflow:hidden !important;

    background-size:cover !important;
    background-position:center center !important;
}

.hawks-hero-kicker{
    font-size:.72rem !important;
}

.hawks-hero-title{
    font-size:2.15rem !important;
}

.hawks-hero-sub{
    font-size:.78rem !important;
}


/* ==========================================
   3. PREMIUM BLACK AREA
   HEROと同じ100%幅
   ========================================== */

.hawks-premium-shell{
    display:block !important;

    width:100% !important;
    max-width:100% !important;

    margin:0 !important;

    padding:
        12px
        16px
        18px
        16px !important;

    border-radius:
        0 0 18px 18px !important;

    box-sizing:border-box !important;

    overflow:hidden !important;
}


/* ==========================================
   4. NPB NEWS BAR
   ========================================== */

.hawks-premium-news{
    display:flex !important;
    align-items:center !important;
    justify-content:flex-start !important;
    flex-wrap:wrap !important;

    width:100% !important;
    max-width:100% !important;

    margin:0 0 12px 0 !important;

    padding:9px 12px !important;

    gap:5px 8px !important;

    box-sizing:border-box !important;
}

.hawks-premium-news .auto{
    margin-left:auto !important;
    white-space:nowrap !important;
}


/* ==========================================
   5. WHITE MAIN CARD
   ========================================== */

.hawks-premium-card{
    display:block !important;

    width:100% !important;
    max-width:100% !important;

    margin:0 !important;

    box-sizing:border-box !important;

    overflow:hidden !important;

    border-radius:18px !important;
}


/* ==========================================
   6. SCORE
   楽天 | SCORE | HAWKS
   ========================================== */

.hawks-premium-score{
    display:grid !important;

    grid-template-columns:
        minmax(0,1fr)
        104px
        minmax(0,1fr) !important;

    align-items:center !important;

    width:100% !important;

    padding:
        18px
        10px
        14px !important;

    gap:4px !important;

    box-sizing:border-box !important;
}


/* TEAM */

.hawks-premium-team{
    display:flex !important;

    flex-direction:column !important;

    align-items:center !important;
    justify-content:center !important;

    width:100% !important;
    min-width:0 !important;

    gap:5px !important;

    text-align:center !important;
}

.hawks-premium-team.right{
    flex-direction:column-reverse !important;
}


/* LOGO */

.hawks-premium-team-logo{
    display:block !important;

    width:54px !important;
    height:54px !important;

    min-width:54px !important;
    flex:0 0 54px !important;

    object-fit:contain !important;

    margin:0 auto !important;
}


/* TEAM NAME */

.hawks-premium-team-name{
    font-size:.90rem !important;
    line-height:1.15 !important;

    text-align:center !important;

    white-space:normal !important;
}

.hawks-premium-team-sub{
    font-size:.52rem !important;
    line-height:1.2 !important;

    text-align:center !important;

    white-space:normal !important;
}


/* SCORE CENTER */

.hawks-premium-scoreline{
    display:flex !important;

    flex-direction:column !important;

    align-items:center !important;
    justify-content:center !important;

    width:104px !important;
    min-width:104px !important;

    margin:0 auto !important;

    text-align:center !important;
}

.hawks-premium-scoreline .numbers{
    font-size:2.65rem !important;
    line-height:1 !important;

    white-space:nowrap !important;

    text-align:center !important;
}

.hawks-premium-status{
    display:inline-flex !important;

    align-items:center !important;
    justify-content:center !important;

    margin:8px auto 0 !important;

    white-space:nowrap !important;
}


/* ==========================================
   7. RESULT
   ========================================== */

.hawks-premium-result{
    display:flex !important;

    justify-content:center !important;
    align-items:center !important;

    width:100% !important;

    gap:14px !important;

    text-align:center !important;

    box-sizing:border-box !important;
}


/* ==========================================
   8. AI PREDICTION
   ========================================== */

.hawks-premium-ai{
    display:grid !important;

    grid-template-columns:
        66px
        minmax(0,1fr) !important;

    width:100% !important;

    margin:0 !important;

    padding:
        18px
        16px !important;

    gap:
        4px
        12px !important;

    align-items:center !important;

    box-sizing:border-box !important;
}

.hawks-premium-bot{
    width:66px !important;
    height:66px !important;

    display:flex !important;

    align-items:center !important;
    justify-content:center !important;

    grid-row:1 !important;
    grid-column:1 !important;
}

.hawks-premium-ai > div:nth-child(2){
    grid-column:2 !important;
    grid-row:1 !important;

    min-width:0 !important;
}

.hawks-premium-prob{
    font-size:2.55rem !important;
    line-height:1 !important;

    white-space:nowrap !important;
}


/* PROGRESS BAR */

.hawks-premium-track{
    grid-column:1 / -1 !important;

    width:100% !important;

    margin-top:10px !important;

    box-sizing:border-box !important;
}


/* CONFIDENCE */

.hawks-premium-confidence{
    grid-column:1 / -1 !important;

    display:flex !important;

    align-items:center !important;
    justify-content:space-between !important;

    width:100% !important;

    box-sizing:border-box !important;
}


/* ==========================================
   9. DETAIL
   ========================================== */

.hawks-premium-detail-title{
    width:100% !important;

    margin:0 !important;

    padding-left:16px !important;
    padding-right:16px !important;

    box-sizing:border-box !important;
}

.hawks-premium-details{
    width:100% !important;

    margin:0 !important;

    padding-left:16px !important;
    padding-right:16px !important;

    box-sizing:border-box !important;
}

.hawks-premium-detail{
    width:100% !important;

    box-sizing:border-box !important;
}


/* ==========================================
   10. FOOTER
   ========================================== */

.hawks-premium-foot{
    display:flex !important;

    justify-content:space-between !important;

    width:100% !important;

    padding:
        8px
        2px
        0 !important;

    gap:8px !important;

    box-sizing:border-box !important;

    font-size:.58rem !important;
}


/* ==========================================
   11. SAFETY
   ========================================== */

.hawks-premium-shell *,
.hawks-premium-card *,
.hawks-hero *{
    box-sizing:border-box !important;
}

.hawks-premium-shell img{
    max-width:100% !important;
}



/* ===== VISUAL FINAL TUNE MERGED ===== */
/* HERO：上部文字切れ修正 */
.hawks-hero{
    min-height:205px !important;
    padding:22px 18px 18px !important;
    background-position:center center !important;
}

.hawks-hero-kicker{
    display:block !important;
    position:relative !important;
    top:0 !important;
    margin:0 0 10px 0 !important;
    line-height:1.3 !important;
    font-size:.72rem !important;
}

.hawks-hero-mainrow{
    margin:0 !important;
}

.hawks-hero-title{
    margin:0 !important;
    line-height:1.05 !important;
}

.hawks-hero-sub{
    margin-top:16px !important;
    line-height:1.25 !important;
}


/* 速報バー */
.hawks-premium-news{
    min-height:54px !important;
    margin-bottom:12px !important;
}


/* AIカードをコンパクト化 */
.hawks-premium-ai{
    padding:16px 16px 14px !important;

    grid-template-columns:
        58px
        minmax(0,1fr) !important;

    column-gap:12px !important;
}

.hawks-premium-bot{
    width:58px !important;
    height:58px !important;
    font-size:1rem !important;
}

.hawks-premium-ai-label{
    font-size:.92rem !important;
    line-height:1.2 !important;
}

.hawks-premium-prob{
    font-size:2.25rem !important;
    line-height:1 !important;
    margin-top:3px !important;
}

.hawks-premium-ai small{
    font-size:.78rem !important;
    line-height:1.2 !important;
}


/* progress */
.hawks-premium-track{
    margin-top:12px !important;
}


/* 信頼度を小さく戻す */
.hawks-premium-confidence{
    margin-top:8px !important;
    padding:0 2px !important;

    font-size:.72rem !important;
    line-height:1 !important;

    min-height:20px !important;
}

.hawks-premium-confidence b{
    font-size:.82rem !important;
    line-height:1 !important;

    margin-left:4px !important;
}


/* 詳細情報との間隔 */
.hawks-premium-detail-title{
    margin-top:0 !important;
}


/* 白カード内の余計な高さを抑える */
.hawks-premium-card{
    padding-bottom:0 !important;
}
/* ===== /VISUAL FINAL TUNE MERGED ===== */

}


/* ===== PITCHER PHOTO CARD FINAL ===== */
.pitcher-card{
    display:flex !important;
    align-items:center !important;
    gap:14px !important;
    min-height:110px !important;
    padding:14px 16px !important;
    background:#fff !important;
    border:1px solid #dce5ef !important;
    border-radius:16px !important;
    box-shadow:0 5px 16px rgba(20,40,70,.06) !important;
}

.pitcher-photo-wrap{
    width:82px !important;
    height:82px !important;
    min-width:82px !important;
    overflow:hidden !important;
    border-radius:13px !important;
    background:#eef3f8 !important;
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;
}

.pitcher-photo{
    width:100% !important;
    height:100% !important;
    object-fit:cover !important;
    object-position:center top !important;
}

.pitcher-photo-fallback{
    font-size:2.2rem !important;
}

.pitcher-info{
    flex:1 !important;
    min-width:0 !important;
}

.pitcher-name{
    font-size:1.08rem !important;
    font-weight:900 !important;
    color:#17233a !important;
    margin-bottom:7px !important;
}

.pitcher-stats{
    display:flex !important;
    align-items:center !important;
    flex-wrap:wrap !important;
    gap:5px !important;
    font-size:.80rem !important;
    font-weight:700 !important;
    color:#607087 !important;
}

.pitcher-era{
    color:#0877d8 !important;
    font-weight:900 !important;
}

.pitcher-grade{
    padding:3px 8px !important;
    border-radius:999px !important;
    background:#eaf5ff !important;
    color:#0877d8 !important;
    font-size:.70rem !important;
    font-weight:900 !important;
}

@media screen and (max-width:600px){
    .pitcher-card{
        gap:9px !important;
        min-height:88px !important;
        padding:10px !important;
    }

    .pitcher-photo-wrap{
        width:62px !important;
        height:70px !important;
        min-width:62px !important;
    }

    .pitcher-name{
        font-size:.94rem !important;
    }

    .pitcher-stats{
        font-size:.68rem !important;
    }
}


/* ===== PREMIUM HANDICAP BOX ===== */
.hawks-premium-handicap-box{
    display:inline-flex;
    flex-direction:column;
    align-items:flex-start;
    justify-content:center;
    margin-top:10px;
    min-width:112px;
    padding:7px 14px 8px;
    background:#ffffff;
    border:3px solid #111820;
    border-radius:8px;
    box-sizing:border-box;
}

.hawks-premium-handicap-box.right{
    align-items:flex-end;
    margin-left:auto;
}

.hawks-premium-handicap-box small{
    display:block;
    margin-bottom:1px;
    color:#596675;
    font-size:.61rem;
    line-height:1.1;
    font-weight:800;
}

.hawks-premium-handicap-box strong{
    display:block;
    color:#14243a;
    font-size:1.45rem;
    line-height:1.05;
    font-weight:950;
}

.hawks-premium-handicap-box strong:not(:only-child){
    letter-spacing:.01em;
}

@media screen and (max-width:600px){
    .hawks-premium-handicap-box{
        min-width:76px;
        margin-top:6px;
        padding:5px 8px 6px;
        border-width:2px;
    }

    .hawks-premium-handicap-box small{
        font-size:.48rem;
    }

    .hawks-premium-handicap-box strong{
        font-size:1rem;
    }
}




.premium-stadium-top{
    display:inline-flex !important;
    align-items:center !important;
    gap:6px !important;
}

.premium-stadium-top::before{
    content:"";
    display:inline-block;
    width:12px;
    height:12px;
    border:2px solid #d7b300;
    border-radius:50%;
    box-sizing:border-box;
    position:relative;
    background:
        radial-gradient(circle at center,#d7b300 0 2px,transparent 2.5px);
}


/* ===== LIVE STATUS UNDER PITCHERS ===== */
.hawks-live-under-pitchers{
    margin:14px 18px 4px;
    padding:12px 16px;
    background:#081321;
    border:1px solid rgba(255,255,255,.12);
    border-radius:13px;
    display:flex;
    align-items:center;
    justify-content:center;
    gap:18px;
    color:#fff;
    box-shadow:0 6px 18px rgba(0,0,0,.16);
}

.hawks-live-inning{
    font-size:1.18rem;
    font-weight:950;
    color:#fff;
    letter-spacing:.03em;
}

.hawks-live-batting{
    font-size:.92rem;
    font-weight:900;
    color:#ffd900;
}

@media screen and (max-width:600px){
    .hawks-live-under-pitchers{
        margin:10px 8px 2px;
        padding:10px 12px;
        gap:10px;
        flex-direction:column;
    }

    .hawks-live-inning{
        font-size:1.05rem;
    }

    .hawks-live-batting{
        font-size:.80rem;
    }
}

/* =========================================================
   HAWKS PREMIUM SCOREBOARD FINAL
   ========================================================= */

.hawks-premium-score{
    display:grid !important;
    grid-template-columns:minmax(330px,1fr) 230px minmax(330px,1fr) !important;
    align-items:start !important;
    gap:16px !important;

    padding:20px 34px 24px !important;
}

/* ===== TEAM ===== */

.hawks-premium-team{
    display:grid !important;
    grid-template-columns:150px minmax(0,1fr) !important;
    align-items:start !important;
    gap:16px !important;
    min-width:0 !important;
}

.hawks-premium-team.right{
    grid-template-columns:minmax(0,1fr) 150px !important;
    text-align:right !important;
}

.hawks-premium-team-visual{
    width:150px !important;
    display:flex !important;
    flex-direction:column !important;
    align-items:center !important;
}

.hawks-premium-team-info{
    padding-top:8px !important;
    min-width:0 !important;
    font-size:16px !important;
    line-height:1.35 !important;
}

.hawks-premium-team-logo{
    width:138px !important;
    height:138px !important;
    object-fit:contain !important;
    flex-shrink:0 !important;
    display:block !important;
    transform:scale(1.10) !important;
    transform-origin:center center !important;
}

.hawks-premium-team-name{
    font-size:26px !important;
    line-height:1.1 !important;
    font-weight:950 !important;
    color:#07111f !important;
}

.hawks-premium-team-sub{
    margin-top:5px !important;
    color:#637083 !important;
    font-size:13px !important;
    line-height:1.25 !important;
    font-weight:750 !important;
}

.hawks-premium-team-meta{
    margin-top:12px !important;
    color:#111827 !important;
    font-size:13px !important;
    font-weight:850 !important;
}

.hawks-premium-team-record{
    margin-top:11px !important;
    color:#4b5563 !important;
    font-size:.72rem !important;
    line-height:1.45 !important;
    font-weight:700 !important;
}

/* ===== HANDICAP ===== */

.hawks-premium-handicap-box,
.hawks-premium-handicap-box.right{
    display:flex !important;
    flex-direction:column !important;
    align-items:center !important;

    width:100% !important;
    min-width:0 !important;

    margin:2px 0 0 !important;
    padding:0 !important;

    background:transparent !important;
    border:0 !important;
    outline:0 !important;
    box-shadow:none !important;

    text-align:center !important;
}

.hawks-premium-handicap-box small{
    display:none !important;
    margin:0 0 3px !important;
    padding:0 !important;

    font-size:11px !important;
    line-height:1 !important;
    font-weight:850 !important;

    color:#5d6979 !important;
}

.hawks-premium-handicap-box strong{
    display:inline-flex !important;
    align-items:center !important;
    justify-content:center !important;

    min-width:112px !important;
    min-height:32px !important;

    padding:2px 8px !important;

    border:0 !important;
    background:transparent !important;
    box-shadow:none !important;

    font-size:25px !important;
    line-height:1 !important;
    font-weight:950 !important;
}

/* 相手側 */
.hawks-premium-team:not(.right)
.hawks-premium-handicap-box strong{
    color:#1683e8 !important;
}

/* ホークス側 */
.hawks-premium-team.right
.hawks-premium-handicap-box strong{
    color:#ef2634 !important;
}

/* ===== CENTER SCORE ===== */

.hawks-premium-scoreline{
    align-self:start !important;
    text-align:center !important;
    padding-top:2px !important;
}

.hawks-premium-scoreline .numbers{
    font-size:58px !important;
    line-height:1 !important;
    font-weight:950 !important;
    letter-spacing:.02em !important;
    color:#07111f !important;
}

.hawks-premium-scoreline .hawks-num{
    color:#e0212f !important;
}

.hawks-premium-status{
    display:inline-flex !important;
    margin-top:10px !important;
    padding:5px 12px !important;

    border-radius:999px !important;
    background:#0a0e13 !important;
    color:#fff !important;

    font-size:.72rem !important;
    font-weight:900 !important;
}

.hawks-premium-venue{
    margin-top:21px !important;
    color:#111827 !important;
    font-size:15px !important;
    font-weight:900 !important;
}

.hawks-premium-time{
    margin-top:7px !important;
    color:#4b5563 !important;
    font-size:.72rem !important;
    font-weight:750 !important;
}

/* ===== MOBILE ===== */

@media screen and (max-width:600px){

    .hawks-premium-score{
        grid-template-columns:minmax(0,1fr) 92px minmax(0,1fr) !important;
        gap:6px !important;
        padding:14px 8px 16px !important;
    }

    .hawks-premium-team{
        grid-template-columns:66px minmax(0,1fr) !important;
        gap:5px !important;
    }

    .hawks-premium-team.right{
        grid-template-columns:minmax(0,1fr) 66px !important;
    }

    .hawks-premium-team-visual{
        width:66px !important;
    }

    .hawks-premium-team-logo{
        width:60px !important;
        height:60px !important;
    }

    .hawks-premium-team-name{
        font-size:13px !important;
    }

    .hawks-premium-team-sub{
        margin-top:2px !important;
        font-size:.43rem !important;
    }

    .hawks-premium-team-meta{
        margin-top:7px !important;
        font-size:.48rem !important;
    }

    .hawks-premium-team-record{
        margin-top:5px !important;
        font-size:.43rem !important;
    }

    .hawks-premium-handicap-box,
    .hawks-premium-handicap-box.right{
        margin-top:2px !important;
    }

    .hawks-premium-handicap-box small{
        margin-bottom:2px !important;
        font-size:.40rem !important;
        white-space:nowrap !important;
    }

    .hawks-premium-handicap-box strong{
        min-width:58px !important;
        min-height:22px !important;
        padding:1px 3px !important;
        font-size:.78rem !important;
        white-space:nowrap !important;
    }

    .hawks-premium-scoreline .numbers{
        font-size:1.8rem !important;
    }

    .hawks-premium-status{
        margin-top:6px !important;
        padding:4px 7px !important;
        font-size:.45rem !important;
    }

    .hawks-premium-venue{
        margin-top:13px !important;
        font-size:.52rem !important;
    }

    .hawks-premium-time{
        margin-top:4px !important;
        font-size:.43rem !important;
    }
}

/* =========================================================
   PREMIUM STARTING PITCHERS FINAL
   ========================================================= */

.hawks-premium-details.premium-details-three{
    grid-template-columns:repeat(3,1fr) !important;
}

.hawks-premium-starters{
    display:grid !important;
    grid-template-columns:minmax(0,1fr) 60px minmax(0,1fr) !important;
    align-items:center !important;
    gap:12px !important;

    margin:0 18px 18px !important;
    padding:14px !important;

    background:#fff !important;
    border:1px solid #e2e8ef !important;
    border-radius:15px !important;
    box-sizing:border-box !important;
}

.hawks-premium-starter-card{
    display:flex !important;
    align-items:center !important;
    gap:16px !important;

    min-height:105px !important;
    padding:10px 14px !important;

    background:linear-gradient(135deg,#fff,#f8fafc) !important;
    border-radius:13px !important;
    box-sizing:border-box !important;
}

.hawks-premium-starter-card.hawks{
    border-left:4px solid #e2b500 !important;
}

.hawks-premium-starter-card.opponent{
    border-left:4px solid #1683e8 !important;
}

.hawks-premium-pitcher-photo-wrap{
    width:84px !important;
    height:84px !important;
    min-width:84px !important;

    display:flex !important;
    align-items:center !important;
    justify-content:center !important;

    overflow:hidden !important;
    border-radius:50% !important;
    background:#eef3f7 !important;
}

.hawks-premium-pitcher-photo{
    width:100% !important;
    height:100% !important;
    object-fit:cover !important;
    object-position:center top !important;
}

.hawks-premium-pitcher-fallback{
    font-size:2rem !important;
}

.hawks-premium-starter-info{
    flex:1 !important;
    min-width:0 !important;
}

.hawks-premium-starter-label{
    margin-bottom:5px !important;

    color:#738197 !important;
    font-size:.68rem !important;
    line-height:1.2 !important;
    font-weight:850 !important;
}

.hawks-premium-starter-card.hawks
.hawks-premium-starter-label{
    color:#c38f00 !important;
}

.hawks-premium-starter-name{
    color:#111d2d !important;

    font-size:1.2rem !important;
    line-height:1.2 !important;
    font-weight:950 !important;
}

.hawks-premium-starter-meta{
    margin-top:7px !important;

    color:#66758a !important;
    font-size:.76rem !important;
    line-height:1.3 !important;
    font-weight:700 !important;
}

.hawks-premium-starter-vs{
    display:flex !important;
    align-items:center !important;
    justify-content:center !important;

    color:#111d2d !important;
    font-size:1.45rem !important;
    font-weight:950 !important;
}


/* ===== MOBILE ===== */

@media screen and (max-width:600px){

    .hawks-premium-details.premium-details-three{
        grid-template-columns:1fr !important;
    }

    .hawks-premium-starters{
        grid-template-columns:1fr !important;
        gap:8px !important;

        margin:0 10px 12px !important;
        padding:9px !important;
    }

    .hawks-premium-starter-vs{
        font-size:.75rem !important;
        height:14px !important;
    }

    .hawks-premium-starter-card{
        gap:10px !important;
        min-height:82px !important;
        padding:8px 10px !important;
    }

    .hawks-premium-pitcher-photo-wrap{
        width:62px !important;
        height:62px !important;
        min-width:62px !important;
    }

    .hawks-premium-starter-label{
        font-size:.57rem !important;
    }

    .hawks-premium-starter-name{
        font-size:.96rem !important;
    }

    .hawks-premium-starter-meta{
        margin-top:4px !important;
        font-size:.63rem !important;
    }
}

</style>
""", unsafe_allow_html=True)
# ===== /HAWKS AI MOBILE ALIGN FINAL =====


# ===== HAWKS MOBILE VISUAL FINAL TUNE =====
st.markdown(r"""

""", unsafe_allow_html=True)
# ===== /HAWKS MOBILE VISUAL FINAL TUNE =====


# ===== HAWKS MOBILE VISUAL FINAL TUNE =====
st.markdown(r"""

""", unsafe_allow_html=True)
# ===== /HAWKS MOBILE VISUAL FINAL TUNE =====

# ===== HAWKS HERO STUDIO CSS START =====
st.markdown(
    r"""
<style>
.hawks-hero {
  min-height: 260px;
  background-size: cover;
  background-position: 38.8% 71%;
  background-repeat: no-repeat;
}

.hawks-hero::before {
  background: linear-gradient(90deg,
    rgba(0, 0, 0, 0.5) 0%,
    rgba(0, 0, 0, 0) 68%
  );
}

@media (max-width: 600px) {
  .hawks-hero {
    min-height: 190px;
    background-size: cover;
    background-position: 50% 50%;
    overflow: hidden;
  }

  .hawks-hero::before {
    background: linear-gradient(90deg,
      rgba(0, 0, 0, 0.6) 0%,
      rgba(0, 0, 0, 0) 82%
    );
  }
}
</style>

<style id="hawks-hero-separation-fix">

/* HEROを独立ブロック化 */
.hawks-hero{
    margin-bottom:16px !important;
    border-radius:18px !important;
    overflow:hidden !important;
}

/* 試合情報を独立カード化 */
.hawks-premium-shell{
    margin-top:0 !important;
    border-radius:18px !important;
    overflow:hidden !important;
    box-shadow:0 14px 36px rgba(5,12,20,.18) !important;
}

/* スマホ */
@media (max-width:768px){
    .hawks-hero{
        margin-bottom:10px !important;
        border-radius:14px !important;
    }

    .hawks-premium-shell{
        border-radius:14px !important;
    }
}

</style>

""",
    unsafe_allow_html=True,
)
# ===== HAWKS HERO STUDIO CSS END =====


# ============================================================
# 💰 BET MANAGEMENT
# ============================================================

from pathlib import Path as BetPath
import json as bet_json

from bet_analytics import SORT_OPTIONS, calculate_hit_rate, sort_bets


def _bet_data_dir():
    return BetPath(DATA_DIR)


def _load_bet_json(filename, default):
    p = _bet_data_dir() / filename
    try:
        if p.exists():
            return bet_json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        pass
    return default


def _save_bet_json(filename, data):
    p = _bet_data_dir() / filename
    p.write_text(
        bet_json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


st.markdown("---")
st.markdown("## 💰 ベット収支管理")

_bet_summary = _load_bet_json("bet_summary.json", {})
_bet_records = _load_bet_json("bet_records.json", [])

_wins, _decided_bets, _hit_rate = calculate_hit_rate(_bet_records)
_metric_col, _sort_col = st.columns([1, 2])
with _metric_col:
    st.metric(
        "的中率",
        f"{_hit_rate:.1f}%" if _hit_rate is not None else "-",
        help="確定したWIN／LOSSのみで計算（PUSH・未確定は除外）",
    )
with _sort_col:
    _bet_sort_option = st.selectbox(
        "履歴の並び順",
        SORT_OPTIONS,
        key="bet_management_sort",
    )

_display_bet_records = sort_bets(_bet_records, _bet_sort_option)

_week_profit = int(
    _bet_summary.get("weekly_unsettled_profit", 0) or 0
)

_week_start = _bet_summary.get("week_start", "-")
_week_end = _bet_summary.get("week_end", "-")

if _week_profit > 0:
    _profit_text = f"+¥{_week_profit:,}"
elif _week_profit < 0:
    _profit_text = f"-¥{abs(_week_profit):,}"
else:
    _profit_text = "¥0"

st.markdown(
    f"""
    <div style="
        padding:18px 20px;
        margin:10px 0 18px 0;
        border-radius:16px;
        background:linear-gradient(145deg,#07111c,#0d1b2a);
        color:white;
        box-shadow:0 8px 24px rgba(0,0,0,.18);
    ">
        <div style="font-size:13px;opacity:.72;">
            {_week_start} 〜 {_week_end}
        </div>
        <div style="font-size:15px;margin-top:4px;">
            今週の未精算収支
        </div>
        <div style="
            font-size:34px;
            font-weight:800;
            margin-top:4px;
        ">
            {_profit_text}
        </div>
    </div>
    """,
    unsafe_allow_html=True
)


_result_label = {
    "win": "✅ WIN",
    "loss": "❌ LOSS",
    "push": "➖ PUSH",
    None: "⏳ 未確定"
}


for idx, bet in enumerate(_display_bet_records):

    date = bet.get("date", "")
    time = bet.get("time", "")
    team = bet.get("team", "")
    opponent = bet.get("opponent", "")
    handicap = bet.get("handicap", 0)
    units = bet.get("bet_units", 0)

    status = bet.get("status", "pending")
    result = bet.get("result")

    team_score = bet.get("team_score")
    opponent_score = bet.get("opponent_score")
    profit = int(bet.get("profit", 0) or 0)
    settled = bool(bet.get("settled", False))

    if profit > 0:
        profit_text = f"+¥{profit:,}"
    elif profit < 0:
        profit_text = f"-¥{abs(profit):,}"
    else:
        profit_text = "¥0"

    if team_score is None or opponent_score is None:
        score_text = "試合結果待ち"
    else:
        score_text = f"{team_score} - {opponent_score}"

    result_text = _result_label.get(result, "⏳ 未確定")

    with st.container(border=True):

        c1, c2, c3 = st.columns([2.2, 1.2, 1.2])

        with c1:
            st.markdown(
                f"**{date}　{time}**  \n"
                f"### {team} vs {opponent}"
            )

            st.caption(
                f"ハンデ {handicap} ｜ ベット {units}"
            )

        with c2:
            st.markdown("**試合結果**")
            st.markdown(f"### {score_text}")
            st.markdown(result_text)

        with c3:
            st.markdown("**収支**")

            if status == "final":
                st.markdown(f"### {profit_text}")
            else:
                st.markdown("### 未確定")

        if status == "final":

            if settled:
                st.success("精算済み")

                if st.button(
                    "未精算へ戻す",
                    key=f"bet_unsettle_{idx}"
                ):
                    bet["settled"] = False
                    _save_bet_json(
                        "bet_records.json",
                        _bet_records
                    )
                    st.rerun()

            else:
                if st.button(
                    "✅ 精算済みにする",
                    key=f"bet_settle_{idx}",
                    type="primary"
                ):
                    bet["settled"] = True
                    _save_bet_json(
                        "bet_records.json",
                        _bet_records
                    )

                    # summaryも即時再計算
                    weekly_total = 0

                    for b in _bet_records:
                        try:
                            if (
                                not b.get("settled", False)
                                and b.get("status") == "final"
                            ):
                                bd = b.get("date", "")

                                if (
                                    _week_start != "-"
                                    and _week_end != "-"
                                    and _week_start <= bd <= _week_end
                                ):
                                    weekly_total += int(
                                        b.get("profit", 0) or 0
                                    )
                        except Exception:
                            pass

                    _bet_summary["weekly_unsettled_profit"] = weekly_total

                    _save_bet_json(
                        "bet_summary.json",
                        _bet_summary
                    )

                    st.rerun()
