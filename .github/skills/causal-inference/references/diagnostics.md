# Diagnostics

Detailed procedures for Step 7 of the workflow. Diagnostics are not optional — they are the difference between a claim your data supports and one it does not. For symptom → cause → fix when a diagnostic fails, see `gotchas-and-diagnostics.md`.

**Key principle:** diagnostics check whether the *data* can support the identification strategy you chose. They cannot validate the untestable assumptions themselves (no unmeasured confounding, exclusion restriction, parallel trends in the post-period) — those stay assumptions. But they can reveal when the data are so poorly suited to the method that no estimate is credible.

## Contents

1. [Overlap and positivity](#overlap-and-positivity)
2. [Covariate balance](#covariate-balance)
3. [Functional-form misspecification](#functional-form-misspecification)
4. [First-stage strength (IV)](#first-stage-strength-iv)
5. [Pre-trends and event studies (DiD)](#pre-trends-and-event-studies-did)
6. [Density continuity (RDD)](#density-continuity-rdd)
7. [Covariate continuity at cutoffs (RDD)](#covariate-continuity-at-cutoffs-rdd)
8. [Residual autocorrelation (ITS)](#residual-autocorrelation-its)
9. [Pre-period fit (synthetic control)](#pre-period-fit-synthetic-control)
10. [Influence and leverage](#influence-and-leverage)
11. [Clustering and dependence](#clustering-and-dependence)
12. [Nuisance-model quality (DML)](#nuisance-model-quality-dml)
13. [Diagnostic checklist by design](#diagnostic-checklist-by-design)

---

## Overlap and positivity

**The single most important diagnostic for any adjustment-based method.** More important than VIF, more important than R², more important than coefficient significance.

### What it is

Positivity means every covariate stratum contains both treated and untreated units. When positivity fails, the estimator extrapolates from regions of the covariate space where one treatment arm simply does not exist. No amount of clever modeling recovers what the data cannot see.

Overlap is the empirical manifestation of positivity: after fitting a propensity model, do treated and untreated units span the same range of predicted probabilities?

### How to check

```python
import numpy as np
import matplotlib.pyplot as plt
from sklearn.linear_model import LogisticRegression

W = ["w1", "w2", "w3"]
T = df["treatment"].values
X = df[W].values

ps = LogisticRegression(max_iter=1000).fit(X, T).predict_proba(X)[:, 1]

fig, ax = plt.subplots(figsize=(7, 4))
ax.hist(ps[T == 1], bins=40, alpha=0.5, label="Treated", density=True)
ax.hist(ps[T == 0], bins=40, alpha=0.5, label="Control", density=True)
ax.set(xlabel="Propensity score", ylabel="Density",
       title="Overlap check — both distributions should span [0, 1]")
ax.legend()

# Numeric check
print(f"Treated PS:  min {ps[T==1].min():.3f}  max {ps[T==1].max():.3f}")
print(f"Control PS:  min {ps[T==0].min():.3f}  max {ps[T==0].max():.3f}")
print(f"Extreme PS (< 0.05 or > 0.95): {((ps < 0.05) | (ps > 0.95)).mean():.1%}")
```

### What to look for

**Good overlap:**
- Both densities span roughly the same range
- Neither density has a long tail extending into a region the other avoids
- Few or no extreme propensities near 0 or 1

**Bad overlap:**
- A region where only treated (or only control) units exist
- Bimodal distributions (treated cluster near 1, control near 0) — often a sign that treatment is near-deterministic given the covariates, which is itself informative
- > 5% of units with PS < 0.02 or > 0.98

### What to do when overlap fails

| Problem | Response |
|---|---|
| Extreme propensities in tails | Trim (drop units with PS outside [0.1, 0.9]) and report ATE-on-overlap |
| Region of no common support | Restrict estimand to the supported region; use matching which enforces support |
| Near-deterministic treatment | The real question is why. Rethink the DAG — maybe a confounder is near-perfectly explaining treatment, in which case effect separation is fundamentally weak |
| Severe imbalance + small sample | Change the estimand. ATT (using matching or IPW-for-treated) often has better support than ATE |

**Report which estimand you ended up with.** "ATE on the overlap region" is not the same as "ATE" — say so.

### Overlap weights as an alternative

Overlap weights (Li, Morgan, Zaslavsky 2018) weight by `p(1−p)` rather than `1/p` and `1/(1−p)`. They downweight extreme-propensity units instead of trimming them, and the target estimand becomes the ATE on the overlap population — usually the most data-supported subset.

```python
# Overlap weights
w_overlap = np.where(T == 1, 1 - ps, ps)

# Weighted difference in means
ate_overlap = (
    np.average(df["y"][T == 1], weights=w_overlap[T == 1])
    - np.average(df["y"][T == 0], weights=w_overlap[T == 0])
)
```

---

## Covariate balance

After matching, weighting, or any adjustment procedure, check that covariates are balanced across treatment arms.

### Standardized mean differences (SMD)

```python
import numpy as np

def smd(x, t, w=None):
    """Standardized mean difference between treated (t=1) and control (t=0)."""
    if w is None:
        w = np.ones_like(t, dtype=float)
    m1 = np.average(x[t == 1], weights=w[t == 1])
    m0 = np.average(x[t == 0], weights=w[t == 0])
    v1 = np.average((x[t == 1] - m1) ** 2, weights=w[t == 1])
    v0 = np.average((x[t == 0] - m0) ** 2, weights=w[t == 0])
    return (m1 - m0) / np.sqrt((v1 + v0) / 2)

for col in W:
    pre = smd(df[col].values, T)
    post = smd(df[col].values, T, w=w_ipw)   # after weighting
    print(f"{col:20s}  SMD pre: {pre:+.3f}   post: {post:+.3f}")
```

**Thresholds:**
- |SMD| < 0.1 — acceptable
- 0.1 ≤ |SMD| < 0.25 — concerning; re-examine the propensity model
- |SMD| ≥ 0.25 — imbalanced; adjustment has failed for this covariate

### Variance ratios

For each covariate, the variance ratio (treated / control) should be close to 1 after adjustment. Ratios outside [0.5, 2.0] indicate the adjustment has changed central tendency but not dispersion — often a sign of misspecification.

### Love plot

Visualize SMDs before and after adjustment for all covariates in one chart. A good adjustment produces a tight cluster of post-adjustment SMDs near zero. This plot is the standard diagnostic in observational studies — include it.

```python
import matplotlib.pyplot as plt

smds_pre  = np.array([smd(df[c].values, T) for c in W])
smds_post = np.array([smd(df[c].values, T, w=w_ipw) for c in W])

fig, ax = plt.subplots(figsize=(6, 0.3 * len(W) + 1))
y = np.arange(len(W))
ax.scatter(smds_pre, y, label="Unadjusted", marker="o")
ax.scatter(smds_post, y, label="Weighted", marker="s")
ax.axvline(0, color="k", lw=0.5)
ax.axvline(0.1, color="r", lw=0.5, ls="--")
ax.axvline(-0.1, color="r", lw=0.5, ls="--")
ax.set_yticks(y); ax.set_yticklabels(W); ax.set_xlabel("SMD")
ax.legend()
```

---

## Functional-form misspecification

Even with the right covariates, a rigid linear model can leave residual confounding when relationships are nonlinear or involve interactions.

### Residual diagnostics

```python
import statsmodels.formula.api as smf
import matplotlib.pyplot as plt

model = smf.ols("y ~ treatment + w1 + w2 + w3", data=df).fit(cov_type="HC3")

# Residuals vs each continuous covariate
for col in ["w1", "w2", "w3"]:
    fig, ax = plt.subplots()
    ax.scatter(df[col], model.resid, alpha=0.3)
    ax.axhline(0, color="k", lw=0.5)
    ax.set(xlabel=col, ylabel="Residual")
    # A non-flat pattern suggests missed nonlinearity in this covariate
```

Clear curvature in any plot indicates the covariate's relationship with the outcome is nonlinear beyond what the linear term captures. Add splines, polynomials, or interactions.

### Flexible-benchmark comparison

Compare the linear estimate to a Double ML estimate with flexible nuisance learners on the same adjustment set. Large divergence without a substantive reason indicates the parametric model is leaving residual confounding.

```python
# See code-recipes.md for full DoubleML pattern
# Rule of thumb: if linear OLS and DML with gradient boosting give qualitatively
# different answers, trust DML and investigate why the linear form fails.
```

### RESET-style test

```python
# Add fitted-value powers as regressors; a non-zero coefficient indicates misspecification
yhat = model.fittedvalues
df["yhat2"] = yhat ** 2
df["yhat3"] = yhat ** 3

reset = smf.ols("y ~ treatment + w1 + w2 + w3 + yhat2 + yhat3", data=df).fit()
print(reset.f_test("yhat2 = yhat3 = 0"))
# Small p-value → misspecification
```

---

## First-stage strength (IV)

Weak instruments cause 2SLS to be biased toward OLS with misleadingly tight CIs. The classic rule of thumb (F > 10) is insufficient in realistic settings.

```python
from linearmodels.iv import IV2SLS

iv = IV2SLS.from_formula(
    "y ~ 1 + w1 + w2 + [treatment ~ z1 + z2]",
    data=df,
).fit(cov_type="robust")

print(iv.first_stage)       # partial F-stat on excluded instruments per endogenous var
```

### Modern guidance

- **Effective F (Montiel Olea–Pflueger)** for heteroskedastic or clustered settings — the standard F can be misleading. Most IV packages now report this by default.
- **Always use weak-IV-robust inference** (Anderson-Rubin confidence interval) for the second-stage coefficient, regardless of the F. AR CIs have correct coverage even when the instrument is weak. See `refutation-and-sensitivity.md` for the recipe.

### Red flags

- Partial F < 10 → weak; use AR CI
- Partial F between 10 and 20 → borderline; report AR alongside 2SLS
- Reduced-form coefficient (outcome on instrument directly) has the opposite sign from 2SLS → something is wrong, investigate
- First-stage F changes dramatically when adding or removing covariates → first stage is sensitive to specification

---

## Pre-trends and event studies (DiD)

Pre-trends tests are **consistent with** parallel trends; they do not **prove** it.

### Visual check

Plot average outcomes by treatment status over the pre-treatment period. Lines should track in parallel.

### Event-study regression

```python
import statsmodels.formula.api as smf

df["event_time"] = df["time"] - df["treat_time"]
df["et_bin"]     = df["event_time"].clip(-5, 5).fillna(-999).astype(int)

evt = smf.ols(
    "y ~ C(et_bin, Treatment(reference=-1)) + C(unit) + C(time)",
    data=df[df["et_bin"] != -999],
).fit(cov_type="cluster", cov_kwds={"groups": df["unit"]})

# Extract pre-period coefficients with CIs
import pandas as pd
coefs = evt.params.filter(like="et_bin")
ci    = evt.conf_int().filter(like="et_bin", axis=0)
```

Plot the coefficients with 95% intervals. The pre-period (event time < 0) should be flat and centered on zero.

### Interpretation

| Pre-period pattern | Meaning |
|---|---|
| Flat near zero, all CIs cover zero | Consistent with parallel trends — proceed with DiD |
| Drift (trend in pre-period coefficients) | Parallel trends violated — do not use DiD; try synthetic control or unit-specific trends |
| One or two pre-period coefficients significant, no pattern | Likely multiple testing; inspect the magnitude and the overall pattern |
| Large, significant, close to treatment date | Likely anticipation — treated units changed behavior before the official treatment |

**Passing a pre-trends test does not prove parallel trends in the post-treatment period.** Unobserved factors could cause trends to diverge only after treatment. State this limitation.

---

## Density continuity (RDD)

RDD requires that agents cannot precisely manipulate the running variable to place themselves on the preferred side of the cutoff. A density discontinuity at the cutoff is evidence of manipulation.

```python
# pip install rddensity
# from rddensity import rddensity
# out = rddensity(X=df["x"].values, c=cutoff)
# print(out)  # H0: density continuous at cutoff

# Visual version:
import matplotlib.pyplot as plt
import numpy as np

x = df["x"].values
bins = np.linspace(x.min(), x.max(), 80)
fig, ax = plt.subplots()
ax.hist(x, bins=bins, alpha=0.7)
ax.axvline(cutoff, color="red", linestyle="--")
ax.set(xlabel="Running variable", ylabel="Count", title="Density at cutoff")
```

**Interpretation:**
- p > 0.10 in formal test, no visible spike near cutoff → pass
- p < 0.05 or a visible spike on one side → manipulation; RDD is invalid at this cutoff

This is a **disqualifying** failure. Do not try to patch it with bandwidth choices.

---

## Covariate continuity at cutoffs (RDD)

Pre-treatment covariates should be continuous across the cutoff. If they jump, assignment is not as-good-as-random near the cutoff.

```python
from rdrobust import rdrobust

for cov in ["age", "baseline_income", "prior_outcome"]:
    r = rdrobust(y=df[cov], x=df["x"], c=cutoff, p=1)
    est = float(r.coef.iloc[0, 0])
    se  = float(r.se.iloc[0, 0])
    print(f"{cov}: jump = {est:+.3f} (SE {se:.3f}) — should be ≈ 0")
```

A significant jump in any pre-treatment covariate is a red flag. The cutoff is not producing quasi-random variation; something else correlated with the covariate is changing at the threshold.

---

## Residual autocorrelation (ITS)

ITS assumes the pre-trend model extrapolates cleanly. Autocorrelated residuals violate this and inflate apparent significance.

```python
import statsmodels.stats.stattools as sms
from statsmodels.graphics.tsaplots import plot_acf, plot_pacf
import matplotlib.pyplot as plt

resid = its_model.resid

dw = sms.durbin_watson(resid)
print(f"Durbin-Watson: {dw:.2f}")   # ≈ 2 ideal; < 1.5 or > 2.5 is concerning

fig, axes = plt.subplots(1, 2, figsize=(10, 4))
plot_acf(resid, lags=20, ax=axes[0])
plot_pacf(resid, lags=20, ax=axes[1])
```

**Interpretation:**
- DW 1.5–2.5, ACF spikes within the band → pass
- DW outside [1.5, 2.5], or clear ACF/PACF spikes → autocorrelation present; add AR terms (use `statsmodels.tsa.arima.model.ARIMA` with an intervention regressor) or move to a state-space model

---

## Pre-period fit (synthetic control)

Synthetic control must closely track the treated unit before treatment. Poor pre-fit means the synthetic counterfactual is not valid.

```python
import numpy as np

pre_rmspe = np.sqrt(np.mean((treated_pre - synthetic_pre) ** 2))
outcome_scale = np.std(treated_pre)

print(f"Pre-RMSPE: {pre_rmspe:.3f}")
print(f"Pre-RMSPE as % of outcome SD: {pre_rmspe / outcome_scale:.1%}")
```

**Rule of thumb:** pre-RMSPE < 10% of the post-treatment gap (or well under one standard deviation of the outcome) for a credible match.

Also inspect the **donor-weight distribution**. If two or three donors carry most of the weight and a fourth is dropped and the result changes, the synthetic control is fragile — see leave-one-out refutation in `refutation-and-sensitivity.md`.

---

## Influence and leverage

A handful of high-influence observations can drive a treatment-effect estimate. Always check.

```python
import matplotlib.pyplot as plt

infl = model.get_influence()
cooks = infl.cooks_distance[0]
leverage = infl.hat_matrix_diag

fig, ax = plt.subplots()
ax.scatter(leverage, model.resid_pearson, s=20 * cooks / cooks.max())
ax.set(xlabel="Leverage", ylabel="Standardized residual",
       title="Influence plot (marker size ∝ Cook's distance)")

# Flag suspicious points
thresh = 4 / len(df)
suspicious = np.where(cooks > thresh)[0]
print(f"{len(suspicious)} observations exceed Cook's D threshold ({thresh:.4f})")
```

If dropping a small number of high-Cook's-D observations changes the point estimate meaningfully, report the estimate both ways.

---

## Clustering and dependence

If observations within a unit (user, firm, classroom, village) are correlated, naive standard errors are too small. The level of clustering is determined by the treatment-assignment mechanism, not by convenience.

```python
# Cluster at the level treatment varies
model = smf.ols("y ~ treatment + w1 + w2", data=df).fit(
    cov_type="cluster",
    cov_kwds={"groups": df["village_id"]},
)
```

### Rules of thumb

- Few clusters (< 30) → cluster-robust SEs are biased downward; use wild cluster bootstrap (no mature Python package — roll your own or use R's `fwildclusterboot`)
- Treatment varies at cluster level → cluster at that level; within-cluster variation only → cluster at finer level
- Panel data with unit-and-time effects → two-way clustering

When in doubt, cluster at the **coarsest plausible level**. Under-clustering inflates false-positive rates.

---

## Nuisance-model quality (DML)

For Double ML, the asymptotic guarantees depend on nuisance models converging at rate > n^{1/4}. Check the out-of-fold quality directly.

```python
# After fitting DoubleMLPLR or DoubleMLIRM
# Access the nuisance predictions and compare to outcomes / treatments

# Outcome nuisance — out-of-fold R²
from sklearn.metrics import r2_score, roc_auc_score

# (Adapt to your fitted DoubleMLData object; the pattern:)
y_hat_oof = model.predictions["ml_g"].flatten()  # or similar accessor
r2 = r2_score(y_true, y_hat_oof)

# Treatment nuisance (binary T) — out-of-fold AUC
t_hat_oof = model.predictions["ml_m"].flatten()
auc = roc_auc_score(t_true, t_hat_oof)

print(f"Outcome R² (out-of-fold): {r2:.3f}")
print(f"Treatment AUC (out-of-fold): {auc:.3f}")
```

**Interpretation:**
- Outcome R² near zero → the outcome model has no predictive power; DML will not outperform simple adjustment
- Treatment AUC near 0.5 → treatment is unpredictable from covariates, which is either (a) a positivity dream (great) or (b) a sign that your covariates are not actually the confounders (bad — rethink the DAG)
- Treatment AUC > 0.95 → near-deterministic treatment; overlap is catastrophic

Also check propensity-score trimming impact on the final estimate; if results depend sensitively on the trimming threshold, the effect is not well-supported.

---

## Diagnostic checklist by design

Minimum diagnostics to run and report, by design. Skip none.

| Design | Required diagnostics |
|---|---|
| Backdoor (OLS / matching / IPW) | Overlap plot; SMD balance table; residual plots; influence check |
| AIPW / Double ML | Overlap; nuisance R²/AUC; trimming sensitivity; stability across learners |
| IV | First-stage effective F; reduced form; AR CI; exclusion-restriction narrative |
| DiD (two-period) | Event-study plot; pre-period coefficient table; clustered SEs |
| Staggered DiD | Cohort-specific pre-trends; Goodman-Bacon decomposition; compare TWFE vs robust estimator |
| Synthetic control | Pre-RMSPE; donor-weight distribution; convex-hull check |
| RDD | Density test (McCrary / CCT); covariate continuity at cutoff; bandwidth sensitivity; polynomial-order sensitivity |
| ITS | Durbin-Watson; ACF/PACF of residuals; placebo intervention date |
| Front-door | Justify that the mediator intercepts all effect; check backdoors to mediator |
| Mediation | Sequential-ignorability diagnostics; sensitivity to M-Y confounding |

Diagnostics that return "concerning" or "fail" should be reported alongside the headline estimate, not filed away. Honest diagnostics build credibility; hidden ones destroy it when discovered.
