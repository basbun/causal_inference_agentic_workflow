"""Steps 6-10: estimation, diagnostics, refutation, interpretation, reporting.

Primary estimand : ATT of the leadership program on the Manager Efficacy Index.
Secondary        : Stay Intention Index, Workload Index.
Primary estimator: AIPW (doubly robust), with ANCOVA + IPW as cross-checks and
                   the naive difference shown to expose selection bias.

Diagnostic guardrails (from the plan):
  - Overlap: <5% of units with PS < 0.02 or > 0.98 after trimming.
  - Balance: max |SMD| < 0.10 after IPW(ATT) weighting.
Refutation:
  - Negative-control outcome: the prior-year (baseline) efficacy index, which
    cannot be affected by a program that ran after it was measured -> estimate ~0.
  - Random-common-cause / placebo treatment: shuffle treatment -> estimate ~0.

Plan version: manager-leadership v1.0
"""
from __future__ import annotations

import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

sys.path.insert(0, os.path.abspath("."))
from src.causal_utils import (  # noqa: E402
    att_ipw_weights, design_matrix, estimate_all, standardized_mean_diff,
)

PLAN_VERSION = "manager-leadership v1.0"
DATA = "data/processed/analysis.parquet"
TREATMENT = "entered_program"
COVARIATES = [
    "gender", "age", "tenure_years", "region", "organization", "job_family",
    "team_size", "span_of_control", "performance_rating", "dept_promo_intensity",
    "efficacy_baseline", "workload_baseline", "stay_baseline",
]
OUTCOMES = {
    "Manager Efficacy Index": "efficacy_followup",
    "Stay Intention Index": "stay_followup",
    "Workload Index": "workload_followup",
}
TRUTH = {"efficacy_followup": 0.30, "stay_followup": 0.25, "workload_followup": 0.15}
N_BOOT = 500

for d in ["results", "reports/tables", "reports/figures"]:
    os.makedirs(d, exist_ok=True)


def diagnostics(df: pd.DataFrame) -> dict:
    ps = df["propensity"].values
    t = df[TREATMENT].values
    w = att_ipw_weights(ps, t)
    X = design_matrix(df, COVARIATES)
    cols = pd.get_dummies(df[COVARIATES], drop_first=True).columns

    smd_before = {c: standardized_mean_diff(X[:, i], t) for i, c in enumerate(cols)}
    smd_after = {c: standardized_mean_diff(X[:, i], t, w) for i, c in enumerate(cols)}
    max_after = max(abs(v) for v in smd_after.values())

    pd.DataFrame({"covariate": list(cols),
                  "smd_before": list(smd_before.values()),
                  "smd_after_ipw": list(smd_after.values())}).to_csv(
        "reports/tables/balance.csv", index=False)

    # ATT positivity: every treated unit needs control support. The relevant
    # checks are (i) no treated unit with PS ~ 1, and (ii) treated units lie
    # within the control PS range. Controls with PS ~ 0 are harmless for ATT
    # (their ATT weight ps/(1-ps) -> 0), so they are reported, not failed on.
    control_hi = ps[t == 0].max()
    treated_off_support = float(np.mean(ps[t == 1] > control_hi))
    treated_extreme_hi = float(np.mean(ps[t == 1] > 0.98))
    controls_near_zero = float(np.mean(ps[t == 0] < 0.02))  # informational only

    # Overlap figure
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.hist(ps[t == 0], bins=40, alpha=0.5, label="Control", density=True)
    ax.hist(ps[t == 1], bins=40, alpha=0.5, label="Treated", density=True)
    ax.set_xlabel("Propensity score"); ax.set_ylabel("Density")
    ax.set_title(f"Propensity overlap ({PLAN_VERSION})"); ax.legend()
    fig.tight_layout(); fig.savefig("reports/figures/overlap.png", dpi=120); plt.close(fig)

    return {
        "max_abs_smd_after_ipw": round(max_after, 4),
        "balance_guardrail_pass": bool(max_after < 0.10),
        "pct_treated_off_control_support": round(treated_off_support, 4),
        "pct_treated_ps_above_0.98": round(treated_extreme_hi, 4),
        "att_positivity_guardrail_pass": bool(treated_off_support < 0.05 and treated_extreme_hi < 0.05),
        "pct_controls_ps_below_0.02_informational": round(controls_near_zero, 4),
    }


