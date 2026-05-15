# Design Playbook

Per-design concepts: when to use, required assumptions, what can go wrong, diagnostics to run, and which refutations matter. This file does **not** contain code — see `code-recipes.md` for estimation code and `refutation-and-sensitivity.md` for refutation code. Use this file to decide *what* to do; use those files for *how*.

## Contents

1. [Backdoor adjustment (regression / matching / IPW / AIPW)](#backdoor-adjustment-regression--matching--ipw--aipw)
2. [Doubly robust / Double ML](#doubly-robust--double-ml)
3. [Instrumental variables (IV)](#instrumental-variables-iv)
4. [Difference-in-differences (classical)](#difference-in-differences-classical)
5. [Staggered DiD](#staggered-did)
6. [Synthetic control](#synthetic-control)
7. [Regression discontinuity (RDD)](#regression-discontinuity-rdd)
8. [Regression kink design](#regression-kink-design)
9. [Interrupted time series (ITS)](#interrupted-time-series-its)
10. [Front-door adjustment](#front-door-adjustment)
11. [Mediation analysis](#mediation-analysis)
12. [g-methods / MSM (longitudinal)](#g-methods--msm-longitudinal)

---

## Backdoor adjustment (regression / matching / IPW / AIPW)

**Use when:** treatment is observational, all confounders are plausibly observed, and the DAG supports an admissible adjustment set.

**Assumptions:**

- Conditional exchangeability: no unmeasured confounding given the adjustment set
- Positivity: every covariate stratum has both treated and untreated units
- Consistency: observed outcome under observed treatment equals the potential outcome under that treatment version
- SUTVA / no interference

**Diagnostics:** propensity-score overlap; covariate balance after weighting/matching (standardized mean differences < 0.1); residual / partial-dependence checks for functional form; sensitivity to unobserved confounders (E-value, Rosenbaum bounds, or DoWhy tipping-point).

**Pitfalls:**

- Adjusting for a mediator (blocks part of the effect) or a collider (induces bias)
- Dropping a true confounder because VIF is high — multicollinearity inflates standard errors but does not bias coefficients
- Rigid linear adjustment when the confounder–outcome relationship is nonlinear → residual confounding

**Refutation:** alternative admissible adjustment sets; placebo outcome; negative control exposure; trim to overlap region; unobserved-confounding sensitivity. See `refutation-and-sensitivity.md`.

---

## Doubly robust / Double ML

**Use when:** many covariates / interactions / proxies, conditional ignorability is plausible, and you want to avoid parametric misspecification.

**Assumptions:** same identification assumptions as backdoor, plus orthogonality (satisfied by the DML construction). Nuisance models must achieve a rate greater than n^{1/4} for asymptotic normality; in practice use cross-fitting and flexible learners.

**Diagnostics:**

- Quality of nuisance fits (out-of-fold R² for outcome; AUC for propensity)
- Propensity-score overlap — extreme scores near 0/1 are a positivity problem
- Stability across learners (gradient boosting vs random forest vs regularized regression)

**Pitfalls:**

- Extreme propensities blow up weights — clip or trim
- Using DML on small samples (n < a few hundred) can be worse than OLS — cross-fitting eats degrees of freedom
- Treating DML as a fix for a bad DAG — it still requires conditional ignorability

**Refutation:** swap nuisance learners and confirm stability; compare to a simple OLS baseline; inspect propensity trimming impact.

---

## Instrumental variables (IV)

**Use when:** treatment is endogenous (unmeasured confounders exist) but an instrument affects treatment and has no direct path to the outcome.

**Assumptions:**

- **Relevance**: instrument predicts treatment (partial F; modern guidance: use weak-IV-robust inference regardless)
- **Exclusion**: instrument affects outcome only through treatment — untestable, must be defended on substantive grounds
- **Independence**: instrument is as-good-as-randomly assigned with respect to potential outcomes
- **Monotonicity** (for LATE interpretation): no "defiers"

**Diagnostics:** first-stage F (effective F if heteroskedastic/clustered); reduced form (outcome on instrument directly — should agree in sign with 2SLS); overidentification test (Hansen J) if multiple instruments — passing does not prove validity.

**Pitfalls:**

- Strong first stage does NOT rescue a bad exclusion restriction. This is the most common IV mistake.
- Weak instrument → 2SLS biased toward OLS, with misleadingly tight CIs
- LATE is the effect for *compliers*, not the ATE, not the ATT. In heterogeneous settings these differ substantially.
- "Judge fixed effects" / leave-one-out designs are still IV and still need all three assumptions.

**Refutation:** Anderson-Rubin weak-IV-robust CI (valid regardless of strength); placebo outcome that should not respond to the instrument; written defense of exclusion with domain experts.

---

## Difference-in-differences (classical)

**Use when:** a treatment turns on at a known time for a subset of units, with pre- and post-period observations for treated and untreated units.

**Assumptions:**

- **Parallel trends**: absent treatment, average outcomes in treated and untreated groups would have evolved in parallel
- No anticipation: treated units did not change behavior before treatment onset
- Stable composition (or adjust for compositional shifts)
- SUTVA

**Diagnostics:** event-study plot with leads and lags (pre-period coefficients should be near zero, statistically and visually); pre-trend regression — *passing is necessary, not sufficient*.

**Pitfalls:**

- Two-way fixed effects with staggered timing produces negatively weighted comparisons that can flip the sign (Goodman-Bacon 2021). See Staggered DiD below.
- Clustering at the wrong level — cluster at the level of treatment assignment
- Treating the pre-trend test as *proof* of parallel trends
- Compositional changes in who is observed over time

**Refutation:** placebo treatment date in the pre-period; placebo "treated" units; alternative control group; conditional parallel trends adjusting for covariates that could shift the trend.

---

## Staggered DiD

**Use when:** treatment onset varies across units.

**Do not use plain TWFE** as the main specification. Use one of:

- **Callaway & Sant'Anna (2021)** — cohort-by-time ATT(g, t), then aggregate. Python: `differences` package.
- **Sun & Abraham (2021)** — interaction-weighted event study.
- **de Chaisemartin & D'Haultfœuille (2020, 2024)** — DIDₘ estimator.
- **Borusyak, Jaravel & Spiess (2024)** — imputation estimator.

**Diagnostics:** cohort-specific pre-trends; Goodman-Bacon decomposition of any TWFE baseline to expose which comparisons dominate; check for negative weights.

**Pitfalls:**

- Never-treated vs not-yet-treated control choice matters; report both
- Continuous treatments in staggered DiD need additional care (de Chaisemartin & D'Haultfœuille 2024)
- Few cohorts (< 5) produce noisy cohort-specific estimates

**Refutation:** compare point estimates across robust estimators — large divergence from TWFE indicates heterogeneous effects over time; event-study plots per cohort.

---

## Synthetic control

**Use when:** one or a few treated aggregate units (state, country, brand), a donor pool of plausibly similar untreated units, and a long pre-period.

**Assumptions:**

- Donor pool can approximate the counterfactual untreated path for the treated unit
- No spillovers from treated to donor
- Treated unit lies within (or near) the convex hull of donors in the pre-period

**Diagnostics:**

- Pre-period RMSPE small relative to the post-treatment gap
- Donor-weight concentration (a few donors dominating is fragile)
- Convex-hull check (is the treated unit extrapolated?)

**Pitfalls:**

- Overfitting the pre-period with a loose donor pool
- Interpreting permutation p-values as exact — they are design-based
- Spillover contamination (donors respond to the policy in the treated unit)

**Refutation:** placebo unit permutation (run SC pretending each donor is treated; compare post/pre MSPE ratios); leave-one-donor-out sensitivity; augmented SC / synthetic DiD as alternative estimators.

**Python tooling.** `pysyncon` (standard and augmented SC), `causalimpact` (Bayesian structural time series — a different but related approach).

---

## Regression discontinuity (RDD)

**Use when:** treatment is assigned based on whether a continuous running variable crosses a cutoff.

**Assumptions:**

- No manipulation of the running variable near the cutoff
- Continuity of potential outcomes at the cutoff (the identifying assumption)
- Local randomization (sharp RDD) or local IV structure (fuzzy RDD)

**Diagnostics:** McCrary / Cattaneo-Jansson-Ma density test for manipulation; covariate balance at the cutoff (covariates should be continuous across it); visual RDD plot with binned means; bandwidth selection (Calonico-Cattaneo-Titiunik MSE-optimal).

**Pitfalls:**

- High-order polynomials give noisy, biased estimates near the cutoff (Gelman & Imbens 2019) — prefer local linear
- Interpreting the estimate as global — RDD identifies a *local* effect at the cutoff
- Fuzzy RDD treated as sharp — use 2SLS with the cutoff as instrument

**Refutation:** bandwidth sensitivity (0.5×, 1×, 2× of the MSE-optimal); polynomial order sensitivity; placebo cutoffs away from the true threshold; covariate-continuity checks.

**Python tooling.** `rdrobust` (Python port of the Stata package — the standard implementation); `rddensity` for the manipulation test.

---

## Regression kink design

**Use when:** treatment *intensity* (not binary assignment) changes slope at a known threshold. You look for a change in the *slope* of the outcome, not a level jump.

**Assumptions:** no manipulation at the kink point; smooth density of the running variable; the relationship between running variable and outcome is smooth everywhere except at the kink.

**Pitfalls:** same as RDD, plus a pre-existing kink in the outcome coinciding with the kink point; small kink angle makes the design underpowered.

**Refutation:** bandwidth sensitivity; covariate balance; placebo kink points; polynomial order sensitivity.

**RDD vs regression kink.** RDD detects a *level jump* (treatment switches 0 → 1). Regression kink detects a *slope change* (treatment intensity changes continuously). Example: a benefit phasing out linearly above an income threshold — the kink is where the phase-out begins.

---

## Interrupted time series (ITS)

**Use when:** a single time series with a clean intervention date and adequate pre- and post-period data. Weaker than DiD — there is no control group, so the counterfactual is extrapolation.

**Assumptions:** no coincident confounding shock at the intervention date; the pre-period trend model extrapolates credibly; autocorrelation is handled.

**Diagnostics:** residual autocorrelation (Durbin-Watson, ACF/PACF); alternative trend specifications (linear, quadratic, spline); segmented regression with both level and slope change.

**Pitfalls:**

- Small n, many parameters
- Other events coinciding with the intervention (there is no statistical test for this — requires domain knowledge)
- Seasonality not modeled → spurious effects

**Refutation:** placebo intervention date; parallel untreated series (converting to controlled ITS / comparative ITS); Bayesian structural time series (`causalimpact`) as alternative estimator; explicit domain check for confounding events.

---

## Front-door adjustment

**Use when:** there is unmeasured confounding between treatment and outcome, but a mediator fully intercepts the effect and has no unblocked backdoor from the treatment.

**Assumptions:**

- The mediator captures the full effect of treatment on outcome (no unmediated path)
- No unblocked backdoor from treatment to mediator
- No unblocked backdoor from mediator to outcome conditional on treatment

**Pitfalls:** very strong structural assumptions — rarely truly applicable; partial mediation invalidates the identification.

---

## Mediation analysis

**Use when:** you want to decompose a total effect into parts working through a mediator vs not.

**Assumptions (sequential ignorability):** no unmeasured treatment-outcome, treatment-mediator, or mediator-outcome confounders; mediator-outcome confounders are not themselves affected by treatment (a strong condition in longitudinal data).

**Pitfalls:**

- Reporting "% mediated" without uncertainty quantification
- Treating a proxy or biomarker as if it were the causal mediator
- Ignoring interactions between treatment and mediator (natural vs controlled effects differ)

**Refutation:** sensitivity to unmeasured mediator-outcome confounding (Imai-Keele-Yamamoto).

For a full structural decomposition using `pm.do()`, see `structural-models.md`.

---

## g-methods / MSM (longitudinal)

**Use when:** treatment is time-varying, and confounders are time-varying AND themselves affected by prior treatment — the canonical Robins setting.

**Assumptions:**

- Sequential exchangeability at each time point
- Positivity at each time point conditional on history
- Consistency

**Methods:** inverse probability of treatment weighting (IPTW) with marginal structural models; g-computation / parametric g-formula; g-estimation of structural nested models.

**Pitfalls:**

- Ordinary regression adjustment here is **wrong** — it blocks part of the effect when time-varying confounders are affected by prior treatment
- Weight instability without stabilization and trimming
- Positivity violations compound across time

**Python tooling.** Options are limited compared to R: `zepid` (epidemiology-oriented); roll your own with `statsmodels.GEE` and careful weight construction. For heavy longitudinal work, the R ecosystem (`ipw`, `gfoRmula`) remains stronger.
