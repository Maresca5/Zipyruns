"""Strava API helpers — OAuth, activity fetch, VDOT, Riegel, zones."""
import math
import requests
import pandas as pd
import numpy as np


# ── Daniels VDOT math ─────────────────────────────────────────────────────────

def estimate_vdot(dist_km: float, time_s: float) -> float | None:
    """Estimate VDOT from any effort using Daniels' formula."""
    if dist_km < 0.5 or time_s < 30:
        return None
    t   = time_s / 60
    v   = dist_km * 1000 / t
    vo2 = -4.60 + 0.182258 * v + 0.000104 * v * v
    pct = (0.8
           + 0.1894393 * math.exp(-0.012778 * t)
           + 0.2989558 * math.exp(-0.1932605 * t))
    vdot = vo2 / pct
    return round(vdot, 2) if 18 < vdot < 92 else None


# keep old private name as alias so predictions.py import still works
_estimate_vdot = estimate_vdot


def vdot_to_race_time(vdot: float, dist_km: float) -> float:
    """Predict race time (seconds) for given VDOT and distance (binary search)."""
    lo, hi = 0.5, 700.0
    for _ in range(64):
        mid = (lo + hi) / 2
        v   = dist_km * 1000 / mid
        vo2 = -4.60 + 0.182258 * v + 0.000104 * v * v
        pct = (0.8
               + 0.1894393 * math.exp(-0.012778 * mid)
               + 0.2989558 * math.exp(-0.1932605 * mid))
        if vo2 / pct < vdot:
            hi = mid
        else:
            lo = mid
    return (lo + hi) / 2 * 60


def riegel_predict(ref_dist: float, ref_time_s: float, target_dist: float) -> float:
    return ref_time_s * (target_dist / ref_dist) ** 1.06


def get_training_paces(vdot: float) -> dict:
    """Return Daniels training pace ranges (secs/km) keyed by zone name."""
    pct_ranges = {
        "easy":      (0.59, 0.74),
        "marathon":  (0.75, 0.84),
        "threshold": (0.83, 0.88),
        "interval":  (0.95, 1.00),
        "rep":       (1.05, 1.20),
    }
    zones = {}
    for name, (lo, hi) in pct_ranges.items():
        v_fast = _v_from_vo2(hi * vdot)
        v_slow = _v_from_vo2(lo * vdot)
        zones[name] = {
            "pace_lo": 1000 / v_fast * 60,  # faster end (lower sec/km)
            "pace_hi": 1000 / v_slow * 60,  # slower end
        }
    return zones


def _v_from_vo2(vo2: float) -> float:
    """m/min from VO2 (quadratic formula)."""
    a, b, c = 0.000104, 0.182258, -(vo2 + 4.60)
    disc = b * b - 4 * a * c
    return (-b + math.sqrt(max(disc, 0))) / (2 * a)


def get_hr_zones(hrmax: int, hrrest: int = 50) -> list:
    hrr = hrmax - hrrest
    return [
        {"name": n, "hr_lo": round(hrrest + lo * hrr), "hr_hi": round(hrrest + hi * hrr), "color": c}
        for n, lo, hi, c in [
            ("Z1 Regeneracja",  0.50, 0.60, "#6bcfff"),
            ("Z2 Aerobowa",     0.60, 0.70, "#47ffb0"),
            ("Z3 Tlenowa",      0.70, 0.80, "#e8ff47"),
            ("Z4 Próg",         0.80, 0.90, "#ffb347"),
            ("Z5 Anaerobowa",   0.90, 1.00, "#ff6b47"),
        ]
    ]


# ── Strava API ────────────────────────────────────────────────────────────────

def exchange_token(client_id, client_secret, code):
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={"client_id": client_id, "client_secret": client_secret,
              "code": code, "grant_type": "authorization_code"},
        timeout=10,
    )
    return resp.json() if resp.ok else None


def refresh_access_token(client_id, client_secret, refresh_token):
    resp = requests.post(
        "https://www.strava.com/oauth/token",
        data={"client_id": client_id, "client_secret": client_secret,
              "refresh_token": refresh_token, "grant_type": "refresh_token"},
        timeout=10,
    )
    return resp.json() if resp.ok else None


def fetch_activities(access_token: str, n: int = 100) -> pd.DataFrame:
    """Fetch up to n run activities, return enriched DataFrame."""
    all_acts, page = [], 1
    headers = {"Authorization": f"Bearer {access_token}"}

    while len(all_acts) < n:
        resp = requests.get(
            "https://www.strava.com/api/v3/athlete/activities",
            headers=headers,
            params={"per_page": min(50, n - len(all_acts)), "page": page},
            timeout=15,
        )
        if not resp.ok:
            break
        batch = resp.json()
        if not batch:
            break
        all_acts.extend(batch)
        if len(batch) < 50:
            break
        page += 1

    if not all_acts:
        return pd.DataFrame()

    df = pd.DataFrame(all_acts)
    df = df[df["type"].isin(["Run", "VirtualRun", "TrailRun"])].copy()
    if df.empty:
        return df

    df["date"]       = pd.to_datetime(df["start_date_local"])
    df["dist_km"]    = df["distance"] / 1000
    df["duration_s"] = df["moving_time"].astype(float)
    df["pace_s_km"]  = df["duration_s"] / df["dist_km"].replace(0, np.nan)

    # optional HR columns — may not exist
    df["avg_hr"] = pd.to_numeric(df.get("average_heartrate", pd.NA), errors="coerce")
    df["max_hr"] = pd.to_numeric(df.get("max_heartrate",     pd.NA), errors="coerce")
    df["elev_gain"] = pd.to_numeric(df.get("total_elevation_gain", 0), errors="coerce").fillna(0)

    df["vdot"] = df.apply(lambda r: estimate_vdot(r["dist_km"], r["duration_s"]), axis=1)
    df["vdot"] = pd.to_numeric(df["vdot"], errors="coerce")

    cols = ["date", "name", "dist_km", "duration_s", "pace_s_km", "avg_hr", "max_hr", "elev_gain", "vdot"]
    return df[cols].sort_values("date", ascending=False).reset_index(drop=True)
