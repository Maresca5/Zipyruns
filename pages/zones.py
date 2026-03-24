"""Training zones page — Daniels pace zones + Karvonen HR zones."""
import streamlit as st
import pandas as pd
from utils.strava import get_training_paces, get_hr_zones
from utils.session import secs_to_mmss

ZONE_META = [
    ("easy",      "Easy / Regeneracja",       "Łatwy bieg, konwersacja możliwa, budowanie bazy.",  "#6bcfff"),
    ("marathon",  "Marathon / Tlenowa",        "Tempo maratońskie, aerobowy fundament.",             "#47ffb0"),
    ("threshold", "Threshold / Próg mleczanu", "Komfortowo twardo; poprawia prędkość progu.",        "#e8ff47"),
    ("interval",  "Interval / VO₂max",         "Ciężko, 3–5 min powtórzenia; max pułap tlenowy.",   "#ffb347"),
    ("rep",       "Repetition / Szybkość",     "Maksymalna prędkość, krótkie powtórzenia <2 min.",  "#ff6b47"),
]


def show():
    st.title("🫀 Strefy treningowe")

    df: pd.DataFrame = st.session_state.get("activities", pd.DataFrame())
    vdot_default = 45.0
    if not df.empty:
        v = df["vdot"].dropna().head(5).mean()
        if not pd.isna(v):
            vdot_default = round(v, 1)

    col1, col2, col3 = st.columns(3)
    vdot   = col1.number_input("VDOT",            25.0, 85.0, vdot_default, 0.5)
    hrmax  = col2.number_input("HR max (bpm)",    140,  220,  int(st.session_state.get("hrmax") or 185))
    hrrest = col3.number_input("HR spoczynkowe",  30,   100,  int(st.session_state.get("hrrest") or 50))

    st.session_state["hrmax"]  = hrmax
    st.session_state["hrrest"] = hrrest

    paces = get_training_paces(vdot)
    hr_z  = get_hr_zones(hrmax, hrrest)

    st.markdown("---")
    tab1, tab2 = st.tabs(["Strefy tempa (Daniels)", "Strefy tętna (Karvonen)"])

    with tab1:
        st.subheader("Strefy tempa wg Jack Daniels Running Formula")
        for i, (key, name, desc, color) in enumerate(ZONE_META, 1):
            lo = secs_to_mmss(paces[key]["pace_lo"])
            hi = secs_to_mmss(paces[key]["pace_hi"])
            pct_width = max(20, 100 - i * 15)
            st.markdown(f"""
            <div style="
                border-left: 4px solid {color};
                padding: 12px 16px;
                margin-bottom: 8px;
                background: rgba(255,255,255,0.03);
                border-radius: 0 4px 4px 0;
            ">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <span style="color:{color};font-family:'DM Mono';font-size:12px;letter-spacing:2px">Z{i}</span>
                  <strong style="margin-left:10px">{name}</strong>
                </div>
                <div style="font-family:'DM Mono';font-size:18px;color:{color}">{lo} – {hi} <small style="font-size:12px;color:#6b6b80">min/km</small></div>
              </div>
              <div style="color:#6b6b80;font-size:12px;margin-top:6px">{desc}</div>
              <div style="height:4px;background:#2a2a35;border-radius:2px;margin-top:10px">
                <div style="height:4px;width:{pct_width}%;background:{color};border-radius:2px"></div>
              </div>
            </div>
            """, unsafe_allow_html=True)

    with tab2:
        st.subheader("Strefy tętna wg metody Karvonena")
        zone_names  = ["Z1 Regeneracja", "Z2 Aerobowa", "Z3 Tlenowa", "Z4 Próg", "Z5 Anaerobowa"]
        zone_descs  = [
            "Aktywna regeneracja, spacery i bardzo lekkie biegi.",
            "Budowanie bazy aerobowej, długie spokojne biegi.",
            "Komfortowy wysiłek, główna strefa treningowa.",
            "Trudny, ale do utrzymania kilka minut — próg mleczanu.",
            "Maksymalny wysiłek, interwały i sprinty.",
        ]
        for z, name, desc in zip(hr_z, zone_names, zone_descs):
            pct = (z["hr_lo"] - hrrest) / (hrmax - hrrest) * 100 if hrmax > hrrest else 50
            st.markdown(f"""
            <div style="
                border-left: 4px solid {z['color']};
                padding: 12px 16px;
                margin-bottom: 8px;
                background: rgba(255,255,255,0.03);
                border-radius: 0 4px 4px 0;
            ">
              <div style="display:flex;justify-content:space-between;align-items:center">
                <div>
                  <span style="color:{z['color']};font-family:'DM Mono';font-size:12px;letter-spacing:2px">{z['name'][:2]}</span>
                  <strong style="margin-left:10px">{name}</strong>
                </div>
                <div style="font-family:'DM Mono';font-size:18px;color:{z['color']}">{z['hr_lo']} – {z['hr_hi']} <small style="font-size:12px;color:#6b6b80">bpm</small></div>
              </div>
              <div style="color:#6b6b80;font-size:12px;margin-top:6px">{desc}</div>
            </div>
            """, unsafe_allow_html=True)

        st.caption("""
        Karvonen: HR_target = HR_rest + % × (HR_max − HR_rest).  
        Dla najdokładniejszych stref zmierz HR max laboratoryjnie lub w teście wysiłkowym.
        """)
