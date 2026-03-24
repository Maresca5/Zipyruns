"""Dashboard — quick overview of recent form and top stats."""
import streamlit as st
import pandas as pd
import numpy as np
from utils.session import secs_to_mmss, secs_to_hhmmss, compute_ctl_atl_tsb, form_label
import plotly.graph_objects as go


def show():
    st.title("⚡ Dashboard")

    # Pobierz dane z session state z zabezpieczeniem
    df: pd.DataFrame = st.session_state.get("activities", pd.DataFrame())
    
    # Sprawdź czy df jest DataFrame i czy nie jest pusty
    if not isinstance(df, pd.DataFrame) or df.empty:
        st.warning("Brak aktywności — sprawdź połączenie ze Stravą.")
        return

    # Pobierz dane użytkownika z zabezpieczeniem
    hrmax = st.session_state.get("hrmax")
    if hrmax is None:
        hrmax = 185
        st.session_state["hrmax"] = hrmax
    
    hrrest = st.session_state.get("hrrest")
    if hrrest is None:
        hrrest = 50
        st.session_state["hrrest"] = hrrest

    # Sprawdź czy wymagane kolumny istnieją
    required_cols = ["date", "dist_km", "vdot", "duration_s", "pace_s_km", "avg_hr", "name"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    if missing_cols:
        st.error(f"Brakuje wymaganych kolumn w danych: {', '.join(missing_cols)}")
        st.info("Dostępne kolumny: " + ", ".join(df.columns.tolist()))
        return

    # ── Quick stats ──────────────────────────────────────────────────────────
    # Sprawdź czy kolumna date jest typu datetime
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        try:
            df["date"] = pd.to_datetime(df["date"])
        except:
            st.error("Nie można przekonwertować kolumny 'date' na format datetime")
            return
    
    now = pd.Timestamp.now()
    last30 = df[df["date"] >= now - pd.Timedelta(days=30)]
    last7 = df[df["date"] >= now - pd.Timedelta(days=7)]

    # Oblicz VDOT z zabezpieczeniem przed pustymi danymi
    vdot_values = df["vdot"].dropna()
    best_vdot = vdot_values.max() if not vdot_values.empty else None
    cur_vdot = vdot_values.head(5).mean() if not vdot_values.empty else None

    c1, c2, c3, c4, c5 = st.columns(5)
    
    with c1:
        if cur_vdot is not None and not np.isnan(cur_vdot):
            c1.metric("VDOT (aktualny)", f"{cur_vdot:.1f}")
        else:
            c1.metric("VDOT (aktualny)", "—")
    
    with c2:
        if best_vdot is not None and not np.isnan(best_vdot):
            c2.metric("VDOT (best ever)", f"{best_vdot:.1f}")
        else:
            c2.metric("VDOT (best ever)", "—")
    
    with c3:
        if not last30.empty and "dist_km" in last30.columns:
            c3.metric("Km / 30 dni", f"{last30['dist_km'].sum():.0f} km")
        else:
            c3.metric("Km / 30 dni", "—")
    
    with c4:
        c4.metric("Treningi / 7 dni", f"{len(last7)}")
    
    with c5:
        c5.metric("Aktywności łącznie", f"{len(df)}")

    st.markdown("---")

    # ── Fitness / Fatigue chart ───────────────────────────────────────────────
    st.subheader("Forma & Zmęczenie (CTL / ATL / TSB)")

    try:
        ctl_df = compute_ctl_atl_tsb(df, hrmax, hrrest)
        
        if ctl_df is not None and not ctl_df.empty:
            current = ctl_df.iloc[-1]
            
            # Sprawdź czy wymagane kolumny istnieją w ctl_df
            if "TSB" in current.index:
                label, color = form_label(current["TSB"])
                
                cc1, cc2, cc3, cc4 = st.columns(4)
                
                with cc1:
                    if "CTL" in current.index:
                        cc1.metric("Fitness (CTL)", f"{current['CTL']:.1f}")
                    else:
                        cc1.metric("Fitness (CTL)", "—")
                
                with cc2:
                    if "ATL" in current.index:
                        cc2.metric("Fatigue (ATL)", f"{current['ATL']:.1f}")
                    else:
                        cc2.metric("Fatigue (ATL)", "—")
                
                with cc3:
                    if "TSB" in current.index:
                        cc3.metric("Form (TSB)", f"{current['TSB']:+.1f}")
                    else:
                        cc3.metric("Form (TSB)", "—")
                
                with cc4:
                    if "TSB" in current.index:
                        cc4.markdown(
                            f"**Stan formy:**<br><span style='color:{color};font-size:1.1rem'>{label}</span>", 
                            unsafe_allow_html=True
                        )
                    else:
                        cc4.markdown("**Stan formy:**<br><span>—</span>", unsafe_allow_html=True)

                # Przygotuj dane do wykresu
                if "date" in ctl_df.columns and "CTL" in ctl_df.columns and "ATL" in ctl_df.columns and "TSB" in ctl_df.columns:
                    ninety_days_ago = pd.Timestamp.now() - pd.Timedelta(days=90)
                    recent = ctl_df[ctl_df["date"] >= ninety_days_ago.date()] if "date" in ctl_df.columns else ctl_df
                    
                    if not recent.empty:
                        fig = go.Figure()
                        
                        # CTL Fitness
                        if "CTL" in recent.columns:
                            fig.add_trace(go.Scatter(
                                x=recent["date"] if "date" in recent.columns else recent.index,
                                y=recent["CTL"],
                                name="CTL Fitness",
                                line=dict(color="#47ffb0", width=2)
                            ))
                        
                        # ATL Fatigue
                        if "ATL" in recent.columns:
                            fig.add_trace(go.Scatter(
                                x=recent["date"] if "date" in recent.columns else recent.index,
                                y=recent["ATL"],
                                name="ATL Fatigue",
                                line=dict(color="#ff6b47", width=2)
                            ))
                        
                        # TSB Form
                        if "TSB" in recent.columns:
                            fig.add_trace(go.Scatter(
                                x=recent["date"] if "date" in recent.columns else recent.index,
                                y=recent["TSB"],
                                name="TSB Form",
                                line=dict(color="#e8ff47", width=1, dash="dot"),
                                fill="tozeroy",
                                fillcolor="rgba(232,255,71,0.05)"
                            ))
                        
                        fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.2)")
                        fig.update_layout(_dark_layout("Ostatnie 90 dni"))
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("Brak danych do wyświetlenia wykresu formy")
                else:
                    st.warning("Niekompletne dane do wyświetlenia wykresu CTL/ATL/TSB")
            else:
                st.warning("Brak danych TSB do wyświetlenia")
        else:
            st.info("Brak danych do obliczenia CTL/ATL/TSB. Dodaj więcej aktywności.")
    
    except Exception as e:
        st.error(f"Błąd podczas obliczania CTL/ATL/TSB: {str(e)}")
        st.info("Upewnij się, że masz wystarczającą liczbę aktywności z danymi tętna")

    # ── Recent runs ──────────────────────────────────────────────────────────
    st.subheader("Ostatnie treningi")
    
    try:
        # Sprawdź czy są dane
        if not df.empty:
            disp = df.head(10).copy()
            
            # Konwertuj dane z zabezpieczeniami
            if "pace_s_km" in disp.columns:
                disp["Tempo"] = disp["pace_s_km"].apply(lambda x: secs_to_mmss(x) if pd.notna(x) else "—")
            else:
                disp["Tempo"] = "—"
            
            if "duration_s" in disp.columns:
                disp["Czas"] = disp["duration_s"].apply(lambda x: secs_to_hhmmss(x) if pd.notna(x) else "—")
            else:
                disp["Czas"] = "—"
            
            if "dist_km" in disp.columns:
                disp["Dystans"] = disp["dist_km"].apply(lambda x: f"{x:.2f} km" if pd.notna(x) else "—")
            else:
                disp["Dystans"] = "—"
            
            if "vdot" in disp.columns:
                disp["VDOT"] = disp["vdot"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
            else:
                disp["VDOT"] = "—"
            
            if "avg_hr" in disp.columns:
                disp["HR avg"] = disp["avg_hr"].apply(lambda x: f"{x:.0f} bpm" if pd.notna(x) else "—")
            else:
                disp["HR avg"] = "—"
            
            if "date" in disp.columns:
                if pd.api.types.is_datetime64_any_dtype(disp["date"]):
                    disp["Data"] = disp["date"].dt.strftime("%d.%m.%Y")
                else:
                    try:
                        disp["date"] = pd.to_datetime(disp["date"])
                        disp["Data"] = disp["date"].dt.strftime("%d.%m.%Y")
                    except:
                        disp["Data"] = disp["date"].astype(str)
            else:
                disp["Data"] = "—"
            
            # Wybierz kolumny do wyświetlenia
            display_cols = ["Data"]
            if "name" in disp.columns:
                display_cols.append("name")
            display_cols.extend(["Dystans", "Czas", "Tempo", "VDOT", "HR avg"])
            
            # Sprawdź czy wszystkie kolumny istnieją
            available_cols = [col for col in display_cols if col in disp.columns]
            
            if available_cols:
                rename_dict = {}
                if "name" in available_cols:
                    rename_dict["name"] = "Nazwa"
                
                st.dataframe(
                    disp[available_cols].rename(columns=rename_dict),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("Brak danych do wyświetlenia")
        else:
            st.info("Brak aktywności do wyświetlenia")
    
    except Exception as e:
        st.error(f"Błąd podczas wyświetlania ostatnich treningów: {str(e)}")
        st.info("Sprawdź czy dane zawierają wszystkie wymagane kolumny")


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