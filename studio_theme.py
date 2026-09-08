import html
import streamlit as st

from auth_session import render_account_controls, require_auth0


STUDIO_CSS = r'''
<style>
:root {
  --studio-bg: #f4f0e8;
  --studio-paper: #fffdf8;
  --studio-ink: #171717;
  --studio-ink-2: #232323;
  --studio-gold: #f1c40f;
  --studio-gold-2: #c99816;
  --studio-line: #ddd5c8;
  --studio-muted: #746f66;
}
[data-testid="stHeader"], [data-testid="stToolbar"], footer {display:none !important;}
[data-testid="stAppViewContainer"] {background:var(--studio-bg) !important; color:var(--studio-ink) !important;}
.block-container {max-width:1320px !important; padding:0 24px 56px !important;}
[data-testid="stSidebar"] {background:#181818;}
[data-testid="stSidebar"] a, [data-testid="stSidebar"] a span {color:#e9e9e9 !important;}
[data-testid="stSidebar"] a:hover, [data-testid="stSidebar"] a:hover span,
[data-testid="stSidebar"] a[aria-current="page"], [data-testid="stSidebar"] a[aria-current="page"] span {color:var(--studio-gold) !important;}
[data-testid="stSidebar"] a:focus-visible {outline:2px solid var(--studio-gold);outline-offset:2px;}
[data-testid="stSidebarNavItems"] li a::before,
[data-testid="stSidebarNav"] li a::before {
  content:"⚾"; display:inline-flex; width:1.6em; margin-right:.55em;
  align-items:center; justify-content:center; font-size:1rem; line-height:1;
}
[data-testid="stSidebarNavItems"] li:nth-child(1) a::before,
[data-testid="stSidebarNav"] li:nth-child(1) a::before {content:"🏠";}
[data-testid="stSidebarNavItems"] li:nth-child(2) a::before,
[data-testid="stSidebarNav"] li:nth-child(2) a::before {content:"📅";}
[data-testid="stSidebarNavItems"] li:nth-child(3) a::before,
[data-testid="stSidebarNav"] li:nth-child(3) a::before {content:"🧠";}
[data-testid="stSidebarNavItems"] li:nth-child(4) a::before,
[data-testid="stSidebarNav"] li:nth-child(4) a::before {content:"✅";}
[data-testid="stSidebarNavItems"] li:nth-child(5) a::before,
[data-testid="stSidebarNav"] li:nth-child(5) a::before {content:"📝";}
[data-testid="stSidebarNavItems"] li:nth-child(6) a::before,
[data-testid="stSidebarNav"] li:nth-child(6) a::before {content:"📈";}
h1,h2,h3,h4,p,label,span {font-family:Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;}
h1,h2,h3 {color:var(--studio-ink) !important;}

.studio-topbar {
  margin:0 -24px 24px; min-height:70px; padding:0 28px; background:#151515; color:#fff;
  border-bottom:2px solid rgba(241,196,15,.42); display:flex; align-items:center; justify-content:space-between; gap:20px;
}
.studio-brand {display:flex; align-items:center; gap:12px;min-width:250px;}
.studio-nav{display:flex;align-items:center;justify-content:center;gap:18px;flex:1}
.studio-nav a{font-size:9px;color:#aaa;text-decoration:none;white-space:nowrap;font-weight:800}
.studio-nav a:hover{color:var(--studio-gold)}
.studio-mark {width:38px;height:38px;border-radius:11px;background:var(--studio-gold);color:#101010;display:flex;align-items:center;justify-content:center;font-size:20px;font-weight:1000;font-style:italic;}
.studio-brand-title {font-weight:950;letter-spacing:.14em;font-size:14px;line-height:1.1;}
.studio-brand-sub {font-size:7px;color:#bcbcbc;letter-spacing:.38em;margin-top:5px;}
.studio-badge {font-size:9px;border:1px solid #555;border-radius:999px;padding:7px 11px;color:#e9e9e9;white-space:nowrap;}

.studio-hero {
  background:linear-gradient(132deg,#161616 0%,#1d1a12 55%,#3a2c10 100%); color:#fff;
  border:1px solid #2b2b2b; border-radius:20px; padding:30px 34px; margin-bottom:22px; position:relative; overflow:hidden;
}
.studio-hero:after {content:"";position:absolute;inset:0;background-image:linear-gradient(rgba(255,255,255,.025) 1px,transparent 1px),linear-gradient(90deg,rgba(255,255,255,.025) 1px,transparent 1px);background-size:36px 36px;pointer-events:none;}
.studio-kicker {font-size:9px;letter-spacing:.28em;color:#f4cd45;font-weight:900;text-transform:uppercase;position:relative;z-index:1;}
.studio-title {font-size:38px;line-height:1.1;font-weight:850;margin:8px 0 9px;letter-spacing:-.03em;position:relative;z-index:1;}
.studio-title span {color:var(--studio-gold);}
.studio-subtitle {font-size:13px;color:#c7c3ba;max-width:780px;line-height:1.7;position:relative;z-index:1;}

.studio-section-label {font-size:9px;letter-spacing:.25em;color:#a77e11;font-weight:950;margin:18px 0 4px;}
.studio-section-title {font-family:Georgia,serif;font-size:28px;margin:0 0 12px;color:var(--studio-ink);}
.studio-card {background:var(--studio-paper);border:1px solid var(--studio-line);border-radius:14px;padding:18px;box-shadow:0 10px 28px rgba(35,29,18,.05);}
.studio-card-dark {background:#191919;color:#fff;border:1px solid #2e2e2e;border-radius:14px;padding:18px;}
.studio-note {font-size:11px;color:var(--studio-muted);line-height:1.7;}
.studio-rank {width:38px;height:38px;border-radius:50%;background:#191919;color:var(--studio-gold);display:inline-flex;align-items:center;justify-content:center;font-weight:900;}
.studio-pick {font-size:23px;font-weight:900;}

/* Streamlit native controls */
div[data-testid="stForm"], div[data-testid="stExpander"] {background:var(--studio-paper);border-color:var(--studio-line) !important;border-radius:14px !important;}
div[data-testid="stMetric"] {background:var(--studio-paper);border:1px solid var(--studio-line);padding:14px;border-radius:12px;}
div[data-testid="stMetricValue"] {color:var(--studio-ink);font-weight:850;}
.stButton>button, button[kind="primary"] {background:#171717 !important;color:var(--studio-gold) !important;border:1px solid #171717 !important;border-radius:999px !important;font-weight:900 !important;}
.stButton>button:hover, button[kind="primary"]:hover {border-color:var(--studio-gold) !important;box-shadow:0 0 0 2px rgba(241,196,15,.15) !important;}
[data-testid="stPageLink"] a {background:var(--studio-paper) !important;color:var(--studio-ink) !important;border:1px solid var(--studio-line) !important;border-radius:999px !important;font-weight:800 !important;}
[data-testid="stPageLink"] a:hover {border-color:var(--studio-gold) !important;}
[data-testid="stDataFrame"], [data-testid="stTable"] {background:var(--studio-paper);border-radius:12px;overflow:hidden;}

@media (max-width: 760px) {
  .block-container {padding:0 12px 38px !important;}
  .studio-topbar {margin:0 -12px 18px;padding:0 14px;}
  .studio-badge {display:none;}
  .studio-nav{overflow-x:auto;justify-content:flex-start;gap:14px;padding:0 4px}
  .studio-nav a{font-size:8px}
  .studio-hero {padding:24px 20px;}
  .studio-title {font-size:31px;}
}
</style>
'''


