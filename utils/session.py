"""Session helpers + ATL/CTL/TSB fitness-fatigue model."""
import streamlit as st
import pandas as pd
import numpy as np


def init_session():
    """No-op — session init is handled in app.py before any imports."""
    pass


def secs_to_mmss(secs) -> str:
    if secs is None or (isinstance(secs, float) and np.isnan(secs)) or secs <= 0:
        return "—"
    secs = int(round(float(secs)))
    m = secs // 60
    s = secs % 60
    return f"{m}:{s:02d}"


def secs_to_hhmmss(secs) -> str:
    if secs is None or (isinstance(secs, float) and np.isnan(secs)) or secs <= 0:
        return "—"
    secs = int(round(float(secs)))
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h}:{m:02d}:{s:02d}"


# ── Fitness-Fatigue (Banister impulse-response) ──────────────────────────────

def compute_trimp(duration_s: float, avg_hr, hrmax: float, hrrest: float) -> float:
    """Training Impulse (TRIMP) — Bannister male formula."""
    try:
        avg_hr = float(avg_hr)
        if np.isnan(avg_hr) or avg_hr <= 0:
            return duration_s / 60 * 0.5
    except (TypeError, ValueError):
        return duration_s / 60 * 0.5

    hrr_frac = (avg_hr - hrrest) / (hrmax - hrrest)
    hrr_frac = float(np.clip(hrr_frac, 0.01, 0.99))
    y = 0.64 * np.exp(1.92 * hrr_frac)
    return (duration_s / 60) * hrr_frac * y


def compute_ctl_atl_tsb(df: pd.DataFrame, hrmax: int = 185, hrrest: int = 50) -> pd.DataFrame:
    """
    Compute daily CTL (Fitness), ATL (Fatigue), TSB (Form).
    CTL τ = 42 days, ATL τ = 7 days (exponential smoothing).
    """
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy().sort_values("date")
    df["trimp"] = df.apply(
        lambda r: compute_trimp(r["duration_s"], r.get("avg_hr", np.nan), hrmax, hrrest),
        axis=1,
    )

    date_range = pd.date_range(df["date"].min().date(), pd.Timestamp.today().date(), freq="D")
    daily = df.groupby(df["date"].dt.date)["trimp"].sum().reindex(date_range, fill_value=0)

    ctl_k = 2 / (42 + 1)
    atl_k = 2 / (7 + 1)

    ctl, atl = 0.0, 0.0
    rows = []
    for date, trimp in daily.items():
        ctl = ctl + ctl_k * (trimp - ctl)
        atl = atl + atl_k * (trimp - atl)
        rows.append({"date": date, "trimp": trimp, "CTL": ctl, "ATL": atl, "TSB": ctl - atl})

    return pd.DataFrame(rows)


def form_label(tsb: float) -> tuple:
    """Return (label, color) for current form."""
    if tsb > 15:   return "🟢 Świeży / Gotowy", "#47ffb0"
    if tsb > 5:    return "🟡 Optymalny", "#e8ff47"
    if tsb > -10:  return "🟠 Akumulacja", "#ffb347"
    if tsb > -25:  return "🔴 Zmęczony", "#ff6b47"
    return "💀 Przeciążony", "#ff3347"
