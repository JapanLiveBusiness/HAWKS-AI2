"""Login screen matching the existing MY AI BASEBALL visual design."""

import streamlit as st


LOGIN_CSS = """
<style>
[data-testid="stSidebar"], [data-testid="stHeader"], footer {display:none !important;}
[data-testid="stAppViewContainer"] {
    background:radial-gradient(ellipse at 87% 25%, #20270c 0%, #080d09 42%, #050906 75%) !important;
    color:#f7faf7 !important;
}
.block-container {
    max-width:828px !important;
    padding:clamp(32px, 15vh, 154px) 24px 48px !important;
}
.st-key-auth0-login-card {
    box-sizing:border-box;
    background:#0a100d;
    border:1px solid #43551a;
    border-left:6px solid #d6ff32;
    padding:84px;
    gap:0 !important;
}
.auth-login-brand {color:#d6ff32;font:500 16px/1.5 system-ui,sans-serif;letter-spacing:.25em;}
.auth-login-title {color:#f7faf7 !important;font:900 italic clamp(48px,8vw,100px)/1.1 system-ui,sans-serif !important;margin:54px 0 26px !important;padding:0 !important;}
.auth-login-subtitle {color:#829099;font:400 17px/1.7 system-ui,sans-serif;margin:0 0 80px;}
.st-key-auth0-login-card button {
    width:100%;min-height:98px;background:#d6ff32 !important;color:#0a100d !important;
    border:2px solid #d6ff32 !important;border-radius:0 !important;
}
.st-key-auth0-login-card button p {font:850 30px/1.35 system-ui,sans-serif !important;}
.st-key-auth0-login-card button:hover {background:#e1ff68 !important;}
.st-key-auth0-login-card button:focus-visible {outline:3px solid #fff;outline-offset:5px;}
.auth-login-note {color:#829099;font:400 13px/1.8 system-ui,sans-serif;text-align:center;margin:26px 0 0;}
@media(max-width:600px) {
    .block-container {padding:40px 16px !important;}
    .st-key-auth0-login-card {padding:40px 24px;}
    .auth-login-brand {font-size:12px;}
    .auth-login-title {margin-top:36px !important;}
    .auth-login-subtitle {font-size:14px;margin-bottom:48px;}
    .st-key-auth0-login-card button {min-height:76px;}
    .st-key-auth0-login-card button p {font-size:22px !important;}
}
</style>
"""


def render_login_screen() -> None:
    st.markdown(LOGIN_CSS, unsafe_allow_html=True)
    with st.container(key="auth0-login-card"):
        st.markdown(
            '<div class="auth-login-brand">MY AI BASEBALL</div>'
            '<h1 class="auth-login-title">LOGIN</h1>'
            '<p class="auth-login-subtitle">GoogleなどのSNSアカウントで安全にログイン</p>',
            unsafe_allow_html=True,
        )
        if st.button("Auth0でログイン", type="primary", width="stretch", key="auth0_login"):
            st.login("auth0")
        st.markdown(
            '<p class="auth-login-note">収支・BET・繰越データはログインアカウント別に保存されます</p>',
            unsafe_allow_html=True,
        )
