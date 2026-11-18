"""Central configuration for Sentinel.

Everything region-specific lives here, so the same engine can be pointed at a new
region by editing this file only (see docs/TECHNICAL_DOCUMENTATION.md, "Scaling to a
new region").
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
REPORTS = ROOT / "reports"
WEB_DATA = ROOT / "web" / "public" / "data"

REGION_NAME = "Abu Dhabi Emirate (UAE)"
TIMEZONE = "Asia/Dubai"
START_DATE = "2024-01-01"
END_DATE = "2026-11-14"

# Chronological split. Whole seasons are held out, never random days.
# Development = 2024 + 2025 (season-wise cross-fitting: fit on one year, score the other).
# Expected values and event thresholds are learned on development data only.
TRAIN_END = "2025-12-31"
VALID_END = "2025-12-31"      # 2025 out-of-fold scores set the calibration and alert threshold
# TEST = 2026-01-01 .. END_DATE  (frozen final hold-out, scored once)


@dataclass(frozen=True)
class District:
    code: str
    name: str
    lat: float
    lon: float


DISTRICTS: list[District] = [
    District("AUH", "Abu Dhabi Island", 24.47, 54.37),
    District("MUS", "Mussafah Industrial", 24.35, 54.50),
    District("KZD", "KIZAD / Khalifa Port", 24.80, 54.65),
    District("AAN", "Al Ain", 24.21, 55.74),
    District("RUW", "Al Ruwais (Al Dhafra)", 24.11, 52.73),
]


@dataclass(frozen=True)
class SiteCluster:
    """A group of workplaces reported together. Workforce sizes are SIMULATED."""

    code: str
    district: str
    name: str
    sector: str
    workforce: int
    outdoor_share: float  # share of the workforce doing outdoor physical work
    vulnerability: float = 1.0  # relative baseline susceptibility (simulated)


SITE_CLUSTERS: list[SiteCluster] = [
    SiteCluster("AUH-C1", "AUH", "Island construction zone", "Construction", 6200, 0.75, 1.05),
    SiteCluster("AUH-C2", "AUH", "Municipal & landscaping services", "Public services", 2400, 0.60, 1.00),
    SiteCluster("AUH-C3", "AUH", "Port & logistics (Mina Zayed)", "Logistics", 900, 0.55, 0.95),
    SiteCluster("MUS-C1", "MUS", "Mussafah metal & fabrication", "Manufacturing", 8800, 0.45, 1.10),
    SiteCluster("MUS-C2", "MUS", "Mussafah workshops & garages", "Services", 5100, 0.35, 1.00),
    SiteCluster("MUS-C3", "MUS", "ICAD warehousing", "Logistics", 3300, 0.40, 0.95),
    SiteCluster("KZD-C1", "KZD", "KIZAD industrial park", "Manufacturing", 4600, 0.40, 1.00),
    SiteCluster("KZD-C2", "KZD", "Khalifa Port terminals", "Logistics", 2700, 0.65, 1.05),
    SiteCluster("AAN-C1", "AAN", "Al Ain farms & date plantations", "Agriculture", 3900, 0.85, 1.15),
    SiteCluster("AAN-C2", "AAN", "Al Ain construction", "Construction", 2900, 0.75, 1.05),
    SiteCluster("RUW-C1", "RUW", "Ruwais petrochemical complex", "Energy", 7400, 0.50, 0.95),
    SiteCluster("RUW-C2", "RUW", "Al Dhafra field & pipeline crews", "Energy", 650, 0.90, 1.20),
]

# UAE midday outdoor work ban (15 Jun - 15 Sep, 12:30-15:00) reduces exposure.
MIDDAY_BAN = ((6, 15), (9, 15))
MIDDAY_BAN_EXPOSURE_FACTOR = 0.70

# Reporting lags (days) of each simulated feed, as a real system would face.
REPORTING_LAG = {"clinic": 1, "absence": 2, "incidents": 1}

# Forecast error added to "future" weather so the model never sees perfect forecasts.
FORECAST_SD = {"wbgt": (0.9, 1.4), "pm10": (0.35, 0.50)}  # day+1, day+2 (pm10 on log scale)

# Alerting policy
ALERT_HORIZON_DAYS = 2              # predict burden in the next 48 hours
ALERT_BUDGET_PER_CLUSTER_MONTH = 3  # target average alert days, sets the threshold
COOLDOWN_DAYS = 2
SEVERITY_LEVELS = ("Watch", "Warning", "Danger")

# Privacy
SMALL_CELL_MIN = 5          # counts below this are shown as "<5"
POOL_WORKFORCE_MIN = 1000   # clusters smaller than this are pooled to district for the regulator view

# Heat thresholds on the WBGT proxy scale (the proxy reads high in humid Gulf heat,
# so it is used as a relative index; see docs/DATA_SHEET.md).
HEAT_REF_WBGT = 30.0   # heat-illness risk starts to rise above this
HOT_DAY_WBGT = 33.0    # a "hot day" for streaks and acclimatisation counting
DUST_REF_PM10 = 90.0   # ug/m3, respiratory risk rises above this daily mean

RANDOM_SEED = 2026


@dataclass(frozen=True)
class Episode:
    """A hidden scenario injected into the simulated health feeds."""

    key: str
    label: str
    cluster: str
    start: str
    days: int
    kind: str  # heat_vuln | water_failure | dust | new_intake | lookalike
    strength: float = 1.0
    meta: dict = field(default_factory=dict)


# Scenario library. Dates are hidden from the model; they are used only to score it.
EPISODES: list[Episode] = [
    # ---- training period ----
    Episode("E01", "Unacclimatised new crew, early heat", "AUH-C1", "2024-05-12", 6, "new_intake", 1.0),
    Episode("E02", "Cooling-water supply failure", "MUS-C1", "2024-07-22", 3, "water_failure", 1.1),
    Episode("E03", "Shamal dust surge, respiratory", "RUW-C1", "2024-06-03", 4, "dust", 1.0),
    Episode("E04", "Vaccination drive (look-alike)", "MUS-C2", "2024-10-14", 3, "lookalike", 1.0),
    Episode("E05", "Farm crews, humid heatwave", "AAN-C1", "2024-08-18", 5, "heat_vuln", 1.0),
    Episode("E06", "Port crews, heat + humidity", "KZD-C2", "2024-09-02", 4, "heat_vuln", 0.9),
    Episode("E07", "Dust episode, construction", "AUH-C1", "2025-03-25", 3, "dust", 0.9),
    Episode("E14", "New crew intake, port", "KZD-C2", "2024-05-26", 5, "new_intake", 1.0),
    Episode("E15", "Shade-shelter breakdown, farms", "AAN-C1", "2024-06-24", 3, "water_failure", 1.0),
    Episode("E16", "Dust surge, warehousing", "MUS-C3", "2024-04-14", 3, "dust", 1.0),
    Episode("E17", "Late-season heat, workshops", "MUS-C2", "2024-09-23", 4, "heat_vuln", 0.9),
    Episode("E18", "New crew intake, pipelines", "RUW-C2", "2024-06-09", 5, "new_intake", 1.0),
    Episode("E19", "Cooling failure, petrochemical", "RUW-C1", "2024-08-27", 3, "water_failure", 1.0),
    Episode("E20", "Municipal crews, humid heat", "AUH-C2", "2024-07-08", 4, "heat_vuln", 1.0),
    Episode("E21", "Screening day (look-alike)", "KZD-C1", "2024-12-03", 3, "lookalike", 1.0),
    Episode("E22", "Dust episode, Al Ain", "AAN-C2", "2025-04-08", 3, "dust", 1.0),
    # ---- validation period ----
    Episode("E08", "New crew intake before ban season", "AAN-C2", "2025-05-28", 6, "new_intake", 1.0),
    Episode("E09", "Shade-shelter breakdown", "KZD-C1", "2025-07-14", 3, "water_failure", 1.0),
    Episode("E10", "Pipeline crews, extreme heat", "RUW-C2", "2025-08-06", 4, "heat_vuln", 1.1),
    Episode("E11", "Dust storm, logistics", "MUS-C3", "2025-05-04", 3, "dust", 1.0),
    Episode("E12", "Screening campaign (look-alike)", "AUH-C2", "2025-11-09", 3, "lookalike", 1.0),
    Episode("E13", "Late-season heat, fabrication", "MUS-C1", "2025-09-20", 4, "heat_vuln", 0.9),
    # ---- frozen test period (2026) ----
    Episode("T01", "Unacclimatised crew, early heat", "AUH-C1", "2026-05-17", 6, "new_intake", 1.0),
    Episode("T02", "Cooling-water failure", "MUS-C1", "2026-07-08", 3, "water_failure", 1.0),
    Episode("T03", "Shamal dust surge", "RUW-C1", "2026-04-21", 4, "dust", 1.0),
    Episode("T04", "Farm crews, humid heatwave", "AAN-C1", "2026-08-11", 5, "heat_vuln", 1.0),
    Episode("T05", "Port crews, heat + humidity", "KZD-C2", "2026-06-24", 4, "heat_vuln", 0.95),
    Episode("T06", "Pipeline crews, extreme heat", "RUW-C2", "2026-07-27", 4, "heat_vuln", 1.05),
    Episode("T07", "Dust episode, warehousing", "MUS-C3", "2026-03-30", 3, "dust", 0.95),
    Episode("T08", "Shelter breakdown, industrial park", "KZD-C1", "2026-09-07", 3, "water_failure", 0.95),
    Episode("T09", "New crew intake, construction", "AAN-C2", "2026-05-31", 5, "new_intake", 0.95),
    Episode("T10", "Vaccination drive (look-alike)", "MUS-C2", "2026-10-12", 3, "lookalike", 1.0),
    Episode("T11", "Late-season heat, workshops", "MUS-C2", "2026-09-22", 4, "heat_vuln", 0.85),
]