def apply_studio_theme():
    st.markdown(STUDIO_CSS, unsafe_allow_html=True)


def render_topbar(section="STUDIO"):
    user = require_auth0()
    safe_section = html.escape(str(section))
    st.markdown(
        f'''
<div class="studio-topbar">
  <div class="studio-brand">
    <div class="studio-mark">M</div>
    <div>
      <div class="studio-brand-title">AI BASEBALL STUDIO</div>
      <div class="studio-brand-sub">GAME INTELLIGENCE</div>
    </div>
  </div>
  <nav class="studio-nav"><a href="/" target="_self">HOME</a><a href="/試合" target="_self">GAMES</a><a href="/本日のAI予想" target="_self">AI PREDICTION</a><a href="/予想結果" target="_self">RESULTS</a><a href="/BET入力" target="_self">BET</a><a href="/収支マップ" target="_self">PERFORMANCE</a><a href="/球団別詳細" target="_self">TEAMS</a><a href="/AI詳細" target="_self">AI DETAIL</a></nav>
  <div class="studio-badge">{safe_section}</div>
</div>
''',
        unsafe_allow_html=True,
    )
    render_account_controls(user)
    return user


def render_hero(title, subtitle, kicker="AI BASEBALL STUDIO", accent=None):
    safe_title = html.escape(str(title))
    safe_subtitle = html.escape(str(subtitle))
    safe_kicker = html.escape(str(kicker))
    if accent and accent in safe_title:
        safe_title = safe_title.replace(accent, f"<span>{accent}</span>", 1)
    st.markdown(
        f'''
<div class="studio-hero">
  <div class="studio-kicker">{safe_kicker}</div>
  <div class="studio-title">{safe_title}</div>
  <div class="studio-subtitle">{safe_subtitle}</div>
</div>
''',
        unsafe_allow_html=True,
    )


def render_section(label, title):
    st.markdown(
        f'<div class="studio-section-label">{html.escape(str(label))}</div>'
        f'<div class="studio-section-title">{html.escape(str(title))}</div>',
        unsafe_allow_html=True,
    )


def render_nav_links():
    """Navigation is rendered in the shared top bar."""
    return None
