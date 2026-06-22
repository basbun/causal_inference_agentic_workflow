"""Step 6 (data preparation): build the analysis-ready dataset.

- Reads immutable raw data.
- Defines the admissible adjustment set (pre-treatment covariates + baseline
  outcomes only -- no post-treatment / mediator variables).
- Fits the propensity score and flags the common-support (overlap) region.
- Writes data/processed/analysis.parquet.

Plan version: manager-leadership v1.0
"""
from __future__ import annotations

import os
import sys

import pandas as pd

sys.path.insert(0, os.path.abspath("."))
from src.causal_utils import design_matrix, fit_propensity  # noqa: E402

PLAN_VERSION = "manager-leadership v1.0"
RAW = "data/raw/manager_data.csv"
OUT = "data/processed/analysis.parquet"

# Admissible adjustment set: everything measured in January (pre-treatment) plus
# the prior-year (baseline) survey indices. NO follow-up outcomes, NO retention
# (those are post-treatment / outcomes themselves).
COVARIATES = [
    "gender", "age", "tenure_years", "region", "organization", "job_family",
    "team_size", "span_of_control", "performance_rating", "dept_promo_intensity",
    "efficacy_baseline", "workload_baseline", "stay_baseline",
]
TREATMENT = "entered_program"


def main() -> None:
    df = pd.read_csv(RAW)

    # Identification guard: refuse any post-treatment variable in the adjustment set.
    forbidden = [c for c in COVARIATES if "followup" in c or c.startswith("active_") or c == "exit_month"]
    if forbidden:
        raise SystemExit(f"GUARD FAILED: post-treatment vars in adjustment set: {forbidden}")

    X = design_matrix(df, COVARIATES)
    ps = fit_propensity(X, df[TREATMENT].values)
    df["propensity"] = ps

    # Common support: keep controls/treated within the overlapping PS range.
    t = df[TREATMENT] == 1
    lo = max(ps[t].min(), ps[~t].min())
    hi = min(ps[t].max(), ps[~t].max())
    df["on_support"] = ((ps >= lo) & (ps <= hi)).astype(int)

    os.makedirs("data/processed", exist_ok=True)
    df.to_parquet(OUT, index=False)
    n_off = int((df["on_support"] == 0).sum())
    print(f"[{PLAN_VERSION}] Wrote {OUT}: {len(df):,} rows; "
          f"{n_off} off-support dropped for trimmed analyses.")
    print(f"PS range treated [{ps[t].min():.3f}, {ps[t].max():.3f}] "
          f"control [{ps[~t].min():.3f}, {ps[~t].max():.3f}]")


if __name__ == "__main__":
    main()
