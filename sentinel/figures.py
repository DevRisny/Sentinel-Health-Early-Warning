"""Figures for the technical documentation (light, print-friendly palette)."""
from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from .config import REPORTS  # noqa: E402

COL = {"sentinel": "#0E7C66", "baseline_a": "#E08A1E", "baseline_b": "#7A8CA3"}
NAME = {"sentinel": "Sentinel", "baseline_a": "Baseline A: fixed heat/dust line",
        "baseline_b": "Baseline B: clinic z-score rule"}


def _style(ax, title):
    ax.set_title(title, loc="left", fontsize=12, fontweight="bold", color="#14213D")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.spines["left"].set_color("#C9D3DF")
    ax.spines["bottom"].set_color("#C9D3DF")
    ax.tick_params(colors="#43536B", labelsize=9)
    ax.grid(axis="y", color="#EEF2F7")
    ax.set_axisbelow(True)


def make_all(res: dict) -> None:
    out = REPORTS / "figures"
    out.mkdir(parents=True, exist_ok=True)

    # 1. headline bars
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4))
    metrics = [("sensitivity", "Events caught (sensitivity)", False),
               ("ppv", "Alerts that were real (PPV)", False),
               ("false_alarms_per_cluster_month", "False alarms per site-cluster per month", True)]
    for ax, (k, t, lower) in zip(axes, metrics):
        keys = list(NAME)
        vals = [res["headline"][m][k] for m in keys]
        bars = ax.bar([NAME[m].split(":")[0] for m in keys], vals, color=[COL[m] for m in keys], width=0.6)
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v, f"{v:.2f}", ha="center", va="bottom", fontsize=9, color="#14213D")
        _style(ax, t + (" (lower is better)" if lower else ""))
    fig.suptitle("2026 frozen hold-out: Sentinel vs today's practice", x=0.01, ha="left", fontsize=13,
                 fontweight="bold", color="#14213D")
    fig.tight_layout()
    fig.savefig(out / "headline.png", dpi=160)
    plt.close(fig)

    # 2. budget curves
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    for m, rows in res["budget_curves"].items():
        x = [r["alert_days_per_cluster_month"] for r in rows]
        axes[0].plot(x, [r["sensitivity"] for r in rows], "o-", color=COL[m], label=NAME[m])
        axes[1].plot(x, [r["false_alarms_per_cluster_month"] for r in rows], "o-", color=COL[m], label=NAME[m])
    _style(axes[0], "Sensitivity at the same alert workload")
    _style(axes[1], "False alarms at the same alert workload")
    for ax in axes:
        ax.set_xlabel("Alert days per site-cluster per month", fontsize=9, color="#43536B")
    axes[0].legend(frameon=False, fontsize=8)
    fig.tight_layout()
    fig.savefig(out / "budget_curves.png", dpi=160)
    plt.close(fig)

    # 3. calibration
    fig, ax = plt.subplots(figsize=(4.6, 4))
    rel = res["discrimination"]["reliability"]
    ax.plot([0, 1], [0, 1], "--", color="#C9D3DF")
    ax.plot([r["pred"] for r in rel], [r["obs"] for r in rel], "o-", color=COL["sentinel"])
    mx = max(max(r["pred"] for r in rel), max(r["obs"] for r in rel)) * 1.15
    ax.set_xlim(0, mx)
    ax.set_ylim(0, mx)
    ax.set_xlabel("Predicted probability", fontsize=9)
    ax.set_ylabel("Observed frequency", fontsize=9)
    _style(ax, "Calibration (2026 hold-out)")
    fig.tight_layout()
    fig.savefig(out / "calibration.png", dpi=160)
    plt.close(fig)

    # 4. ablation
    fig, ax = plt.subplots(figsize=(7.5, 3))
    ab = res["ablation"]
    ax.barh([a["variant"] for a in ab], [a["average_precision"] for a in ab],
            color=["#9FD8CB", "#4FB39E", COL["sentinel"]])
    for i, a in enumerate(ab):
        ax.text(a["average_precision"], i, f"  AP {a['average_precision']:.3f} | sens {a['sensitivity']:.2f}",
                va="center", fontsize=9, color="#14213D")
    ax.invert_yaxis()
    _style(ax, "Each signal family earns its place (average precision)")
    ax.grid(axis="x", color="#EEF2F7")
    fig.tight_layout()
    fig.savefig(out / "ablation.png", dpi=160)
    plt.close(fig)

    # 5. importance
    fig, ax = plt.subplots(figsize=(7.5, 3.8))
    gi = res["global_importance"][:10]
    fam_col = {"environmental": "#E08A1E", "service": COL["sentinel"], "workplace": "#3E7CB1", "context": "#A7B4C6"}
    ax.barh([g["group"] for g in gi], [g["mean_abs_shap"] for g in gi], color=[fam_col[g["family"]] for g in gi])
    ax.invert_yaxis()
    _style(ax, "What drives the risk score (mean |SHAP|, by signal group)")
    ax.grid(axis="x", color="#EEF2F7")
    fig.tight_layout()
    fig.savefig(out / "importance.png", dpi=160)
    plt.close(fig)
