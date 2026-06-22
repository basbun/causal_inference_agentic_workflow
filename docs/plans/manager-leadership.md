# Plan: Manager Leadership Development Program Evaluation

**Plan version:** manager-leadership v1.0
**Estimand:** ATT (effect of the program on managers who participated)

> This plan was produced as the worked example for the template, following the
> 10-step canonical workflow in `.github/skills/causal-inference/SKILL.md`.

## 1. Objective
Estimate the causal effect of the Jan–Mar leadership development program on
manager survey outcomes (primary: Manager Efficacy Index) and retention, to
inform whether HR should continue scaling the program.

## 2. Structural EDA findings (eligibility, overlap, zero-cells)
- Treatment is rare: 570 / 9,000 managers (6.3%) participated.
- No structural zero-cells: every region / organization / job-family level
  contains both treated and control managers.
- Propensity range: treated [0.002, 0.652], control [0.000, 0.609]. Because
  treatment is rare, most controls have PS ≈ 0. **For an ATT estimand this is
  not a positivity violation** — what matters is that every *treated* unit has
  control support, which holds (only 0.35% of treated lie above the control PS
  max). The naive "<5% with PS<0.02" rule is inappropriate here and is replaced
  by the ATT-specific positivity check below.

## 3. Target trial description
Hypothetical RCT: among all eligible managers in post in January, randomize
access to the 3-month program; measure the June survey indices and 12-month
retention. The observational data approximates this trial by adjusting for all
pre-treatment determinants of both enrollment and outcomes (manager quality
proxies, baseline survey scores, department promotion intensity).

## 4. Causal question
"What is the effect of entering the leadership development program at January
(t₀) on the June Manager Efficacy Index over a 6-month window, among managers
who chose to participate, expressed as the ATT?"

## 5. Estimand
**ATT** — the effect on participating managers. Chosen because participation is
voluntary; the decision-relevant question is whether the program helped the
people who actually take it, not a forced roll-out to everyone.

## 6. Unit of analysis
Individual manager (cross-section with one pre-treatment baseline and one
post-treatment follow-up per manager).

## 7. DAG / causal structure
```
  Manager quality / motivation (Q, partially unobserved)
        |               \
        v                v
  performance,        Enrollment (T) ----> Efficacy_followup (Y)
  baseline scores  ^        ^                    ^
        |          |        |                    |
        +----------+   dept_promo_intensity      |
                                                 |
  baseline_efficacy --------------------(direct)-+
```
- **Confounders (adjust):** baseline survey indices, performance rating, tenure,
  team size, span of control, demographics, organization/region/job family,
  dept promotion intensity.
- **Unobserved common cause:** latent manager motivation/competence (Q), only
  partly captured by the observed proxies → residual-confounding risk.
- **No mediators or colliders** are placed in the adjustment set. Follow-up
  outcomes and retention are post-treatment and excluded from adjustment.

## 8. Identification block
```
Identification strategy: backdoor adjustment (conditional exchangeability)
Required assumptions:
  1. Conditional exchangeability given the adjustment set (no unmeasured
     confounding) — IDENTIFYING, partly untestable.
  2. Positivity for the treated (ATT) — every treated unit has control support —
     TESTABLE, checked in diagnostics.
  3. Consistency / well-defined treatment version — IDENTIFYING.
  4. SUTVA / no interference between managers — IDENTIFYING, plausible.
Identification status: identified (conditional on assumption 1)
```

## 9. Treatment timing / assignment mechanism
Voluntary enrollment in Jan–Mar; pre-treatment covariates measured in January;
outcomes measured the following June. No staggered timing — single cohort.

## 10. Proposed estimator with justification
- **Primary: AIPW (doubly robust ATT).** Robust to misspecification of either
  the outcome model or the propensity model. Matches a backdoor design with a
  rich, mostly-observed confounder set.
- **Cross-checks:** ANCOVA (OLS with treatment + covariates) and IPW(ATT).
  Agreement across all three is evidence the estimate is not an artifact of one
  modeling choice. The naive difference is reported only to expose selection bias.

## 11. Diagnostics and falsification tests (numeric thresholds)
- **Balance:** max |SMD| after IPW(ATT) weighting **< 0.10**.
- **ATT positivity:** share of treated units above control PS support **< 5%**
  AND share of treated with PS > 0.98 **< 5%**.

## 12. Refutation plan
- **Placebo / random-common-cause:** shuffle treatment labels → ATT ≈ 0
  (|estimate| < 0.05).
- **Trim-to-overlap:** re-estimate on the common-support subset; should be
  stable (within 0.05 of primary).
- **E-value (unobserved confounding):** report how strong an unmeasured
  confounder would need to be to explain away the estimate and its CI bound.

## 13. Inference strategy
Nonparametric bootstrap (500 resamples) for SEs and percentile 95% CIs.
Treatment is assigned at the individual level, so individual-level resampling is
appropriate. The propensity model is **refit within each bootstrap resample** so
that first-stage estimation error is propagated into the IPW/AIPW intervals
(treating the estimated propensity as fixed would not reflect the estimator's
true sampling distribution).

## 14. Files to inspect/change
`scripts/00_generate_dummy_data.py`, `scripts/01_prepare_data.py`,
`scripts/02_estimate.py`, `src/causal_utils.py`.

## 15. Output artifacts
`results/summary.json`, `reports/tables/estimates.csv`,
`reports/tables/balance.csv`, `reports/figures/overlap.png`,
`reports/manager-leadership-report.md`.

## 16. Residual risks (pre-mortem)
1. **Unmeasured motivation (Q).** Proxies don't fully capture why a manager
   enrolls; residual confounding likely inflates the estimate. Mitigation:
   E-value sensitivity; report as "consistent with" not "proven."
2. **Self-report common-method bias.** Trained managers may rate themselves
   higher independent of real change. Mitigation: cross-check with the
   behavioral retention outcome.
3. **Effect heterogeneity by department.** Promotion-heavy departments may have
   different responders, so the pooled ATT may not transport. Mitigation: note
   limited external validity; CATE analysis is future work.

## 17. Risks / rollback notes
Raw data is immutable. All artifacts are reproduced by re-running the three
scripts in order; delete `data/processed/` and `results/` to reset.
