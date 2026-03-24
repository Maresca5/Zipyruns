"""Dashboard — quick overview of recent form and top stats."""
import streamlit as st
import pandas as pd
import numpy as np
from utils.session import secs_to_mmss, secs_to_hhmmss, compute_ctl_atl_tsb, form_label
import plotly.graph_objects as go


def show():
    st.title("⚡ Dashboard")

    df: pd.DataFrame = st.session_state.get("activities", pd.DataFrame())
    if df.empty:
        st.warning("Brak aktywności — sprawdź połączenie ze Stravą.")
        return

    hrmax  = st.session_state.get("hrmax") or 185
    hrrest = st.session_state.get("hrrest") or 50

    # ── Quick stats ──────────────────────────────────────────────────────────
    last30 = df[df["date"] >= pd.Timestamp.now() - pd.Timedelta(days=30)]
    last7  = df[df["date"] >= pd.Timestamp.now() - pd.Timedelta(days=7)]

    best_vdot = df["vdot"].dropna().max()
    cur_vdot  = df["vdot"].dropna().head(5).mean()  # rolling recent

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("VDOT (aktualny)",   f"{cur_vdot:.1f}"  if not np.isnan(cur_vdot)  else "—")
    c2.metric("VDOT (best ever)",  f"{best_vdot:.1f}" if not np.isnan(best_vdot) else "—")
    c3.metric("Km / 30 dni",       f"{last30['dist_km'].sum():.0f} km")
    c4.metric("Treningi / 7 dni",  f"{len(last7)}")
    c5.metric("Aktywności łącznie",f"{len(df)}")

    st.markdown("---")

    # ── Fitness / Fatigue chart ───────────────────────────────────────────────
    st.subheader("Forma & Zmęczenie (CTL / ATL / TSB)")

    ctl_df = compute_ctl_atl_tsb(df, hrmax, hrrest)
    if not ctl_df.empty:
        current = ctl_df.iloc[-1]
        label, color = form_label(current["TSB"])

        cc1, cc2, cc3, cc4 = st.columns(4)
        cc1.metric("Fitness (CTL)",  f"{current['CTL']:.1f}")
        cc2.metric("Fatigue (ATL)",  f"{current['ATL']:.1f}")
        cc3.metric("Form (TSB)",     f"{current['TSB']:+.1f}")
        cc4.markdown(f"**Stan formy:**<br><span style='color:{color};font-size:1.1rem'>{label}</span>", unsafe_allow_html=True)

        recent = ctl_df[ctl_df["date"] >= (pd.Timestamp.now() - pd.Timedelta(days=90)).date()]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=recent["date"], y=recent["CTL"],  name="CTL Fitness",  line=dict(color="#47ffb0", width=2)))
        fig.add_trace(go.Scatter(x=recent["date"], y=recent["ATL"],  name="ATL Fatigue",  line=dict(color="#ff6b47", width=2)))
        fig.add_trace(go.Scatter(x=recent["date"], y=recent["TSB"],  name="TSB Form",     line=dict(color="#e8ff47", width=1, dash="dot"),
                                 fill="tozeroy", fillcolor="rgba(232,255,71,0.05)"))
        fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
        fig.update_layout(_dark_layout("Ostatnie 90 dni"))
        st.plotly_chart(fig, use_container_width=True)

    # ── Recent runs ──────────────────────────────────────────────────────────
    st.subheader("Ostatnie treningi")
    disp = df.head(10).copy()
    disp["Tempo"]    = disp["pace_s_km"].apply(secs_to_mmss)
    disp["Czas"]     = disp["duration_s"].apply(secs_to_hhmmss)
    disp["Dystans"]  = disp["dist_km"].apply(lambda x: f"{x:.2f} km")
    disp["VDOT"]     = disp["vdot"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
    disp["HR avg"]   = disp["avg_hr"].apply(lambda x: f"{x:.0f} bpm" if pd.notna(x) else "—")
    disp["Data"]     = disp["date"].dt.strftime("%d.%m.%Y")
    st.dataframe(
        disp[["Data","name","Dystans","Czas","Tempo","VDOT","HR avg"]].rename(columns={"name":"Nazwa"}),
        use_container_width=True, hide_index=True
    )


def _dark_layout(title=""):
    return dict(
        title=title,
        plot_bgcolor="#0d0d0f",
        paper_bgcolor="#15151a",
        font_color="#f0f0f5",
        xaxis=dict(gridcolor="#2a2a35", showgrid=True),
        yaxis=dict(gridcolor="#2a2a35", showgrid=True),
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor="#2a2a35"),
        margin=dict(l=0, r=0, t=36, b=0),
    )
