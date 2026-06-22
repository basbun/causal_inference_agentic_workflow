"""Generate the synthetic manager-leadership dataset described in configs/project.yaml.

This reproduces the dummy data the README references at data/raw/manager_data.csv.
It is an *observational* setup with voluntary participation, so selection into the
program is correlated with latent manager quality -- which means a naive
treated-vs-control comparison is biased upward. The script bakes in a KNOWN true
effect (ATT) so the downstream causal workflow can be validated against ground truth.

Ground-truth effects (additive, on the 1-5 survey scale):
    Manager Efficacy Index   : +0.30
    Stay Intention Index     : +0.25
    Workload Index           : +0.15

Raw data is immutable once written; never edit the CSV by hand.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SEED = 20240601
N = 9000
TRUE_EFFECT = {"efficacy": 0.30, "stay": 0.25, "workload": 0.15}

REGIONS = ["North America", "EMEA", "APAC", "LATAM"]
ORGS = ["Sales", "Engineering", "Operations", "Customer Success", "Corporate"]
JOB_FAMILIES = ["People Manager", "Technical Lead", "Program Manager", "Functional Lead"]

# Department-level promotion intensity (the "uneven promotion" note in project.yaml).
# Acts almost like an encouragement nudge: it strongly shifts uptake but is not a
# direct driver of the outcomes -- useful later as a possible instrument.
ORG_PROMO_LOGIT = {
    "Sales": 1.4,
    "Engineering": 0.2,
    "Operations": 0.6,
    "Customer Success": 1.0,
    "Corporate": -0.3,
}


def clip_scale(x: np.ndarray) -> np.ndarray:
    return np.clip(x, 1.0, 5.0)


def main() -> None:
    rng = np.random.default_rng(SEED)

    # --- Latent manager competence Q drives selection AND outcomes (the confounder) ---
    Q = rng.standard_normal(N)

    gender = rng.choice(["Female", "Male"], size=N, p=[0.46, 0.54])
    age = np.clip(rng.normal(42, 8, N).round(0), 24, 64).astype(int)
    tenure = np.clip(rng.gamma(2.0, 3.0, N).round(1), 0.1, 30.0)
    region = rng.choice(REGIONS, size=N, p=[0.4, 0.3, 0.2, 0.1])
    organization = rng.choice(ORGS, size=N, p=[0.25, 0.25, 0.2, 0.15, 0.15])
    job_family = rng.choice(JOB_FAMILIES, size=N)
    team_size = np.clip(rng.poisson(7, N), 1, None)
    span_of_control = team_size + np.clip(rng.poisson(3, N), 0, None)

    performance_rating = clip_scale(np.round(3.0 + 0.8 * Q + rng.normal(0, 0.7, N)))

    # --- Baseline (prior-year June) survey indices ---
    efficacy_baseline = clip_scale(3.2 + 0.50 * Q + rng.normal(0, 0.6, N))
    stay_baseline = clip_scale(3.5 + 0.40 * Q + rng.normal(0, 0.6, N))
    workload_baseline = clip_scale(3.0 - 0.20 * Q + rng.normal(0, 0.6, N))

    # --- Voluntary selection into the program (treatment) ---
    promo = np.array([ORG_PROMO_LOGIT[o] for o in organization])
    tenure_z = (tenure - tenure.mean()) / tenure.std()
    logit = (
        -3.95
        + 1.00 * Q
        + 0.45 * (performance_rating - 3.0)
        + promo
        + 0.30 * tenure_z
        - 0.20 * tenure_z**2  # mid-tenure managers most likely to enroll
    )
    p_treat = 1.0 / (1.0 + np.exp(-logit))
    treated = rng.binomial(1, p_treat)

    # --- Follow-up (current-year June) survey indices, with true treatment effect ---
    efficacy_followup = clip_scale(
        0.80 + 0.55 * efficacy_baseline + 0.40 * Q
        + TRUE_EFFECT["efficacy"] * treated + rng.normal(0, 0.5, N)
    )
    stay_followup = clip_scale(
        0.70 + 0.55 * stay_baseline + 0.30 * Q
        + TRUE_EFFECT["stay"] * treated + rng.normal(0, 0.5, N)
    )
    workload_followup = clip_scale(
        0.60 + 0.55 * workload_baseline - 0.10 * Q
        + TRUE_EFFECT["workload"] * treated + rng.normal(0, 0.5, N)
    )

    # --- Retention: monthly attrition hazard; treatment lowers it ---
    # Higher stay intention and competence reduce hazard.
    base_hazard_logit = -2.6 - 0.45 * (stay_followup - 3.0) - 0.25 * Q - 0.6 * treated
    monthly_p_exit = 1.0 / (1.0 + np.exp(-base_hazard_logit))
    exit_month = np.full(N, np.nan)
    for m in range(1, 13):
        still_in = np.isnan(exit_month)
        leaves = still_in & (rng.random(N) < monthly_p_exit)
        exit_month[leaves] = m

    def survived(month: int) -> np.ndarray:
        return ((np.isnan(exit_month)) | (exit_month > month)).astype(int)

    df = pd.DataFrame(
        {
            "manager_id": np.arange(1, N + 1),
            # pre-treatment covariates (measured January)
            "gender": gender,
            "age": age,
            "tenure_years": tenure,
            "region": region,
            "organization": organization,
            "job_family": job_family,
            "team_size": team_size,
            "span_of_control": span_of_control,
            "performance_rating": performance_rating,
            "dept_promo_intensity": np.round(promo, 2),
            # treatment
            "entered_program": treated.astype(int),
            # baseline (prior-year June) outcomes
            "efficacy_baseline": np.round(efficacy_baseline, 3),
            "workload_baseline": np.round(workload_baseline, 3),
            "stay_baseline": np.round(stay_baseline, 3),
            # follow-up (current-year June) outcomes
            "efficacy_followup": np.round(efficacy_followup, 3),
            "workload_followup": np.round(workload_followup, 3),
            "stay_followup": np.round(stay_followup, 3),
            # retention
            "exit_month": exit_month,
            "active_3m": survived(3),
            "active_6m": survived(6),
            "active_9m": survived(9),
            "active_12m": survived(12),
        }
    )

    out = "data/raw/manager_data.csv"
    import os

    os.makedirs("data/raw", exist_ok=True)
    df.to_csv(out, index=False)
    print(f"Wrote {out}: {len(df):,} rows, {df['entered_program'].sum():,} treated "
          f"({df['entered_program'].mean():.1%})")
    print("Ground-truth ATT (by construction):", TRUE_EFFECT)


if __name__ == "__main__":
    main()
