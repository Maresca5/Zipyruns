"""Race predictions page — VDOT + Riegel from best recent effort."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from utils.strava import vdot_to_race_time, riegel_predict
from utils.session import secs_to_mmss, secs_to_hhmmss, now

RACES = [
    ("1 mile",    1.60934),
    ("5 km",      5.0),
    ("10 km",     10.0),
    ("Półmaraton",21.0975),
    ("Maraton",   42.195),
]


def show():
    st.title("📈 Prognozy czasów")

    df: pd.DataFrame = st.session_state.get("activities", pd.DataFrame())
    if df.empty:
        st.warning("Brak danych — połącz Stravę.")
        return

    # ── Source of prediction ─────────────────────────────────────────────────
    st.subheader("Podstawa prognozy")
    col1, col2 = st.columns([2, 1])

    with col1:
        mode = st.radio("Źródło", ["Najlepszy wysiłek ze Stravy", "Wpisz czas ręcznie"], horizontal=True)

    if mode == "Najlepszy wysiłek ze Stravy":
        window = col2.selectbox("Okno czasowe", ["30 dni", "90 dni", "6 miesięcy", "Wszystko"])
        days_map = {"30 dni": 30, "90 dni": 90, "6 miesięcy": 180, "Wszystko": 9999}
        days = days_map[window]
        cutoff = now() - pd.Timedelta(days=days)
        recent = df[df["date"] >= cutoff].dropna(subset=["vdot"])
        if recent.empty:
            st.warning("Brak danych w wybranym oknie.")
            return
        best_row = recent.loc[recent["vdot"].idxmax()]
        vdot = best_row["vdot"]
        ref_dist = best_row["dist_km"]
        ref_time = best_row["duration_s"]
        st.info(
            f"Najlepszy wysiłek: **{best_row['name']}** | "
            f"{ref_dist:.2f} km | {secs_to_hhmmss(ref_time)} | "
            f"VDOT **{vdot:.1f}**"
        )
    else:
        c1, c2, c3, c4 = st.columns(4)
        dist_name = c1.selectbox("Dystans", [r[0] for r in RACES], index=2)
        ref_dist = next(r[1] for r in RACES if r[0] == dist_name)
        hh = c2.number_input("Godz", 0, 9, 0)
        mm = c3.number_input("Min",  0, 59, 45)
        ss = c4.number_input("Sek",  0, 59, 0)
        ref_time = hh * 3600 + mm * 60 + ss
        if ref_time == 0:
            st.stop()
        from utils.strava import _estimate_vdot
        vdot = _estimate_vdot(ref_dist, ref_time) or 40.0
        st.info(f"Wyliczony VDOT: **{vdot:.1f}**")

    st.markdown("---")

    # ── Prediction table ─────────────────────────────────────────────────────
    st.subheader("Prognozy")
    cols = st.columns(len(RACES))
    for col, (name, km) in zip(cols, RACES):
        t_daniels = vdot_to_race_time(vdot, km)
        t_riegel  = riegel_predict(ref_dist, ref_time, km)
        t_avg     = (t_daniels + t_riegel) / 2
        pace      = t_avg / km

        col.metric(name, secs_to_hhmmss(t_avg) if km > 5 else secs_to_mmss(t_avg))
        col.caption(f"Tempo: {secs_to_mmss(pace)}/km")

    # ── Chart: pace vs distance ───────────────────────────────────────────────
    dists  = [r[1] for r in RACES]
    labels = [r[0] for r in RACES]
    paces  = [((vdot_to_race_time(vdot, d) + riegel_predict(ref_dist, ref_time, d)) / 2) / d for d in dists]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=labels, y=paces,
        mode="lines+markers",
        line=dict(color="#e8ff47", width=2),
        marker=dict(size=8, color="#e8ff47"),
        hovertemplate="%{x}<br>%{customdata}<extra></extra>",
        customdata=[secs_to_mmss(p) + "/km" for p in paces],
    ))
    fig.update_layout(
        **_dark_layout("Prognozowane tempo vs dystans"),
        yaxis=dict(autorange="reversed", tickformat=".0f",
                   title="Tempo (sek/km)", gridcolor="#2a2a35"),
        xaxis=dict(gridcolor="#2a2a35"),
    )
    st.plotly_chart(fig, use_container_width=True)


def _dark_layout(title=""):
    return dict(
        title=title,
        plot_bgcolor="#0d0d0f", paper_bgcolor="#15151a",
        font_color="#f0f0f5",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=36, b=0),
    )
