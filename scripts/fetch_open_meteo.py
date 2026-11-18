"""Fetch the real environmental inputs from Open-Meteo (CC BY 4.0).

    python scripts/fetch_open_meteo.py

Writes data/raw/open_meteo_daily.csv: one row per district and day with daily
temperature, dew point, humidity, wind, the daily maximum of the HOURLY WBGT proxy
(temperature and dew point at the same hour), and daily PM10 / PM2.5 / dust from
the CAMS global air-quality reanalysis.
"""
from __future__ import annotations

import csv
import json
import math
import sys
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sentinel.config import DATA_RAW, DISTRICTS, END_DATE, START_DATE, TIMEZONE  # noqa: E402

WEATHER = ("https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date={s}&end_date={e}"
           "&daily=temperature_2m_max,temperature_2m_min,dew_point_2m_mean,relative_humidity_2m_mean,wind_speed_10m_max"
           "&hourly=temperature_2m,dew_point_2m&timezone={tz}")
AIR = ("https://air-quality-api.open-meteo.com/v1/air-quality?latitude={lat}&longitude={lon}&start_date={s}&end_date={e}"
       "&hourly=pm10,pm2_5,dust&timezone={tz}")


def get(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.loads(r.read())


def vapour_pressure(td: float) -> float:
    return 6.105 * math.exp(17.27 * td / (237.7 + td))


def r1(x):
    return "" if x is None or (isinstance(x, float) and math.isnan(x)) else round(x, 1)


def mean(v: list[float]) -> float:
    return sum(v) / len(v) if v else float("nan")


def main() -> None:
    out = DATA_RAW / "open_meteo_daily.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    tz = TIMEZONE.replace("/", "%2F")
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "district", "tmax", "tmin", "dewpoint_mean", "rh_mean", "wind_max", "wbgt_max_hourly",
                    "pm10_mean", "pm10_max", "pm25_mean", "dust_mean"])
        for d in DISTRICTS:
            kw = dict(lat=d.lat, lon=d.lon, s=START_DATE, e=END_DATE, tz=tz)
            wx, aq = get(WEATHER.format(**kw)), get(AIR.format(**kw))
            daily, hourly, ah = wx["daily"], wx["hourly"], aq["hourly"]
            for i, day in enumerate(daily["time"]):
                hrs = range(i * 24, i * 24 + 24)
                wb = [0.567 * hourly["temperature_2m"][h] + 0.393 * vapour_pressure(hourly["dew_point_2m"][h]) + 3.94
                      for h in hrs if hourly["temperature_2m"][h] is not None and hourly["dew_point_2m"][h] is not None]

                def vals(k: str) -> list[float]:
                    return [ah[k][h] for h in hrs if ah[k][h] is not None]

                w.writerow([day, d.code, r1(daily["temperature_2m_max"][i]), r1(daily["temperature_2m_min"][i]),
                            r1(daily["dew_point_2m_mean"][i]), r1(daily["relative_humidity_2m_mean"][i]),
                            r1(daily["wind_speed_10m_max"][i]), r1(max(wb)) if wb else "",
                            r1(mean(vals("pm10"))), r1(max(vals("pm10"), default=float("nan"))),
                            r1(mean(vals("pm2_5"))), r1(mean(vals("dust")))])
            print(f"{d.code}: {len(daily['time'])} days")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
