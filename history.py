"""Historical analysis — VDOT trend, best efforts, HR drift."""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from utils.session import secs_to_mmss, secs_to_hhmmss, compute_ctl_atl_tsb, form_label
from utils.strava import vdot_to_race_time

RACES_KM = {"5 km": 5.0, "10 km": 10.0, "Półmaraton": 21.0975, "Maraton": 42.195}


def show():
    st.title("📊 Analiza historyczna")

    df: pd.DataFrame = st.session_state.get("activities", pd.DataFrame())
    if df.empty:
        st.warning("Brak danych.")
        return

    tab1, tab2, tab3, tab4 = st.tabs(["VDOT w czasie", "Najlepsze wyniki", "HR & Fitness", "Forma / ATL·CTL"])

    # ─────────────────────────────────────────────────────────────────────────
    with tab1:
        st.subheader("Progresja VDOT")
        vdot_df = df.dropna(subset=["vdot"]).copy()
        if vdot_df.empty:
            st.info("Za mało danych do progresji.")
        else:
            # rolling 4-run average
            vdot_df = vdot_df.sort_values("date")
            vdot_df["vdot_roll"] = vdot_df["vdot"].rolling(4, min_periods=1).mean()

            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=vdot_df["date"], y=vdot_df["vdot"],
                mode="markers", name="Pojedynczy wysiłek",
                marker=dict(color="#47c8ff", size=6, opacity=0.5),
                hovertemplate="%{x|%d.%m.%Y}<br>VDOT: %{y:.1f}<extra></extra>",
            ))
            fig.add_trace(go.Scatter(
                x=vdot_df["date"], y=vdot_df["vdot_roll"],
                mode="lines", name="Średnia krocząca (4 runy)",
                line=dict(color="#e8ff47", width=2.5),
            ))
            fig.update_layout(**_dark("VDOT w czasie"))
            st.plotly_chart(fig, use_container_width=True)

            # trend
            if len(vdot_df) >= 4:
                x_num = (vdot_df["date"] - vdot_df["date"].min()).dt.days.values
                coef  = np.polyfit(x_num, vdot_df["vdot"].values, 1)
                trend_per_month = coef[0] * 30
                arrow = "↑" if trend_per_month > 0 else "↓"
                color = "#47ffb0" if trend_per_month > 0 else "#ff6b47"
                st.markdown(
                    f"**Trend:** <span style='color:{color}'>{arrow} {abs(trend_per_month):.2f} VDOT / miesiąc</span>",
                    unsafe_allow_html=True,
                )

    # ─────────────────────────────────────────────────────────────────────────
    with tab2:
        st.subheader("Najlepsze wyniki na dystansach")

        col1, col2 = st.columns(2)
        tolerance = col1.slider("Tolerancja dystansu (±%)", 1, 20, 5)

        best_efforts = {}
        for name, km in RACES_KM.items():
            tol = km * tolerance / 100
            candidates = df[(df["dist_km"] >= km - tol) & (df["dist_km"] <= km + tol)].copy()
            if not candidates.empty:
                # adjust time to exact distance via pace
                candidates["adj_time"] = candidates["pace_s_km"] * km
                best_row = candidates.loc[candidates["adj_time"].idxmin()]
                best_efforts[name] = best_row

        if best_efforts:
            cols = st.columns(len(best_efforts))
            for col, (name, row) in zip(cols, best_efforts.items()):
                km = RACES_KM[name]
                adj = row["pace_s_km"] * km
                col.metric(name, secs_to_hhmmss(adj))
                col.caption(
                    f"{secs_to_mmss(row['pace_s_km'])}/km\n"
                    f"{row['date'].strftime('%d.%m.%Y')}"
                )

            st.markdown("---")
            # Timeline of best efforts per race distance
            fig = go.Figure()
            for name, km in RACES_KM.items():
                tol = km * tolerance / 100
                sub = df[(df["dist_km"] >= km - tol) & (df["dist_km"] <= km + tol)].copy()
                if sub.empty: continue
                sub["adj_pace"] = sub["pace_s_km"]
                sub = sub.sort_values("date")
                sub["best_pace"] = sub["adj_pace"].cummin()
                fig.add_trace(go.Scatter(
                    x=sub["date"], y=sub["best_pace"],
                    mode="lines+markers", name=name,
                    hovertemplate=f"<b>{name}</b><br>%{{x|%d.%m.%Y}}<br>%{{customdata}}/km<extra></extra>",
                    customdata=sub["adj_pace"].apply(secs_to_mmss),
                ))
            fig.update_yaxes(autorange="reversed", title="Tempo (sek/km)", gridcolor="#2a2a35")
            fig.update_layout(**_dark("Progresja najlepszego tempa"))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Za mało danych spełniających kryteria dystansu.")

    # ─────────────────────────────────────────────────────────────────────────
    with tab3:
        st.subheader("Analiza HR & Aerobic Fitness")

        hr_df = df.dropna(subset=["avg_hr"]).copy()
        if hr_df.empty:
            st.info("Brak danych tętna. Upewnij się, że biegasz z pulsometrem.")
        else:
            # HR efficiency: pace per HR unit
            hr_df["hr_efficiency"] = hr_df["avg_hr"] / hr_df["pace_s_km"]  # higher = more HR for same pace → worse
            hr_df["aerobic_idx"]   = hr_df["pace_s_km"] / hr_df["avg_hr"]  # lower pace (faster) per HR → better

            col1, col2 = st.columns(2)

            with col1:
                fig = go.Figure()
                hr_df_s = hr_df.sort_values("date")
                hr_df_s["ae_roll"] = hr_df_s["aerobic_idx"].rolling(5, min_periods=1).mean()
                fig.add_trace(go.Scatter(
                    x=hr_df_s["date"], y=hr_df_s["aerobic_idx"],
                    mode="markers", name="Sesja",
                    marker=dict(color="#47c8ff", size=5, opacity=0.4),
                ))
                fig.add_trace(go.Scatter(
                    x=hr_df_s["date"], y=hr_df_s["ae_roll"],
                    mode="lines", name="Śr. krocząca",
                    line=dict(color="#e8ff47", width=2),
                ))
                fig.update_layout(**_dark("Aerobic Index (niższy = wolniejszy / wyższy HR)"))
                fig.update_yaxes(autorange="reversed")
                st.plotly_chart(fig, use_container_width=True)
                st.caption("Malejący trend = poprawa efektywności aerobowej")

            with col2:
                fig2 = go.Figure(go.Scatter(
                    x=hr_df["avg_hr"], y=hr_df["pace_s_km"],
                    mode="markers",
                    marker=dict(
                        color=hr_df["date"].astype(np.int64),
                        colorscale="Viridis",
                        size=7, opacity=0.7,
                        showscale=True,
                        colorbar=dict(title="Data"),
                    ),
                    hovertemplate="HR: %{x} bpm<br>Tempo: %{customdata}/km<extra></extra>",
                    customdata=hr_df["pace_s_km"].apply(secs_to_mmss),
                ))
                fig2.update_yaxes(autorange="reversed", title="Tempo (sek/km)")
                fig2.update_xaxes(title="HR śr. (bpm)")
                fig2.update_layout(**_dark("HR vs tempo (kolor = czas)"))
                st.plotly_chart(fig2, use_container_width=True)

            # HR zones distribution
            st.subheader("Rozkład czasu w strefach HR")
            hrmax  = st.session_state.get("hrmax") or 185
            hrrest = st.session_state.get("hrrest") or 50
            hrr    = hrmax - hrrest

            zone_breaks = [hrrest + f * hrr for f in [0, 0.60, 0.70, 0.80, 0.90, 1.0, 9999]]
            zone_names  = ["Z1 Regen", "Z2 Aerob", "Z3 Tlenowa", "Z4 Próg", "Z5 Anaerob"]
            zone_colors = ["#6bcfff", "#47ffb0", "#e8ff47", "#ffb347", "#ff6b47"]

            hr_df["zone"] = pd.cut(hr_df["avg_hr"], bins=zone_breaks, labels=zone_names)
            zone_counts = hr_df.groupby("zone", observed=True)["duration_s"].sum() / 3600

            fig3 = go.Figure(go.Bar(
                x=list(zone_counts.index),
                y=list(zone_counts.values),
                marker_color=zone_colors[:len(zone_counts)],
            ))
            fig3.update_layout(**_dark("Godziny w strefach HR"), yaxis_title="Godziny")
            st.plotly_chart(fig3, use_container_width=True)

    # ─────────────────────────────────────────────────────────────────────────
    with tab4:
        st.subheader("Forma i zmęczenie — model ATL/CTL/TSB")

        hrmax  = st.session_state.get("hrmax") or 185
        hrrest = st.session_state.get("hrrest") or 50

        ctl_df = compute_ctl_atl_tsb(df, hrmax, hrrest)
        if ctl_df.empty:
            st.info("Za mało danych.")
        else:
            current = ctl_df.iloc[-1]
            label, color = form_label(current["TSB"])

            c1, c2, c3 = st.columns(3)
            c1.metric("CTL – Fitness",    f"{current['CTL']:.1f}", help="Chronic Training Load — τ=42 dni")
            c2.metric("ATL – Fatigue",    f"{current['ATL']:.1f}", help="Acute Training Load — τ=7 dni")
            c3.metric("TSB – Form",       f"{current['TSB']:+.1f}", help="Training Stress Balance = CTL - ATL")
            st.markdown(f"**Stan:** <span style='color:{color};font-size:1.2rem'>{label}</span>", unsafe_allow_html=True)

            st.markdown("---")
            days_back = st.slider("Pokaż ostatnie (dni)", 30, 365, 120)
            cutoff = (pd.Timestamp.now() - pd.Timedelta(days=days_back)).date()
            ctl_recent = ctl_df[ctl_df["date"] >= cutoff]

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=ctl_recent["date"], y=ctl_recent["CTL"], name="CTL Fitness",
                                     line=dict(color="#47ffb0", width=2)))
            fig.add_trace(go.Scatter(x=ctl_recent["date"], y=ctl_recent["ATL"], name="ATL Fatigue",
                                     line=dict(color="#ff6b47", width=2)))
            fig.add_trace(go.Scatter(x=ctl_recent["date"], y=ctl_recent["TSB"], name="TSB Form",
                                     line=dict(color="#e8ff47", width=1.5, dash="dot"),
                                     fill="tozeroy", fillcolor="rgba(232,255,71,0.06)"))
            fig.add_hline(y=0,  line_dash="dash", line_color="rgba(255,255,255,0.15)")
            fig.add_hrect(y0=5, y1=15, fillcolor="rgba(71,255,176,0.05)", line_width=0,
                          annotation_text="Optimal zone", annotation_position="top right")
            fig.update_layout(**_dark(f"ATL / CTL / TSB — ostatnie {days_back} dni"))
            st.plotly_chart(fig, use_container_width=True)

            st.caption("""
            **CTL** (Fitness) = długoterminowe obciążenie (τ=42 dni).  
            **ATL** (Fatigue) = krótkoterminowe zmęczenie (τ=7 dni).  
            **TSB** (Form) = CTL − ATL. Zielona strefa (5–15) = optymalny stan startowy.
            """)


def _dark(title=""):
    return dict(
        title=title,
        plot_bgcolor="#0d0d0f", paper_bgcolor="#15151a",
        font_color="#f0f0f5",
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        margin=dict(l=0, r=0, t=36, b=0),
    )
