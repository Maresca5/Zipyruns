"""Race Strategy — km-by-km pacing plan."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils.strava import vdot_to_race_time, get_training_paces
from utils.session import secs_to_mmss, secs_to_hhmmss

RACES = [
    ("5 km",       5.0),
    ("10 km",      10.0),
    ("Półmaraton", 21.0975),
    ("Maraton",    42.195),
]

ZONE_COLORS = {
    "rep":       "#ff6b47",
    "interval":  "#ffb347",
    "threshold": "#e8ff47",
    "marathon":  "#47ffb0",
    "easy":      "#6bcfff",
}
ZONE_LABELS = {
    "rep": "Rep", "interval": "Interval", "threshold": "Threshold",
    "marathon": "Marathon", "easy": "Easy",
}


def show():
    st.title("🗺️ Race Strategy")

    df: pd.DataFrame = st.session_state.get("activities", pd.DataFrame())
    vdot = None
    if not df.empty:
        vdot = df["vdot"].dropna().head(5).mean()

    # ── Controls ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    dist_name = col1.selectbox("Dystans", [r[0] for r in RACES], index=2)
    dist_km   = next(r[1] for r in RACES if r[0] == dist_name)

    vdot_input = col2.number_input("VDOT", min_value=25.0, max_value=85.0,
                                   value=float(round(vdot, 1)) if vdot else 45.0, step=0.5)

    strategy = col3.selectbox("Strategia tempa", [
        "Even splits",
        "Negative split (ostatnie km szybsze)",
        "Positive split (klasyczny start)",
        "Race profile (sag w środku)",
    ])

    adj_pct = col4.slider("Korekta celu", -10, 10, 0, 1, format="%d%%")

    # ── Compute ───────────────────────────────────────────────────────────────
    base_secs = vdot_to_race_time(vdot_input, dist_km)
    target_secs = base_secs * (1 + adj_pct / 100)
    base_pace = target_secs / dist_km  # secs/km average

    step = 1.0 if dist_km >= 5 else 0.5
    segments = []
    km = 0.0
    while km < dist_km - 0.001:
        end = min(km + step, dist_km)
        segments.append((km, end, end - km))
        km = end

    def multiplier(frac):
        if "Negative" in strategy:
            return 1.03 - 0.06 * frac
        if "Positive" in strategy:
            return 0.97 + 0.06 * frac
        if "profile" in strategy:
            if frac < 0.1:   return 0.97
            if frac < 0.5:   return 1.01
            if frac < 0.85:  return 1.025
            return 0.975
        return 1.0  # even

    paces_zones = get_training_paces(vdot_input)

    def get_zone(pace_s_km):
        for key in ["rep", "interval", "threshold", "marathon", "easy"]:
            if pace_s_km <= paces_zones[key]["pace_hi"]:
                return key
        return "easy"

    rows = []
    elapsed = 0.0
    for i, (frm, to, length) in enumerate(segments):
        frac = (i + 0.5) / len(segments)
        pace = base_pace * multiplier(frac)
        seg_time = pace * length
        elapsed += seg_time
        zone = get_zone(pace)
        rows.append({
            "Km": f"{frm:.1f}–{to:.1f}",
            "Tempo": secs_to_mmss(pace) + "/km",
            "Czas odcinka": secs_to_mmss(seg_time),
            "Suma": secs_to_hhmmss(elapsed),
            "Strefa": ZONE_LABELS[zone],
            "_pace": pace,
            "_zone": zone,
            "_elapsed": elapsed,
            "_km_end": to,
        })

    # ── Summary metrics ───────────────────────────────────────────────────────
    st.markdown("---")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Cel czasowy",  secs_to_hhmmss(target_secs))
    m2.metric("Tempo średnie", secs_to_mmss(base_pace) + "/km")
    m3.metric("VDOT",         f"{vdot_input:.1f}")
    m4.metric("Korekta",      f"{adj_pct:+d}%")

    # ── Pacing chart ──────────────────────────────────────────────────────────
    fig = go.Figure()
    for zone, color in ZONE_COLORS.items():
        zone_rows = [r for r in rows if r["_zone"] == zone]
        if zone_rows:
            fig.add_trace(go.Bar(
                x=[r["_km_end"] for r in zone_rows],
                y=[r["_pace"] for r in zone_rows],
                name=ZONE_LABELS[zone],
                marker_color=color,
                width=[r["_km_end"] - float(r["Km"].split("–")[0]) for r in zone_rows],
                hovertemplate="<b>%{customdata}</b><br>%{text}<extra></extra>",
                text=[r["Tempo"] for r in zone_rows],
                customdata=[r["Km"] + " km" for r in zone_rows],
            ))
    fig.update_yaxes(autorange="reversed", title="Tempo (sek/km)", gridcolor="#2a2a35")
    fig.update_xaxes(title="km", gridcolor="#2a2a35")
    fig.update_layout(**_dark("Pacing plan — tempo po km"), barmode="overlay")
    st.plotly_chart(fig, use_container_width=True)

    # ── Splits table ──────────────────────────────────────────────────────────
    display_df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # ── Export hint ───────────────────────────────────────────────────────────
    csv = display_df.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Pobierz CSV", csv, "race_strategy.csv", "text/csv")


def _dark(title=""):
    return dict(
        title=title,
        plot_bgcolor="#0d0d0f", paper_bgcolor="#15151a",
        font_color="#f0f0f5",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=36, b=0),
    )
