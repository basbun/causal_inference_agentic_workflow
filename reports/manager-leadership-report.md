# Impact Evaluation Report — Manager Leadership Development Program

**Plan version:** manager-leadership v1.0
**Estimand:** ATT (effect on managers who participated)
**Primary outcome:** Manager Efficacy Index (June, 1–5 scale)
**Primary estimator:** AIPW (doubly robust)

> Worked example for the template. Numbers are reproducible by running
> `scripts/00_…`, `scripts/01_…`, `scripts/02_…` in order. This dataset is
> **synthetic** with a known true ATT, so the analysis can be checked against
> ground truth (Efficacy +0.30, Stay +0.25, Workload +0.15).

## Assumptions first (read before the numbers)
This is an **observational** evaluation with **voluntary** enrollment, so the
causal claim rests on **conditional exchangeability**: that the measured
covariates (manager-quality proxies, baseline survey scores, department
promotion intensity, demographics) capture everything that jointly drives both
who enrolls and their later outcomes. This is partly untestable. The remaining
identifying assumptions — positivity for the treated, consistency, and SUTVA —
are satisfied or plausible (see diagnostics).

## Headline estimates (ATT, 95% bootstrap CI)

| Outcome | Naive | ANCOVA | IPW | **AIPW (primary)** | True |
|---|---|---|---|---|---|
| Manager Efficacy Index | +1.034 | +0.427 | +0.420 | **+0.417 [0.364, 0.465]** | +0.30 |
| Stay Intention Index | +0.767 | +0.305 | +0.309 | **+0.303 [0.250, 0.346]** | +0.25 |
| Workload Index | −0.112 | +0.072 | +0.055 | **+0.060 [0.019, 0.104]** | +0.15 |

**What the adjustment did.** The naive comparison massively overstates the
effect (+1.03 on efficacy) because better, more motivated managers
self-selected into the program. Backdoor adjustment removes roughly three
quarters of that bias. The Workload Index is the clearest cautionary tale: the
naive estimate is *negative* (trained managers report worse workload), but that
is pure selection — once we adjust, the sign flips to a small positive effect.

## Diagnostics
- **Covariate balance:** max |SMD| after IPW(ATT) weighting = **0.023** (< 0.10
  guardrail). ✅ Pass.
- **ATT positivity:** only **0.35%** of treated managers fall outside the
  control propensity range, and **0%** have PS > 0.98. ✅ Pass.
  (≈41% of *controls* sit at PS < 0.02 — expected for a rare program and
  harmless for ATT, since those controls carry ≈0 weight.)
- See `reports/figures/overlap.png` for the propensity overlap.

## Refutation / sensitivity
- **Placebo treatment** (labels shuffled): ATT = **−0.028** ≈ 0. ✅ Pass — the
  pipeline does not manufacture an effect from noise.
- **Trim-to-overlap:** ATT = **0.416**, essentially identical to the full-sample
  estimate. ✅ Stable.
- **E-value:** **2.45** (CI bound **2.27**). An unmeasured confounder would need
  to be associated with both enrollment and efficacy by a risk ratio of ~2.4×,
  beyond the measured covariates, to explain away the estimate. Manager
  motivation is a plausible candidate at moderate strength, so some upward
  residual bias is likely — consistent with the estimate (+0.42) sitting above
  the true value (+0.30).

## Interpretation (language-calibrated)
The results are **consistent with a positive causal effect** of the leadership
program on participating managers: roughly a **+0.3 to +0.4 point** gain in
self-reported Manager Efficacy and a **~+0.3 point** gain in Stay Intention on
the 1–5 scale, for the kind of manager who chooses to attend (the ATT). The
Workload effect is small and least robust. We avoid the unqualified "the program
*causes*…" phrasing because one identifying assumption (no unmeasured
confounding) cannot be fully verified and the E-value indicates moderate, not
overwhelming, robustness.

## Decision-relevant takeaway
For the HR review: the evidence supports **continuing the program**, with the
caveat that gains are measured on self-reported indices for self-selected
participants and are partly inflated by who opts in. Two strengthening steps
before scaling: (1) corroborate with the behavioral retention outcome, and (2)
introduce an element of *as-good-as-random* encouragement (e.g., randomized
invitations in some departments) so the next evaluation can lean on an
instrument rather than on the no-unmeasured-confounding assumption.

## Residual risks
1. Unmeasured manager motivation (quantified by the E-value above).
2. Common-method bias in self-reported survey indices.
3. Limited transportability across departments with different uptake dynamics.
