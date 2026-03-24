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

    # Pobierz dane z session state i sprawdź czy istnieją
    df: pd.DataFrame = st.session_state.get("activities", pd.DataFrame())
    vdot = None
    if not df.empty:
        # Sprawdź czy kolumna vdot istnieje
        if "vdot" in df.columns:
            vdot = df["vdot"].dropna().head(5).mean()
        else:
            vdot = 45.0  # domyślna wartość jeśli nie ma danych

    # ── Controls ─────────────────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)

    dist_name = col1.selectbox("Dystans", [r[0] for r in RACES], index=2)
    dist_km   = next(r[1] for r in RACES if r[0] == dist_name)

    # Ustaw wartość VDOT z domyślną jeśli brak danych
    default_vdot = float(round(vdot, 1)) if vdot and not pd.isna(vdot) else 45.0
    vdot_input = col2.number_input("VDOT", min_value=25.0, max_value=85.0,
                                   value=default_vdot, step=0.5)

    strategy = col3.selectbox("Strategia tempa", [
        "Even splits",
        "Negative split (ostatnie km szybsze)",
        "Positive split (klasyczny start)",
        "Race profile (sag w środku)",
    ])

    adj_pct = col4.slider("Korekta celu", -10, 10, 0, 1, format="%d%%")

    # ── Compute ───────────────────────────────────────────────────────────────
    # Sprawdź czy funkcja vdot_to_race_time istnieje, jeśli nie, użyj domyślnego wzoru
    try:
        base_secs = vdot_to_race_time(vdot_input, dist_km)
    except (AttributeError, NameError, TypeError):
        # Jeśli funkcja nie istnieje, użyj uproszczonego wzoru
        base_secs = _vdot_to_time_fallback(vdot_input, dist_km)
    
    target_secs = base_secs * (1 + adj_pct / 100)
    base_pace = target_secs / dist_km  # secs/km average

    # Określ krok dla segmentów
    if dist_km >= 42:
        step = 2.0  # dla maratonu co 2 km
    elif dist_km >= 21:
        step = 1.0  # dla półmaratonu co 1 km
    else:
        step = 0.5  # dla krótszych dystansów co 0.5 km
    
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

    # Pobierz strefy treningowe
    try:
        paces_zones = get_training_paces(vdot_input)
    except (AttributeError, NameError, TypeError):
        # Jeśli funkcja nie istnieje, użyj domyślnych stref
        paces_zones = _get_training_paces_fallback(vdot_input)

    def get_zone(pace_s_km):
        # Sprawdź czy paces_zones zawiera wymagane klucze
        for key in ["rep", "interval", "threshold", "marathon", "easy"]:
            if key in paces_zones and pace_s_km <= paces_zones[key]["pace_hi"]:
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
    if rows:  # Sprawdź czy są dane do wykresu
        fig = go.Figure()
        for zone, color in ZONE_COLORS.items():
            zone_rows = [r for r in rows if r["_zone"] == zone]
            if zone_rows:
                # Oblicz szerokości słupków
                widths = []
                for r in zone_rows:
                    start_km = float(r["Km"].split("–")[0])
                    end_km = float(r["Km"].split("–")[1])
                    widths.append(end_km - start_km)
                
                fig.add_trace(go.Bar(
                    x=[r["_km_end"] for r in zone_rows],
                    y=[r["_pace"] for r in zone_rows],
                    name=ZONE_LABELS[zone],
                    marker_color=color,
                    width=widths,
                    hovertemplate="<b>%{customdata}</b><br>Tempo: %{text}<extra></extra>",
                    text=[r["Tempo"] for r in zone_rows],
                    customdata=[r["Km"] + " km" for r in zone_rows],
                ))
        
        # Konwertuj tempo na min/km dla osi Y
        y_ticks = []
        y_values = []
        for pace in np.linspace(min([r["_pace"] for r in rows]), max([r["_pace"] for r in rows]), 5):
            y_values.append(pace)
            y_ticks.append(secs_to_mmss(pace) + "/km")
        
        fig.update_yaxes(
            autorange="reversed", 
            title="Tempo (min/km)", 
            gridcolor="#2a2a35",
            tickmode='array',
            tickvals=y_values,
            ticktext=y_ticks
        )
        fig.update_xaxes(title="Dystans (km)", gridcolor="#2a2a35")
        fig.update_layout(
            title="Pacing plan — tempo po km",
            plot_bgcolor="#0d0d0f", 
            paper_bgcolor="#15151a",
            font_color="#f0f0f5",
            legend=dict(bgcolor="rgba(0,0,0,0)"),
            margin=dict(l=0, r=0, t=36, b=0),
            barmode="overlay"
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("Nie można wygenerować wykresu - brak danych")

    # ── Splits table ──────────────────────────────────────────────────────────
    if rows:
        display_df = pd.DataFrame([{k: v for k, v in r.items() if not k.startswith("_")} for r in rows])
        st.dataframe(display_df, use_container_width=True, hide_index=True)

        # ── Export hint ───────────────────────────────────────────────────────────
        csv = display_df.to_csv(index=False).encode("utf-8")
        st.download_button("⬇️ Pobierz CSV", csv, "race_strategy.csv", "text/csv")
    else:
        st.warning("Nie można wygenerować tabeli - brak danych")


def _vdot_to_time_fallback(vdot, distance_km):
    """Uproszczona funkcja pomocnicza do przeliczania VDOT na czas"""
    # Przybliżone czasy dla różnych VDOT
    vdot_times = {
        30: {"5k": 1800, "10k": 3720, "half": 8220, "full": 17520},
        35: {"5k": 1560, "10k": 3240, "half": 7140, "full": 15000},
        40: {"5k": 1380, "10k": 2880, "half": 6360, "full": 13320},
        45: {"5k": 1240, "10k": 2580, "half": 5700, "full": 12000},
        50: {"5k": 1120, "10k": 2340, "half": 5160, "full": 10800},
        55: {"5k": 1040, "10k": 2160, "half": 4740, "full": 9900},
        60: {"5k": 960, "10k": 1980, "half": 4380, "full": 9180},
        65: {"5k": 880, "10k": 1840, "half": 4080, "full": 8580},
        70: {"5k": 820, "10k": 1720, "half": 3840, "full": 8040},
    }
    
    # Znajdź najbliższy VDOT
    available_vdots = sorted(vdot_times.keys())
    closest_vdot = min(available_vdots, key=lambda x: abs(x - vdot))
    
    # Wybierz odpowiedni dystans
    if distance_km <= 5:
        time = vdot_times[closest_vdot]["5k"] * (distance_km / 5)
    elif distance_km <= 10:
        time = vdot_times[closest_vdot]["5k"] + (vdot_times[closest_vdot]["10k"] - vdot_times[closest_vdot]["5k"]) * ((distance_km - 5) / 5)
    elif distance_km <= 21.0975:
        time = vdot_times[closest_vdot]["10k"] + (vdot_times[closest_vdot]["half"] - vdot_times[closest_vdot]["10k"]) * ((distance_km - 10) / 11.0975)
    else:
        time = vdot_times[closest_vdot]["half"] + (vdot_times[closest_vdot]["full"] - vdot_times[closest_vdot]["half"]) * ((distance_km - 21.0975) / 21.0975)
    
    return time


def _get_training_paces_fallback(vdot):
    """Uproszczona funkcja pomocnicza do pobierania stref treningowych"""
    # Przybliżone tempo maratonu (min/km)
    marathon_pace = {
        30: 8.20, 35: 7.10, 40: 6.15, 45: 5.40,
        50: 5.00, 55: 4.40, 60: 4.15, 65: 4.00, 70: 3.45
    }
    
    available_vdots = sorted(marathon_pace.keys())
    closest_vdot = min(available_vdots, key=lambda x: abs(x - vdot))
    base_pace = marathon_pace[closest_vdot]
    base_seconds = base_pace * 60
    
    return {
        "rep": {"pace_hi": base_seconds * 0.78},
        "interval": {"pace_hi": base_seconds * 0.85},
        "threshold": {"pace_hi": base_seconds * 0.92},
        "marathon": {"pace_hi": base_seconds},
        "easy": {"pace_hi": base_seconds * 1.25}
    }