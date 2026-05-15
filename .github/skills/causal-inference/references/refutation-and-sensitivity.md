# Refutation and Sensitivity Analysis

> Refutation is mandatory for every causal analysis. No exceptions. If you skip this step, the analysis cannot support causal claims.

For the per-design *menu* of which refutations to run, see the tables in `design-playbook.md`. This file has the **code**. For the *concept* of why each design needs refutation, see `design-playbook.md`.

## Contents

1. [Refutation principles](#refutation-principles)
2. [DiD refutation recipes](#did-refutation-recipes)
3. [Synthetic control refutation recipes](#synthetic-control-refutation-recipes)
4. [RDD refutation recipes](#rdd-refutation-recipes)
5. [ITS refutation recipes](#its-refutation-recipes)
6. [IV refutation recipes](#iv-refutation-recipes)
7. [General refutation (DoWhy)](#general-refutation-dowhy)
8. [Sensitivity to unobserved confounding](#sensitivity-to-unobserved-confounding)
9. [Specification curve analysis](#specification-curve-analysis)
10. [Multiverse analysis](#multiverse-analysis)
11. [Partial identification and bounds](#partial-identification-and-bounds)
12. [Pass / fail interpretation](#pass--fail-interpretation)
13. [What to do when refutation fails](#what-to-do-when-refutation-fails)

---

## Refutation principles

Every causal claim rests on assumptions that cannot be directly tested with the available data. Refutation does not test whether the assumptions are *true* — it tests whether your conclusions are *robust* to plausible violations.

**The logic is asymmetric:**

- **Pass** does NOT prove causality. It means you tried to falsify the result and did not succeed. The result remains plausible, not proven.
- **Fail** means the causal claim is suspect. The data are consistent with a world where your assumptions are violated and the apparent effect is spurious.
- A pass gives limited reassurance; a fail gives a strong warning.

**Do not iterate until you get a pass.** Re-running refutation with slightly different parameters until it passes is p-hacking by another name. Run the tests once, with pre-specified parameters, and report honestly.

---

## DiD refutation recipes

### Placebo treatment time

Shift the "treatment" to a point in the pre-treatment period. If parallel trends holds and the real effect is real, the placebo effect should be indistinguishable from zero.

```python
import pandas as pd
import statsmodels.formula.api as smf

df_pre_only = df[df["time"] < treatment_time].copy()
placebo_time = df_pre_only["time"].median()
df_pre_only["post_placebo"] = (df_pre_only["time"] >= placebo_time).astype(int)

placebo = smf.ols(
    "y ~ treated * post_placebo + C(unit) + C(time)",
    data=df_pre_only,
).fit(cov_type="cluster", cov_kwds={"groups": df_pre_only["unit"]})

print(placebo.summary())
# PASS: coefficient on treated:post_placebo is not significantly different from zero
# FAIL: significant placebo effect — parallel trends is likely violated
```

### Parallel trends visualization + event study

Before any modeling, plot pre-treatment outcomes by group. They should track each other closely.

```python
import matplotlib.pyplot as plt

pre = df[df["time"] < treatment_time]

fig, ax = plt.subplots(figsize=(9, 4))
for g, gd in pre.groupby("treated"):
    means = gd.groupby("time")["y"].mean()
    ax.plot(means.index, means.values, marker="o",
            label="Treated" if g == 1 else "Control")
ax.axvline(treatment_time, color="red", linestyle="--", alpha=0.5)
ax.set(xlabel="Time", ylabel="Outcome",
       title="Pre-treatment trends (should be parallel)")
ax.legend()
```

A formal event study is more rigorous — plot coefficients on event-time indicators relative to t = −1:

```python
df["event_time"] = df["time"] - df["treat_time"]
df["et_bin"] = df["event_time"].clip(-5, 5).fillna(-999).astype(int)

evt = smf.ols(
    "y ~ C(et_bin, Treatment(reference=-1)) + C(unit) + C(time)",
    data=df[df["et_bin"] != -999],
).fit(cov_type="cluster", cov_kwds={"groups": df["unit"]})

# Extract pre-period coefficients; CIs should straddle zero
coefs = evt.params.filter(like="et_bin")
ci = evt.conf_int().filter(like="et_bin", axis=0)
```

**PASS:** pre-period CIs straddle zero, visibly close to zero. **FAIL:** drift or significance in the pre-period — parallel trends is not supported.

If trends are not parallel: do not use DiD. Consider synthetic control (tolerates heterogeneous pre-trends), or add unit-specific time trends and re-check.

### Goodman-Bacon decomposition (staggered DiD)

With staggered timing, two-way fixed effects is a weighted average of many 2×2 sub-estimates — some using already-treated units as controls. Negative weights can flip the sign of the true effect.

```python
# Options for Python:
# 1. `bacondecomp` package (port of the Stata routine)
# 2. `differences` package (Callaway-Sant'Anna + includes diagnostic decomposition)
# 3. Manual: enumerate (cohort_i, cohort_j) comparisons and weight by treatment variance

# If using differences:
from differences import ATTgt
att = ATTgt(data=df, cohort_name="treat_time", strata_name=None,
            base_period="universal")
att.fit(formula="y ~ 1")
event_study = att.aggregate("event")
simple = att.aggregate("simple")   # ATT averaging over all (g,t)
```

**PASS:** Callaway-Sant'Anna and TWFE give qualitatively similar answers. **FAIL:** sign flip or large magnitude difference → heterogeneous treatment effects; use the robust estimator as your headline.

---

## Synthetic control refutation recipes

### Leave-one-out donors

Refit removing each donor one at a time. If the post-treatment gap changes dramatically when any single donor is dropped, the result is fragile.

```python
import numpy as np
import pandas as pd

# Assuming you have a function fit_sc(df, treated_unit, donor_list) that returns
# a dict with pre_period_rmse, post_gap (array), effect (scalar).
donors = [u for u in df["unit"].unique() if u != treated_unit]
loo = {}
for drop in donors:
    donors_loo = [u for u in donors if u != drop]
    res = fit_sc(df, treated_unit, donors_loo)
    loo[drop] = res["effect"]

loo_series = pd.Series(loo)
print(loo_series.describe())
# PASS: range of LOO effects is narrow relative to the headline effect
# FAIL: one or two donors drive most of the result
```

### Pre-treatment fit quality

Synthetic control must closely track the treated unit before treatment. Poor pre-fit means the synthetic counterfactual is not valid and the post-treatment gap is not interpretable as a causal effect.

```python
pre_rmspe = np.sqrt(np.mean((treated_pre - synthetic_pre) ** 2))
post_mspe = np.mean((treated_post - synthetic_post) ** 2)
ratio = post_mspe / (pre_rmspe ** 2)   # Abadie et al. test statistic

print(f"Pre-period RMSPE: {pre_rmspe:.4f}")
print(f"Post/pre MSPE ratio: {ratio:.2f}")
# Rule of thumb: pre-RMSPE < ~10% of the post-treatment gap
# A large post/pre ratio under permutation testing is evidence of a real effect
```

### Placebo unit permutation

Pretend each donor is the treated unit and fit synthetic controls for them. The true treated unit should have a larger post-to-pre fit ratio than most placebos.

```python
ratios = {}
for candidate in donors:
    others = [u for u in donors if u != candidate]
    res = fit_sc(df, candidate, others)
    ratios[candidate] = res["post_mspe"] / (res["pre_rmspe"] ** 2)

p_like = (np.array(list(ratios.values())) >= true_ratio).mean()
print(f"Permutation p-value: {p_like:.3f}")
```

**PASS:** the true unit's ratio ranks in the top few percent of the permutation distribution.

---

## RDD refutation recipes

### Bandwidth sensitivity

```python
from rdrobust import rdrobust

# Data-driven optimal bandwidth
main = rdrobust(y=df["y"], x=df["x"], c=cutoff, p=1, bwselect="mserd")
h_opt = main.bws.iloc[0, 0]

# Sensitivity
for h in [0.5 * h_opt, h_opt, 2 * h_opt]:
    r = rdrobust(y=df["y"], x=df["x"], c=cutoff, p=1, h=h)
    print(f"h = {h:.3f}: tau = {float(r.coef.iloc[0,0]):.3f}  se = {float(r.se.iloc[0,0]):.3f}")

# PASS: estimates qualitatively stable across bandwidths
# FAIL: point estimate swings or changes sign
```

### Polynomial order sensitivity

```python
for p in [1, 2, 3]:
    r = rdrobust(y=df["y"], x=df["x"], c=cutoff, p=p, bwselect="mserd")
    print(f"p = {p}: tau = {float(r.coef.iloc[0,0]):.3f}")

# Prefer p = 1 (local linear) as the main spec.
# High-order polynomials are fragile near the cutoff (Gelman & Imbens 2019).
```

### McCrary density test (manipulation at the cutoff)

```python
# rddensity (Python port) — install: pip install rddensity
# from rddensity import rddensity
# out = rddensity(X=df["x"].values, c=cutoff)
# print(out)  # check the p-value for H0: continuous density at cutoff

# PASS: p > 0.10 (no evidence of manipulation)
# FAIL: p < 0.05 (density is discontinuous — agents are manipulating the running variable)
```

If the density test fails, the design is invalid at that cutoff. Do not try to patch it.

### Covariate continuity at the cutoff

```python
# Pre-treatment covariates should be continuous at the cutoff — if they jump,
# the assignment is not as-good-as-random across the cutoff.
for cov in ["age", "income", "prior_outcome"]:
    r = rdrobust(y=df[cov], x=df["x"], c=cutoff, p=1)
    print(f"{cov}: jump = {float(r.coef.iloc[0,0]):.3f} (should be ≈ 0)")
```

### Placebo cutoffs

Run RDD at fake cutoffs away from the true one. You should find no effect.

```python
for placebo_c in [cutoff - 2.0, cutoff - 1.0, cutoff + 1.0, cutoff + 2.0]:
    df_sub = df[(df["x"] > placebo_c - h_opt) & (df["x"] < placebo_c + h_opt)]
    # Drop observations too close to the real cutoff if placebo is near it
    r = rdrobust(y=df_sub["y"], x=df_sub["x"], c=placebo_c, p=1)
    print(f"placebo c = {placebo_c}: tau = {float(r.coef.iloc[0,0]):.3f}")
```

---

## ITS refutation recipes

### Residual autocorrelation

ITS assumes the pre-trend model extrapolates cleanly. Autocorrelated residuals violate this and inflate significance.

```python
import statsmodels.stats.stattools as sms
from statsmodels.graphics.tsaplots import plot_acf
import matplotlib.pyplot as plt

resid = its_model.resid
dw = sms.durbin_watson(resid)
print(f"Durbin-Watson: {dw:.2f}  (≈ 2 is ideal; 1.5–2.5 usually acceptable)")

plot_acf(resid, lags=20)
plt.title("Residual ACF (spikes outside the band indicate autocorrelation)")
```

If autocorrelation is present, add AR terms (`statsmodels.tsa.arima.model.ARIMA` with an intervention regressor) or use a state-space model (e.g., Kalman-filter-based segmented regression).

### Placebo intervention date

```python
placebo_date = treatment_time - pd.Timedelta(days=180)
df_pre = df[df["time"] < treatment_time].copy()
df_pre["post_placebo"] = (df_pre["time"] >= placebo_date).astype(int)
df_pre["t"] = (df_pre["time"] - df_pre["time"].min()).dt.days

placebo = smf.ols(
    "y ~ t + post_placebo + t:post_placebo",
    data=df_pre,
).fit()
print(placebo.summary())
# PASS: post_placebo and t:post_placebo coefficients both near zero
```

### Confounding event search (domain knowledge required)

ITS is especially vulnerable to events coinciding with the treatment. There is no statistical test for this.

> **Ask the user:** "Did anything else change at or near the treatment time — a concurrent policy, market shock, data collection change, or simultaneous intervention on a related variable?"

If yes: (a) add the confounding event as a covariate, (b) collect data on a control unit that experienced the confound but not the treatment (converting ITS to DiD), or (c) downgrade the causal claim.

---

## IV refutation recipes

### First-stage strength

```python
from linearmodels.iv import IV2SLS

iv = IV2SLS.from_formula(
    "y ~ 1 + w1 + w2 + [treatment ~ z1 + z2]",
    data=df,
).fit(cov_type="robust")

print(iv.first_stage)
# Partial F > 10 per endogenous variable is a historical rule of thumb;
# modern practice: use weak-IV-robust inference regardless (Lee et al. 2022)
```

### Anderson-Rubin weak-IV-robust confidence interval

```python
# Valid regardless of first-stage strength. Grid search over candidate values.
import numpy as np
from scipy import stats

def ar_test(beta0, y, x, z, X=None):
    """AR test statistic for H0: beta = beta0 in IV model Y = X*beta + X'gamma + e."""
    u = y - x * beta0
    if X is None:
        num = np.linalg.lstsq(z, u, rcond=None)[1]
    # ... full implementation: regress u on z (and any exogenous controls),
    # form F-stat, convert to p-value under H0.
    # See `linearmodels` or a dedicated package for a tested implementation.
    pass

# In practice, the `ivmodels` package (https://github.com/mlondschien/ivmodels)
# provides `ivmodels.tests.anderson_rubin_test` and weak-IV-robust CIs directly.
```

### Placebo outcome (instrument irrelevance test)

An outcome the instrument should NOT affect. The IV estimate on this outcome should be zero.

```python
iv_placebo = IV2SLS.from_formula(
    "y_placebo ~ 1 + w1 + w2 + [treatment ~ z1 + z2]",
    data=df,
).fit()
# PASS: coefficient near zero
# FAIL: significant effect — suggests the instrument is not excluded from other outcomes,
# weakening the case that it's excluded from the outcome of interest
```

### Exclusion-restriction argument

There is no statistical test for exclusion. Write the argument:

> *"The instrument Z affects Y only through T because [mechanism]. Alternative channels considered and dismissed: [A], [B], [C], with reasoning [...]."*

Send this to a domain expert for red-teaming before publishing.

---

## General refutation (DoWhy)

For any DAG-based analysis. Run all three; they probe complementary failure modes.

```python
import dowhy
from dowhy import CausalModel

model = CausalModel(data=df, treatment="treatment", outcome="y", graph=dag)
identified = model.identify_effect(proceed_when_unidentifiable=False)
estimate = model.estimate_effect(identified,
                                 method_name="backdoor.linear_regression")

# 1. Random common cause — adds a random covariate as unobserved confounder
ref_rcc = model.refute_estimate(identified, estimate,
                                method_name="random_common_cause")
print(ref_rcc)
# PASS: new estimate ≈ original (within sampling noise)

# 2. Placebo treatment — replaces real treatment with a random permutation
ref_placebo = model.refute_estimate(identified, estimate,
                                    method_name="placebo_treatment_refuter")
print(ref_placebo)
# PASS: refuted estimate ≈ 0 (a real effect cannot survive random assignment)

# 3. Data subset — re-estimates on random 80% subsets
ref_subset = model.refute_estimate(identified, estimate,
                                   method_name="data_subset_refuter",
                                   subset_fraction=0.8)
print(ref_subset)
# PASS: estimate stable across subsets
```

---

## Sensitivity to unobserved confounding

The most important sensitivity analysis for observational data. Even if all other refutations pass, an unobserved confounder could explain the result. The question is *how strong* that confounder would need to be.

### Tipping-point analysis (DoWhy)

```python
for strength in [0.05, 0.1, 0.2, 0.3, 0.5, 0.7]:
    ref = model.refute_estimate(
        identified, estimate,
        method_name="add_unobserved_common_cause",
        confounders_effect_on_treatment="binary_flip",
        confounders_effect_on_outcome="linear",
        effect_strength_on_treatment=strength,
        effect_strength_on_outcome=strength,
    )
    print(f"Strength {strength}: refuted estimate = {ref.new_effect:.4f}")
```

Read off the tipping point — the strength at which the effect is pushed to zero. Compare to the observed associations of measured confounders:

> *"The effect is robust to unobserved confounders up to strength ≈ 0.3. The strongest observed confounder has association strength ≈ 0.15, so an unobserved confounder capable of explaining away the result would need to be roughly 2× stronger than anything we have measured."*

### E-value (VanderWeele & Ding 2017)

Closed-form alternative for risk-ratio-style estimates.

```python
def e_value(rr):
    """Minimum joint association (RR scale) an unmeasured confounder must have
    with both treatment and outcome to fully explain away the observed effect."""
    rr = rr if rr >= 1 else 1 / rr
    return rr + (rr * (rr - 1)) ** 0.5

print(e_value(1.8))   # e.g., 2.97 — a confounder would need RR ≈ 3 on both
```

For a continuous outcome, convert the effect to an approximate RR first (see VanderWeele & Ding 2017, Table 2).

### Rosenbaum bounds (for matched designs)

For matched observational studies, Γ is the multiplicative bias a hidden confounder would need to introduce in the odds of treatment to overturn significance. Γ = 1 → no hidden bias assumed; larger Γ → more robust.

```python
# No mature Python port — use rbounds in R or port the algorithm.
# Report Γ at which the p-value crosses 0.05.
```

### Reporting template

> *"The estimated effect of [treatment] on [outcome] is [X] (95% interval: [lo, hi]). Sensitivity analysis shows this estimate is robust to unobserved confounders with effect strengths up to ≈ [tipping point]. Given that the strongest observed confounder ([variable]) has association ≈ [observed], an unobserved confounder capable of explaining away this result would need to be ≈ [ratio]× stronger than anything measured."*

---

## Specification curve analysis

Beyond unobserved confounding: how sensitive is the result to the dozens of defensible specification choices that go into any analysis? Simonsohn, Simmons & Nelson (2020) propose running the analysis across *all* reasonable specifications and presenting the distribution of estimates. A result that holds across most specifications is robust; one that depends on a single favored spec is cherry-picked.

```python
import itertools
import pandas as pd
import statsmodels.formula.api as smf

# Enumerate defensible specification choices
covariate_sets = [
    ["w1", "w2"],
    ["w1", "w2", "w3"],
    ["w1", "w2", "w3", "w4"],
]
functional_forms = ["linear", "quadratic_w1", "interaction_w1_w2"]
se_types = ["HC3", ("cluster", "unit_id")]
sample_filters = ["all", "overlap_only", "exclude_outliers"]

def build_formula(covs, form):
    base = "y ~ treatment + " + " + ".join(covs)
    if form == "quadratic_w1":
        base += " + I(w1**2)"
    elif form == "interaction_w1_w2":
        base += " + w1:w2"
    return base

results = []
for covs, form, se, flt in itertools.product(
    covariate_sets, functional_forms, se_types, sample_filters
):
    d = df
    if flt == "overlap_only":
        d = df[df["in_overlap"]]
    elif flt == "exclude_outliers":
        d = df[df["cooks_d"] < 4 / len(df)]

    formula = build_formula(covs, form)
    if isinstance(se, tuple):
        m = smf.ols(formula, data=d).fit(
            cov_type="cluster", cov_kwds={"groups": d[se[1]]}
        )
    else:
        m = smf.ols(formula, data=d).fit(cov_type=se)

    results.append({
        "covs": "+".join(covs), "form": form, "se": str(se), "filter": flt,
        "beta": m.params["treatment"],
        "ci_lo": m.conf_int().loc["treatment", 0],
        "ci_hi": m.conf_int().loc["treatment", 1],
    })

curve = pd.DataFrame(results).sort_values("beta").reset_index(drop=True)

# Plot: each spec is a dot with CI; color the main spec
import matplotlib.pyplot as plt
fig, ax = plt.subplots(figsize=(10, 4))
ax.errorbar(curve.index, curve["beta"],
            yerr=[curve["beta"] - curve["ci_lo"], curve["ci_hi"] - curve["beta"]],
            fmt=".", alpha=0.5)
ax.axhline(0, color="k", lw=0.5)
ax.set(xlabel="Specification (sorted by estimate)", ylabel="Effect",
       title="Specification curve")

# Summary statistic: share of specs with positive and 95%-significant effects
share_positive     = (curve["beta"] > 0).mean()
share_significant  = (curve["ci_lo"] > 0).mean()
print(f"{share_positive:.0%} of specifications give positive estimates")
print(f"{share_significant:.0%} reject zero at 95%")
```

**Interpretation:**

- If 95%+ of specs give estimates of the same sign and most reject zero, the result is robust to analyst choices
- If the distribution straddles zero, the headline estimate is a choice — report the curve, not the headline
- If only the preferred spec gives a significant effect, that spec needs extraordinary justification

This is expensive to run but worth it for high-stakes decisions. It is also a strong defense against pre-registration skepticism — the curve shows every plausible analysis, not just one.

---

## Multiverse analysis

Multiverse analysis (Steegen et al. 2016) extends the specification curve to data-processing choices — not just modeling choices. Different reasonable operationalizations of key variables become different "universes."

Typical multiverse dimensions:

- **Outcome operationalization**: 30-day retention vs 60-day vs rolling 30-day vs NPS-based composite
- **Treatment operationalization**: "ever adopted" vs "adopted within first 14 days" vs "sustained adoption >= 30 days"
- **Exclusion rules**: drop test accounts / not; drop users who churned pre-period / not; drop duplicates / not
- **Missing-data handling**: complete cases vs mean imputation vs multiple imputation
- **Outlier rules**: no trimming vs 1% vs 5% vs Tukey IQR

The cartesian product of choices is the multiverse. Run every combination and plot the distribution, as above.

Multiverse is most valuable when:
- The outcome is ambiguous (engagement metrics, satisfaction scores)
- There are many plausible exclusion rules
- Missing data is substantial
- The stakes are high enough to justify the compute

Be explicit about which universes correspond to different *causal questions* (not just different estimators of the same thing). A 30-day retention effect and a 60-day retention effect are different estimands — the multiverse averages over scientific questions as well as methodological choices.

---

## Partial identification and bounds

When point identification fails — because an assumption you need (no unmeasured confounding, exclusion restriction, monotonicity) cannot be defended — the fallback is to *bound* the effect rather than pretend it is point-identified.

### Manski bounds (no-assumption bounds)

The widest possible bound. Assumes nothing about the potential-outcome distribution beyond what the observed data reveal.

For a binary outcome in [0, 1] and a binary treatment:

```
Lower bound:  E[Y(1)] - E[Y(0)]  ≥  P(T=1) * E[Y | T=1] + P(T=0) * 0
                                   - [P(T=1) * 1         + P(T=0) * E[Y | T=0]]

Upper bound:  symmetric, assuming the unobserved potential outcomes take the opposite extreme
```

The Manski bound is often very wide — it tells you what the data alone can support. If the Manski bound contains zero (it usually does), no point estimate from the same data is trustworthy without additional assumptions.

```python
def manski_bounds_binary(y, t):
    """Manski bounds for ATE when Y, T are both binary."""
    import numpy as np
    p_t = t.mean()
    e_y_given_t1 = y[t == 1].mean()
    e_y_given_t0 = y[t == 0].mean()
    # Observed part
    observed = p_t * e_y_given_t1 - (1 - p_t) * e_y_given_t0
    # Unobserved potential outcomes are in [0, 1]
    lower = observed + (1 - p_t) * 0 - p_t * 1
    upper = observed + (1 - p_t) * 1 - p_t * 0
    return lower, upper

lo, hi = manski_bounds_binary(df["y"].values, df["treatment"].values)
print(f"Manski bounds on ATE: [{lo:.3f}, {hi:.3f}]")
```

### Lee bounds (monotonicity)

If you are willing to assume *monotonicity* (treatment does not push any unit out of the sample in one direction), Lee (2009) bounds are narrower than Manski bounds. Useful for trial dropout and selection-into-sample problems.

### IV bounds (Balke-Pearl)

With a binary instrument but without exclusion-restriction confidence, Balke-Pearl bounds identify the range of ATE consistent with the data. If the bounds exclude zero, the result is robust to violations of exclusion within the assumed structure.

### Reporting bounds

> *"Under no further assumptions, the ATE lies in [−0.15, +0.42] (Manski bounds). Under the additional assumption that treatment does not decrease adoption among the sample (monotonicity), the bound tightens to [0.02, 0.35] (Lee bounds). Our point estimate of 0.18 requires additionally the assumption of no unmeasured confounding; given the sensitivity analysis above, this assumption is our main limitation."*

This framing is honest and decision-useful. It tells the reader exactly which assumptions are doing the work in narrowing the range.

### When to use bounds

- When a core identification assumption is doubted
- When the audience is hostile or adversarial (bounds are harder to attack than points)
- For highest-stakes decisions (regulatory, legal, policy)
- As a sanity check on a point estimate: if the point estimate is outside the bounds implied by weaker assumptions, something is wrong

Mature Python tooling for bounds is limited. `econml` has some partial-identification support; for Manski / Lee / Balke-Pearl, implementations are typically manual or via R packages.

---

## Pass / fail interpretation

| Result | Meaning | Action |
|---|---|---|
| All pass | Robust to tested failures | Tier-1 causal language permitted |
| Most pass, some marginal | Mildly sensitive | Tier-2 hedged language ("consistent with", "suggestive") |
| Critical test fails | Assumption likely violated | Tier-3: downgrade to associational |
| Multiple failures | Design likely invalid | No causal claim; redesign |

**Critical tests (failure disqualifies):**

- Placebo treatment time shows large non-zero effect (DiD / ITS)
- McCrary density test shows bunching (RDD)
- Pre-treatment RMSPE is comparable to the post-treatment gap (SC)
- DoWhy placebo does not drive effect to zero
- Tipping point for unobserved confounding is implausibly low
- IV placebo outcome shows a meaningful effect

**Marginal tests (warrant caveats, not disqualification):**

- Bandwidth sensitivity shows modest variation within overlapping intervals
- Durbin-Watson indicates mild autocorrelation in ITS residuals
- Leave-one-out SC shows one influential donor
- Data subset refuter shows drift but same sign

---

## What to do when refutation fails

**Rule: do not hide failures.** A buried failure in an appendix is still a failure. Report it prominently.

### Step-by-step response

1. **Identify which assumption failed.** Testable design assumptions (parallel trends, density continuity) are direct evidence of a problem. Untestable structural assumptions (no unmeasured confounding) are risks, not confirmed failures.

2. **Determine if it is fixable.**

| Failure | Possible fix |
|---|---|
| Non-parallel pre-trends | Add unit-specific time trends; switch to synthetic control or matched DiD |
| Bunching at RDD threshold | Abandon this cutoff; consider fuzzy RDD if the threshold drives *probability*, not status |
| Poor SC pre-treatment fit | Expand donor pool; add predictors; use Bayesian structural time series (`causalimpact`) |
| ITS autocorrelation | Add AR terms; move to a full state-space model |
| Low unobserved-confounding tipping point | Collect more covariates; switch to a quasi-experimental design |
| DoWhy placebo non-zero | Re-examine DAG; check for residual confounding or a collider in the adjustment set |
| Weak IV | Use weak-IV-robust inference; find a stronger instrument; or stop making strong claims |

3. **Downgrade the language.** See `reporting-template.md` for the three-tier ladder. Use "associated with" instead of "causes," "suggestive" instead of "demonstrates."

4. **Consider alternative designs.** If observational adjustment fails, is there a quasi-experimental alternative? An instrument, a discontinuity, a comparison group?

5. **Flag the fragile assumption in the report explicitly:**

> *"Warning: the parallel-trends assumption is not supported by pre-treatment data (placebo effect = 2.1, 95% CI [0.8, 3.4]). The DiD estimate below should be interpreted as associational, not causal. We retain the analysis for transparency but recommend collecting additional comparison units before drawing policy conclusions."*

6. **Do not iterate until you get a pass.** Re-running with slightly different parameters until the test passes is p-hacking. Pre-specify, run once, report.