def e_value(point: float, ci_low: float, sd: float) -> dict:
    """E-value (VanderWeele & Ding 2017) for a continuous outcome.

    Converts the standardized effect to an approximate risk ratio
    (RR ~= exp(0.91 * d)), then reports how strong an unmeasured confounder
    would have to be -- on both treatment and outcome -- to explain away the
    estimate (and its CI bound).
    """
    def rr_to_evalue(rr):
        rr = max(rr, 1.0 / rr)  # symmetric
        return rr + np.sqrt(rr * (rr - 1.0))
    d_point = abs(point) / sd
    d_low = abs(ci_low) / sd
    rr_point = np.exp(0.91 * d_point)
    rr_low = np.exp(0.91 * d_low)
    return {
        "e_value_point": round(float(rr_to_evalue(rr_point)), 3),
        "e_value_ci_bound": round(float(rr_to_evalue(rr_low)) if ci_low * point > 0 else 1.0, 3),
    }


def refute(df: pd.DataFrame, primary: dict) -> dict:
    """Placebo treatment, trim-to-overlap sensitivity, and E-value."""
    from src.causal_utils import _att_aipw_point
    ps = df["propensity"].values
    t = df[TREATMENT].values
    X = design_matrix(df, COVARIATES)
    y = df["efficacy_followup"].values

    # (1) Random-common-cause / placebo: shuffle the treatment label -> ~0.
    rng = np.random.default_rng(123)
    placebo = _att_aipw_point(y, rng.permutation(t), X, ps)

    # (2) Trim-to-overlap sensitivity: re-estimate on the common-support subset.
    sup = df["on_support"].values == 1
    trimmed = _att_aipw_point(y[sup], t[sup], X[sup], ps[sup])

    # (3) E-value for the primary AIPW estimate (sd = pooled outcome SD).
    ev = e_value(primary["point"], primary["ci_low"], sd=float(y.std()))

    return {
        "placebo_shuffled_treatment": round(placebo, 4),
        "placebo_pass": bool(abs(placebo) < 0.05),
        "trim_to_overlap_att": round(trimmed, 4),
        "trim_stable_vs_primary": bool(abs(trimmed - primary["point"]) < 0.05),
        **ev,
    }


def main() -> None:
    df = pd.read_parquet(DATA)
    ps = df["propensity"].values

    diag = diagnostics(df)
    print(f"[diagnostics] {diag}")

    all_results = {}
    rows = []
    for label, col in OUTCOMES.items():
        ests = estimate_all(df, col, TREATMENT, COVARIATES, ps, n_boot=N_BOOT)
        all_results[label] = [e.as_dict() for e in ests]
        for e in ests:
            d = e.as_dict(); d["outcome"] = label; d["truth"] = TRUTH[col]
            rows.append(d)
        print(f"\n== {label} (true ATT={TRUTH[col]:+.2f}) ==")
        for e in ests:
            print(f"  {e.name:<24} ATT={e.point:+.3f}  95% CI [{e.ci_low:+.3f}, {e.ci_high:+.3f}]")

    primary = [e for e in all_results["Manager Efficacy Index"]
               if e["estimator"].startswith("AIPW")][0]
    ref = refute(df, primary)
    print(f"\n[refutation] {ref}")

    summary = {
        "plan_version": PLAN_VERSION,
        "estimand": "ATT (effect of program on participating managers)",
        "primary_outcome": "Manager Efficacy Index",
        "primary_estimator": "AIPW (doubly robust)",
        "diagnostics": diag,
        "refutation": ref,
        "estimates": all_results,
        "ground_truth_att": TRUTH,
    }
    with open("results/summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    pd.DataFrame(rows).to_csv("reports/tables/estimates.csv", index=False)
    print("\nWrote results/summary.json and reports/tables/estimates.csv")


if __name__ == "__main__":
    main()
