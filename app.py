import streamlit as st
import urllib.parse
import requests
from utils.strava import exchange_token, refresh_access_token, fetch_activities
from utils.session import init_session

st.set_page_config(
    page_title="PaceForge",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── custom CSS ──────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bebas+Neue&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');

html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'Bebas Neue', sans-serif; letter-spacing: 2px; }
[data-testid="stMetricValue"] { font-family: 'DM Mono', monospace; font-size: 2rem !important; }
.stButton > button {
    background: #e8ff47; color: #0d0d0f;
    font-family: 'Bebas Neue', sans-serif;
    font-size: 18px; letter-spacing: 3px;
    border: none; border-radius: 2px;
    padding: 10px 28px;
    transition: all 0.2s;
}
.stButton > button:hover { background: #fff; transform: translateY(-1px); }
</style>
""", unsafe_allow_html=True)

# ── session init ─────────────────────────────────────────────────────────────
init_session()

CLIENT_ID     = st.secrets["STRAVA_CLIENT_ID"]
CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
REDIRECT_URI  = st.secrets["STRAVA_REDIRECT_URI"]

# ── handle OAuth callback (code in URL) ──────────────────────────────────────
params = st.query_params
if "code" in params and not st.session_state.get("access_token"):
    code = params["code"]
    token_data = exchange_token(CLIENT_ID, CLIENT_SECRET, code)
    if token_data:
        st.session_state.access_token   = token_data["access_token"]
        st.session_state.refresh_token  = token_data["refresh_token"]
        st.session_state.expires_at     = token_data["expires_at"]
        st.session_state.athlete        = token_data.get("athlete", {})
        st.query_params.clear()
        st.rerun()

# ── refresh token if expired ─────────────────────────────────────────────────
if st.session_state.get("refresh_token"):
    import time
    if time.time() > st.session_state.get("expires_at", 0) - 300:
        new_tokens = refresh_access_token(
            CLIENT_ID, CLIENT_SECRET, st.session_state["refresh_token"]
        )
        if new_tokens:
            st.session_state.access_token  = new_tokens["access_token"]
            st.session_state.refresh_token = new_tokens["refresh_token"]
            st.session_state.expires_at    = new_tokens["expires_at"]

# ── NOT LOGGED IN ────────────────────────────────────────────────────────────
if not st.session_state.get("access_token"):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("# ⚡ PaceForge")
        st.markdown("### Race Predictor & Training Analytics")
        st.markdown("---")
        st.markdown("""
        **Co dostaniesz po połączeniu ze Stravą:**
        - 📈 Prognoza czasu na 5 dystansach (VDOT / Riegel)
        - 🗺️ Race strategy — pacing plan km po km
        - 🫀 Strefy tętna i tempa (Daniels / Karvonen)
        - 📊 Progresja VDOT w czasie
        - 🏆 Najlepsze wyniki na dystansach
        - 😮‍💨 Detekcja formy i zmęczenia (ATL/CTL/TSB)
        - ❤️ Analiza aerobic fitness (HR drift)
        """)
        st.markdown("")

        auth_url = (
            f"https://www.strava.com/oauth/authorize"
            f"?client_id={CLIENT_ID}"
            f"&response_type=code"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
            f"&approval_prompt=auto"
            f"&scope=read,activity:read_all"
        )
        st.link_button("🔗  Połącz ze Stravą", auth_url, use_container_width=True)
        st.caption("Tylko odczyt — aplikacja nie modyfikuje Twoich danych.")
    st.stop()

# ── LOGGED IN — sidebar ───────────────────────────────────────────────────────
athlete = st.session_state.get("athlete", {})
with st.sidebar:
    st.markdown(f"### 👋 {athlete.get('firstname', 'Atleta')} {athlete.get('lastname','')}")
    st.caption(f"📍 {athlete.get('city','')}, {athlete.get('country','')}")
    st.markdown("---")

    st.markdown("**Nawigacja**")
    page = st.radio(
        "",
        ["🏠 Dashboard", "📈 Prognozy", "🗺️ Race Strategy", "📊 Analiza historyczna", "🫀 Strefy"],
        label_visibility="collapsed",
    )
    st.markdown("---")

    n_activities = st.slider("Aktywności do pobrania", 50, 200, 100, 50)
    if st.button("🔄 Odśwież dane", use_container_width=True):
        st.session_state.pop("activities", None)

    st.markdown("---")
    if st.button("🚪 Wyloguj", use_container_width=True):
        for k in ["access_token", "refresh_token", "expires_at", "athlete", "activities"]:
            st.session_state.pop(k, None)
        st.rerun()

# ── fetch activities (cached in session) ──────────────────────────────────────
if "activities" not in st.session_state:
    with st.spinner("Pobieranie aktywności ze Stravy…"):
        acts = fetch_activities(st.session_state["access_token"], n_activities)
        st.session_state["activities"] = acts

# ── page routing ──────────────────────────────────────────────────────────────
if   "Dashboard"          in page: from pages import dashboard;  dashboard.show()
elif "Prognozy"           in page: from pages import predictions; predictions.show()
elif "Race Strategy"      in page: from pages import strategy;   strategy.show()
elif "Analiza"            in page: from pages import history;    history.show()
elif "Strefy"             in page: from pages import zones;      zones.show()
