# Model card: Sentinel fused risk model v1.0

| | |
|---|---|
| Task | Probability that a site cluster has a heat- or dust-related health-burden surge in the next 48 hours |
| Unit | One site cluster on one day (aggregated counts only) |
| Model | Two monotone-constrained LightGBM classifiers (one per development season), scores averaged, Platt-calibrated; a weather-free fallback model for feed outages |
| Inputs | 42 features in 12 groups: heat forecast, heat so far, acclimatisation, season, dust, heat-illness visits, respiratory visits, all-cause visits, incident reports, sickness absence, site profile, data completeness |
| Output | Calibrated probability, severity (Watch / Warning / Danger), grouped SHAP contributions, template sentence, action card |
| Owner | Risny Suha · Future Health Digital Innovation Challenge 2026 |

## Intended use

- Population-level prevention by public-health authorities and employer occupational-health teams.
- Prioritising preventive workplace measures 1–2 days ahead of heat and dust health surges.

## Out of scope (prohibited)

- Any decision about an individual worker (employment, discipline, insurance, immigration status).
- Diagnosis, triage or clinical decisions for any person.
- Automatic actions without a named human approving them.

## Training and evaluation data

- Environment: real Open-Meteo ERA5 and CAMS reanalysis, 5 Abu Dhabi districts, 2024-01-01 to 2026-11-14.
- Health and workplace feeds: synthetic, generated from the real environment (see DATA_SHEET.md).
- Development: 2024 and 2025, season-wise cross-fitting. Frozen test: 2026-01-01 to 2026-11-14.

## Performance on the 2026 hold-out

| Metric | Value |
|---|---|
| ROC-AUC | 0.893 |
| Average precision | 0.241 (base rate 0.038; fixed heat rule 0.122) |
| Brier score | 0.032 |
| Event sensitivity at operating point | 77.3% (95% CI 65.9–88.6%) |
| PPV of alert episodes | 25.9% (95% CI 17.3–35.8%) |
| False alarms per site per month | 0.48 (fixed heat rule 1.07 at the same workload) |
| Sensitivity, small vs large sites | 79% vs 76% |

## Explainability

TreeSHAP values summed into the 12 signal groups. Sentences use fixed templates filled with the row's numbers; a driver is only stated when the data support it.

## Known limitations and risks

- Trained and tested on synthetic health feeds; real-world accuracy is unknown until a pilot.
- WBGT is a temperature-humidity proxy.
- Weakest on dust-driven respiratory surges.
- Threshold drift in hotter seasons; review the alert line each season.
- Monotone constraints assume more heat, dust or illness never lowers risk, which is reasonable for this task but should be revisited with real data.

## Ethical considerations

Workers cannot opt out of aggregate surveillance at their workplace, so the system is built to minimise data (aggregates only), protect small groups (suppression, pooling), limit purpose, and keep humans accountable for every action.
