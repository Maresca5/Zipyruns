"""Session helpers + ATL/CTL/TSB fitness-fatigue model."""
import pandas as pd
import numpy as np


def init_session():
    pass  # handled in app.py


def now() -> pd.Timestamp:
    """Timezone-naive Timestamp — safe for comparisons with Strava date columns."""
    return pd.Timestamp.now().tz_localize(None)


def secs_to_mmss(secs) -> str:
    try:
        secs = int(round(float(secs)))
    except (TypeError, ValueError):
        return "—"
    if secs <= 0:
        return "—"
    return f"{secs // 60}:{secs % 60:02d}"


def secs_to_hhmmss(secs) -> str:
    try:
        secs = int(round(float(secs)))
    except (TypeError, ValueError):
        return "—"
    if secs <= 0:
        return "—"
    h = secs // 3600
    m = (secs % 3600) // 60
    s = secs % 60
    return f"{h}:{m:02d}:{s:02d}"


def _ensure_dt(series: pd.Series) -> pd.Series:
    """Coerce to timezone-naive datetime64 regardless of input type."""
    s = pd.to_datetime(series, errors="coerce")
    if hasattr(s.dt, "tz") and s.dt.tz is not None:
        s = s.dt.tz_localize(None)
    return s


def compute_trimp(duration_s: float, avg_hr, hrmax: float, hrrest: float) -> float:
    try:
        avg_hr = float(avg_hr)
        if np.isnan(avg_hr) or avg_hr <= 0:
            raise ValueError
    except (TypeError, ValueError):
        return duration_s / 60 * 0.5
    hrr = float(np.clip((avg_hr - hrrest) / (hrmax - hrrest), 0.01, 0.99))
    return (duration_s / 60) * hrr * 0.64 * np.exp(1.92 * hrr)


def compute_ctl_atl_tsb(df: pd.DataFrame, hrmax: int = 185, hrrest: int = 50) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["date"] = _ensure_dt(df["date"])
    df = df.sort_values("date")
    df["trimp"] = df.apply(
        lambda r: compute_trimp(r["duration_s"], r.get("avg_hr", np.nan), hrmax, hrrest), axis=1
    )

    start = df["date"].min().normalize()
    end   = pd.Timestamp.now().normalize()
    date_range = pd.date_range(start, end, freq="D")

    # group by date (normalized to day)
    daily_idx = df["date"].dt.normalize()
    daily = df.groupby(daily_idx)["trimp"].sum().reindex(date_range, fill_value=0)

    ctl_k, atl_k = 2 / 43, 2 / 8
    ctl = atl = 0.0
    rows = []
    for ts, trimp in daily.items():
        ctl += ctl_k * (trimp - ctl)
        atl += atl_k * (trimp - atl)
        rows.append({"date": ts, "trimp": trimp, "CTL": ctl, "ATL": atl, "TSB": ctl - atl})

    out = pd.DataFrame(rows)
    out["date"] = pd.to_datetime(out["date"])  # guarantee datetime64
    return out


def form_label(tsb: float) -> tuple:
    if tsb > 15:  return "🟢 Świeży / Gotowy", "#47ffb0"
    if tsb > 5:   return "🟡 Optymalny",        "#e8ff47"
    if tsb > -10: return "🟠 Akumulacja",        "#ffb347"
    if tsb > -25: return "🔴 Zmęczony",          "#ff6b47"
    return "💀 Przeciążony", "#ff3347"
