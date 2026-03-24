import streamlit as st
import urllib.parse
import time
import requests

st.set_page_config(
    page_title="PaceForge",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
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
    padding: 10px 28px; transition: all 0.2s;
}
.stButton > button:hover { background: #fff; transform: translateY(-1px); }
</style>
""", unsafe_allow_html=True)

# ── session defaults — ALWAYS before any session_state reads ─────────────────
_DEFAULTS = {
    "access_token":  None,
    "refresh_token": None,
    "expires_at":    0,
    "athlete":       {},
    "activities":    None,
    "hrmax":         185,
    "hrrest":        50,
    "n_activities":  100,
}
for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── secrets ───────────────────────────────────────────────────────────────────
try:
    CLIENT_ID     = st.secrets["STRAVA_CLIENT_ID"]
    CLIENT_SECRET = st.secrets["STRAVA_CLIENT_SECRET"]
    REDIRECT_URI  = st.secrets["STRAVA_REDIRECT_URI"]
except Exception:
    st.error(
        "Brak konfiguracji! Dodaj w Streamlit Cloud → Settings → Secrets:\n\n"
        "```toml\n"
        'STRAVA_CLIENT_ID     = "123456"\n'
        'STRAVA_CLIENT_SECRET = "abc..."\n'
        'STRAVA_REDIRECT_URI  = "https://TWOJA-APPKA.streamlit.app"\n'
        "```"
    )
    st.stop()

# ── OAuth callback ────────────────────────────────────────────────────────────
params = st.query_params
if "code" in params and not st.session_state["access_token"]:
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
              "code": params["code"], "grant_type": "authorization_code"},
        timeout=10,
    )
    if resp.ok:
        d = resp.json()
        st.session_state["access_token"]  = d["access_token"]
        st.session_state["refresh_token"] = d["refresh_token"]
        st.session_state["expires_at"]    = d["expires_at"]
        st.session_state["athlete"]       = d.get("athlete", {})
        st.session_state["activities"]    = None
        st.query_params.clear()
        st.rerun()
    else:
        st.error(f"OAuth error: {resp.text}")
        st.stop()

# ── token refresh ─────────────────────────────────────────────────────────────
if st.session_state["refresh_token"] and time.time() > st.session_state["expires_at"] - 300:
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={"client_id": CLIENT_ID, "client_secret": CLIENT_SECRET,
              "refresh_token": st.session_state["refresh_token"],
              "grant_type": "refresh_token"},
        timeout=10,
    )
    if resp.ok:
        d = resp.json()
        st.session_state["access_token"]  = d["access_token"]
        st.session_state["refresh_token"] = d["refresh_token"]
        st.session_state["expires_at"]    = d["expires_at"]

# ── NOT LOGGED IN ─────────────────────────────────────────────────────────────
if not st.session_state["access_token"]:
    _, col, _ = st.columns([1, 2, 1])
    with col:
        st.markdown("# ⚡ PaceForge")
        st.markdown("### Race Predictor & Training Analytics")
        st.markdown("---")
        st.markdown("""
**Co dostaniesz po połączeniu ze Stravą:**
- 📈 Prognoza czasu na 5 dystansach (VDOT / Riegel)
- 🗺️ Race strategy — pacing plan km po km
- 🫀 Strefy tętna i tempa (Daniels / Karvonen)
- 📊 Progresja VDOT w czasie + trend miesięczny
- 🏆 Najlepsze wyniki na dystansach
- 😮‍💨 Detekcja formy i zmęczenia (ATL/CTL/TSB)
- ❤️ Analiza aerobic fitness (HR vs tempo)
        """)
        auth_url = (
            "https://www.strava.com/oauth/authorize"
            f"?client_id={CLIENT_ID}&response_type=code"
            f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
            "&approval_prompt=auto&scope=read,activity:read_all"
        )
        st.link_button("🔗  Połącz ze Stravą", auth_url, use_container_width=True)
        st.caption("Tylko odczyt — aplikacja nigdy nie modyfikuje Twoich danych.")
    st.stop()

# ══════════════════════════════════════════════════════════════════════════════
# LOGGED IN
# ══════════════════════════════════════════════════════════════════════════════
athlete = st.session_state["athlete"]
with st.sidebar:
    st.markdown(f"### 👋 {athlete.get('firstname','Atleta')} {athlete.get('lastname','')}")
    st.caption(f"📍 {athlete.get('city','')}, {athlete.get('country','')}")
    st.markdown("---")

    page = st.radio(
        "Nawigacja",
        ["🏠 Dashboard", "📈 Prognozy", "🗺️ Race Strategy", "📊 Analiza historyczna", "🫀 Strefy"],
    )
    st.markdown("---")

    n_act = st.slider("Aktywności do pobrania", 50, 200, int(st.session_state["n_activities"]), 50)
    st.session_state["n_activities"] = n_act

    if st.button("🔄 Odśwież dane", use_container_width=True):
        st.session_state["activities"] = None
        st.rerun()

    st.markdown("---")
    # HR settings — use number_input with explicit value (not key= to avoid conflicts)
    hrmax_val  = st.number_input("HR max (bpm)",     140, 220, int(st.session_state["hrmax"]))
    hrrest_val = st.number_input("HR spoczynkowe",    30, 100, int(st.session_state["hrrest"]))
    st.session_state["hrmax"]  = hrmax_val
    st.session_state["hrrest"] = hrrest_val

    st.markdown("---")
    if st.button("🚪 Wyloguj", use_container_width=True):
        for k, v in _DEFAULTS.items():
            st.session_state[k] = v
        st.rerun()

# ── fetch activities ──────────────────────────────────────────────────────────
if st.session_state["activities"] is None:
    with st.spinner("Pobieranie aktywności ze Stravy…"):
        from utils.strava import fetch_activities
        st.session_state["activities"] = fetch_activities(
            st.session_state["access_token"],
            st.session_state["n_activities"],
        )

# ── routing ───────────────────────────────────────────────────────────────────
if "Dashboard" in page:
    from pages import dashboard;   dashboard.show()
elif "Prognozy" in page:
    from pages import predictions; predictions.show()
elif "Race Strategy" in page:
    from pages import strategy;    strategy.show()
elif "Analiza" in page:
    from pages import history;     history.show()
elif "Strefy" in page:
    from pages import zones;       zones.show()
