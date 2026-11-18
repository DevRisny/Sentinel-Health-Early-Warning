"""Turn model contributions into plain-language reasons and a proportionate action.

No generative AI is used in the alert path: sentences are filled from fixed
templates with numbers taken straight from the data, so the wording cannot
invent facts.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

GROUP_ORDER = [
    "Heat forecast", "Heat so far", "Acclimatisation", "Dust", "Heat-illness visits", "Respiratory visits",
    "All-cause visits", "Incident reports", "Sickness absence", "Site profile", "Season", "Data completeness",
]

# Groups whose positive push is worth stating to a health team.
SAYABLE = {"Heat forecast", "Heat so far", "Acclimatisation", "Dust", "Heat-illness visits", "Respiratory visits",
           "Incident reports", "Sickness absence", "All-cause visits"}


def _ratio(obs: float, exp: float) -> str:
    if not np.isfinite(obs) or not np.isfinite(exp) or exp <= 0:
        return "n/a"
    return f"{obs / exp:.1f}x"


def reason_phrase(group: str, r: pd.Series) -> str | None:
    """One evidence phrase for a signal group, using the row's own numbers."""
    if group == "Heat forecast":
        return (f"heat stress forecast to reach WBGT {r['fc_wbgt_max']:.1f} in the next 48 h "
                f"(seasonal normal {r['wbgt_normal']:.1f})")
    if group == "Heat so far":
        n = int(r['hot_streak'])
        return f"{n} consecutive hot day{'s' if n != 1 else ''}, 3-day mean WBGT {r['wbgt_3d']:.1f}"
    if group == "Acclimatisation":
        n = int(r['hot_days_ytd'])
        return f"early in the hot season ({n} hot day{'s' if n != 1 else ''} so far this year), workers not yet acclimatised"
    if group == "Dust":
        return f"dust forecast up to PM10 {np.expm1(r['fc_logpm10_max']):.0f} ug/m3 (today {r['pm10_mean']:.0f})"
    if group == "Heat-illness visits":
        return f"heat-illness visits {_ratio(r['hri_obs3'], r['hri_exp3'])} expected over the last 3 reported days"
    if group == "Respiratory visits":
        return f"respiratory visits {_ratio(r['resp_obs3'], r['resp_exp3'])} expected over the last 3 reported days"
    if group == "Incident reports":
        return f"{int(r['incidents_obs3'])} heat-related incident reports in 3 days (about {r['incidents_exp3']:.0f} expected)"
    if group == "Sickness absence":
        return f"sickness absence {_ratio(r['absent_obs3'], r['absent_exp3'])} expected"
    if group == "All-cause visits":
        return f"all-cause clinic visits {_ratio(r['allcause_obs3'], r['allcause_exp3'])} expected"
    return None


def explain_row(r: pd.Series, contrib: pd.Series, k: int = 3) -> tuple[str, list[dict]]:
    pos = contrib[[g for g in contrib.index if g in SAYABLE]].sort_values(ascending=False)
    pos = pos[pos > 0.05]
    drivers = []
    for g, v in pos.head(k).items():
        phrase = reason_phrase(g, r)
        if phrase:
            drivers.append({"group": g, "weight": round(float(v), 3), "text": phrase})
    if not drivers:
        return "No single signal stands out; risk reflects the overall season and site profile.", drivers
    lead = drivers[0]["text"]
    rest = "; ".join(d["text"] for d in drivers[1:])
    sentence = f"Risk is elevated mainly because {lead}" + (f"; also {rest}." if rest else ".")
    return sentence[0].upper() + sentence[1:], drivers


# ----------------------------------------------------------------------------- playbook
PLAYBOOK = {
    "heat": {
        "Watch": ["Brief supervisors on heat-illness signs and buddy checks",
                  "Confirm cool drinking water and shaded rest points at every work area"],
        "Warning": ["Move heavy outdoor tasks to before 10:00 and after 16:00",
                    "Enforce work-rest cycles of at least 15 min rest per hour in shade",
                    "Occupational-health nurse to check on new and returning workers"],
        "Danger": ["Pause non-essential heavy outdoor work 11:00-16:00",
                   "Set up a cooling station and stage first-aid at the site",
                   "Notify the nearest clinic to expect heat-illness cases"],
    },
    "dust": {
        "Watch": ["Share the dust forecast with site supervisors",
                  "Check stock of FFP2/N95 respirators"],
        "Warning": ["Issue respirators to outdoor crews and reduce dust-generating tasks",
                    "Advise workers with asthma or COPD to report symptoms early"],
        "Danger": ["Suspend outdoor dust-generating work during peak hours",
                   "Notify clinics to expect respiratory cases"],
    },
    "signal": {
        "Watch": ["Review the clinic and incident reports for this site cluster"],
        "Warning": ["Occupational-health nurse field visit within 24 h to verify the trend",
                    "Check water supply, shade shelters and new-worker acclimatisation plans"],
        "Danger": ["Same-day field verification by the occupational-health lead",
                   "Prepare heat-illness response measures pending verification"],
    },
}
ROLE = {"Watch": "Site safety officer", "Warning": "Occupational-health lead", "Danger": "Occupational-health lead + regulator duty officer"}


def action_card(severity: str, drivers: list[dict]) -> dict:
    groups = [d["group"] for d in drivers]
    top = groups[0] if groups else "Heat forecast"
    if top in ("Dust", "Respiratory visits"):
        kind = "dust"
    elif top in ("Heat-illness visits", "Incident reports", "Sickness absence", "All-cause visits"):
        kind = "signal"
    else:
        kind = "heat"
    return {
        "kind": kind,
        "actions": PLAYBOOK[kind].get(severity, []),
        "responsible": ROLE.get(severity, ""),
        "assumptions": [
            "Aggregated site-cluster counts only; no individual data used",
            "Health feeds in this prototype are SYNTHETIC; weather and dust are real (Open-Meteo)",
            "Recommendation only: a named person approves, modifies or dismisses",
        ],
    }
