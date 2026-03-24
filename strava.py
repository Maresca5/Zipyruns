"""Strava API helpers — OAuth, activity fetch, data parsing."""
import requests
import pandas as pd
import streamlit as st
from datetime import datetime


def exchange_token(client_id: str, client_secret: str, code: str) -> dict | None:
    """Exchange authorization code for access/refresh tokens."""
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
        },
        timeout=10,
    )
    if resp.ok:
        return resp.json()
    st.error(f"Token exchange failed: {resp.text}")
    return None


def refresh_access_token(client_id: str, client_secret: str, refresh_token: str) -> dict | None:
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=10,
    )
    return resp.json() if resp.ok else None


def fetch_activities(access_token: str, n: int = 100) -> pd.DataFrame:
    """Fetch last `n` activities, return as DataFrame with runs only."""
    all_acts = []
    page = 1
    per_page = 50
    headers = {"Authorization": f"Bearer {access_token}"}

    while len(all_acts) < n:
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params={"per_page": per_page, "page": page},
            timeout=15,
        )
        if not resp.ok or not resp.json():
            break
        all_acts.extend(resp.json())
        if len(resp.json()) < per_page:
            break
        page += 1

    if not all_acts:
        return pd.DataFrame()

    df = pd.DataFrame(all_acts)

    # Keep only runs
    df = df[df["type"].isin(["Run", "VirtualRun", "TrailRun"])].copy()
    if df.empty:
        return df

    # Parse & compute useful columns
    df["date"]         = pd.to_datetime(df["start_date_local"])
    df["dist_km"]      = df["distance"] / 1000
    df["duration_s"]   = df["moving_time"]
    df["pace_s_km"]    = df["duration_s"] / df["dist_km"]
    df["pace_min_km"]  = df["pace_s_km"] / 60
    df["avg_hr"]       = df.get("average_heartrate", pd.NA)
    df["max_hr"]       = df.get("max_heartrate", pd.NA)
    df["elev_gain"]    = df.get("total_elevation_gain", 0)
    df["name"]         = df["name"]
    df["vdot"]         = df.apply(lambda r: _estimate_vdot(r["dist_km"], r["duration_s"]), axis=1)

    cols = ["date", "name", "dist_km", "duration_s", "pace_s_km", "pace_min_km",
            "avg_hr", "max_hr", "elev_gain", "vdot"]
    return df[cols].sort_values("date", ascending=False).reset_index(drop=True)


# ─── VDOT from Daniels ───────────────────────────────────────────────────────

def _estimate_vdot(dist_km: float, time_s: float) -> float | None:
    """Estimate VDOT from race/effort using Daniels' formula."""
    if dist_km < 1 or time_s < 60:
        return None
    t = time_s / 60  # minutes
    v = dist_km * 1000 / t  # m/min
    vo2      = -4.60 + 0.182258 * v + 0.000104 * v * v
    pct_vo2  = 0.8 + 0.1894393 * _exp(-0.012778 * t) + 0.2989558 * _exp(-0.1932605 * t)
    vdot = vo2 / pct_vo2
    return round(vdot, 2) if 20 < vdot < 90 else None


def _exp(x: float) -> float:
    import math
    return math.exp(x)


def vdot_to_race_time(vdot: float, dist_km: float) -> float:
    """Predict race time (seconds) for given VDOT and distance."""
    import math
    lo, hi = 1.0, 600.0
    for _ in range(60):
        mid = (lo + hi) / 2
        v    = dist_km * 1000 / mid
        vo2  = -4.60 + 0.182258 * v + 0.000104 * v * v
        pct  = 0.8 + 0.1894393 * math.exp(-0.012778 * mid) + 0.2989558 * math.exp(-0.1932605 * mid)
        if vo2 / pct < vdot:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2 * 60  # seconds


def riegel_predict(ref_dist: float, ref_time_s: float, target_dist: float) -> float:
    """Riegel's formula: T2 = T1 * (D2/D1)^1.06"""
    return ref_time_s * (target_dist / ref_dist) ** 1.06


def get_training_paces(vdot: float) -> dict:
    """Return Daniels training pace ranges (secs/km) for each zone."""
    import math

    def v_from_vo2(vo2):
        a, b, c = 0.000104, 0.182258, -(vo2 + 4.60)
        return (-b + math.sqrt(b * b - 4 * a * c)) / (2 * a)

    pct_ranges = {
        "easy":      (0.59, 0.74),
        "marathon":  (0.75, 0.84),
        "threshold": (0.83, 0.88),
        "interval":  (0.95, 1.00),
        "rep":       (1.05, 1.20),
    }
    zones = {}
    for name, (lo, hi) in pct_ranges.items():
        v_hi = v_from_vo2(lo * vdot)  # slower (higher pace value)
        v_lo = v_from_vo2(hi * vdot)  # faster
        zones[name] = {
            "pace_lo": 1000 / v_lo * 60,  # fast end
            "pace_hi": 1000 / v_hi * 60,  # slow end
        }
    return zones


def get_hr_zones(hrmax: int, hrrest: int = 50) -> list[dict]:
    """Karvonen HR zones."""
    hrr = hrmax - hrrest
    defs = [
        ("Z1 Regeneracja",  0.50, 0.60, "#6bcfff"),
        ("Z2 Aerobowa",     0.60, 0.70, "#47ffb0"),
        ("Z3 Tlenowa",      0.70, 0.80, "#e8ff47"),
        ("Z4 Próg",         0.80, 0.90, "#ffb347"),
        ("Z5 Anaerobowa",   0.90, 1.00, "#ff6b47"),
    ]
    return [
        {"name": n, "hr_lo": round(hrrest + lo * hrr), "hr_hi": round(hrrest + hi * hrr), "color": c}
        for n, lo, hi, c in defs
    ]
