# Gotchas and Diagnostics

When intuition disagrees with the estimate, the estimate is usually right — about the wrong quantity. Work through this before re-running the model.

## Symptom → likely cause → fix

| Symptom | Likely cause | Fix |
|---|---|---|
| Effect flips sign or changes magnitude under minor spec change | Residual confounding, misspecification, or thin support | Inspect overlap; add flexible terms (splines, interactions); check for colliders in the adjustment set |
| Huge standard error on the treatment effect | Weak effective treatment variation after adjustment; poor overlap | Restrict to the overlap region; redefine estimand (ATT instead of ATE); reconsider identification |
| DoWhy says "not identifiable" | Adjustment set insufficient given the DAG | Add observed confounders; reconsider the DAG; switch design (IV / DiD / RDD) |
| Balance still bad after IPW | Propensity model misspecified or positivity violation | Re-specify propensity with flexible learner; trim extreme scores; move to the overlap population |
| DiD placebo shows an effect in the pre-period | Parallel trends is implausible | Reconsider design; enrich controls; use synthetic control; stop |
| RDD shows bunching in the density at the cutoff | Manipulation of the running variable | RDD invalid at this cutoff; look for a different threshold or design |
| IV first-stage F < 10 | Weak instrument | Use weak-IV-robust inference (Anderson-Rubin); find a stronger instrument; or stop |
| CATEs are unstable, flip signs, or give implausible values | Sparse support in subgroups; overfitting | Coarsen subgroups; reduce feature set; increase `min_samples_leaf`; demand ATE-first |
| ATT differs wildly from ATE | Treatment effect heterogeneity + different populations | This is fine if you report the right estimand — just do not conflate them |
| Post-treatment variable accidentally in adjustment set | Timing leakage | Re-partition covariates by whether they are measured **before** the treatment assignment, exclusively |

---

## Common conceptual errors

### "I controlled for X" does not mean "X is accounted for"

Controlling for a linear X leaves residual confounding if the X–Y relationship is nonlinear, if X interacts with T, or if you observe a proxy of X rather than X itself. Use flexible functional forms (splines, trees, GPs) for the confounder model.

### Adjusting for a mediator

If M is on the causal path T → M → Y, including M in a regression of Y on T estimates a **controlled direct effect**, not the total effect. If that is what you want, state it. Otherwise, exclude M.

### Adjusting for a collider

If C is caused by both T and Y (or by variables related to both), conditioning on C induces a non-causal association. Classic example: selection bias from conditioning on a post-treatment outcome.

### Pre-trend test ≠ parallel trends

Passing a pre-trend test is consistent with parallel trends but does not prove them. Unobserved factors could cause trends to diverge only after treatment. Report the test, do not lean on it.

### LATE is not ATE

IV estimates the effect among **compliers** (units whose treatment status is moved by the instrument). This population can be small, atypical, or both. Do not publish LATE as "the causal effect."

### A strong first stage does not rescue a bad exclusion restriction

Validity of an IV rests on the exclusion restriction — that the instrument affects Y only through T. This is an assumption about the world, not a statistic. A first-stage F of 10,000 is compatible with a totally invalid IV.

### Two-way fixed effects in staggered rollout

With heterogeneous treatment effects and staggered onset, TWFE can give negatively weighted comparisons and even flip the sign of the true average effect (Goodman-Bacon 2021). Use a robust estimator — Callaway–Sant'Anna, Sun–Abraham, de Chaisemartin–D'Haultfœuille, Borusyak–Jaravel–Spiess.

### High VIF is not a reason to drop a true confounder

Multicollinearity inflates standard errors but does not bias coefficients. Removing a necessary confounder to reduce VIF biases the effect. The fix is more data or a redesigned estimand, not a smaller model.

### Post-LASSO OLS is not a valid generic causal strategy

LASSO selects for prediction, which does not guarantee selection of confounders. Use double-selection or debiased ML (Belloni-Chernozhukov-Hansen, DoubleML) rather than naive post-LASSO.

### Regression adjustment fails with time-varying confounders affected by prior treatment

In longitudinal data where confounders evolve and prior treatment affects them, conditioning on those confounders blocks part of the treatment effect. Use g-methods (IPTW with MSMs, g-computation, g-estimation) instead.

---

## Diagnostic procedures

For detailed procedures and code (overlap, balance, functional form, first-stage strength, pre-trends, density tests, covariate continuity, autocorrelation, influence, clustering, nuisance-model quality, and the diagnostic checklist by design) see `diagnostics.md`.

This file focuses on **what to do when a diagnostic fails or an estimate looks wrong** — the symptom → cause → fix mapping above, plus the conceptual errors below. Use the two files together: `diagnostics.md` tells you what "failing" looks like; this file tells you what failing usually *means*.

---

## Product / HR / analytics-specific traps

- **A predictor is not a lever.** A correlate of churn in your random forest is not necessarily something you can intervene on to reduce churn.
- **Survey constructs** (job satisfaction, NPS, engagement) are often mediators, proxies, or downstream signals. Treating them as treatments requires care.
- **"Lift from this campaign"** from a non-randomized rollout is attribution, not causation, unless you have a genuine design (holdout, geo-experiment, synthetic control).
- **Lagged features in a retention model** mix time-varying confounding with treatment. Regression adjustment can block part of the causal effect. Use g-methods.
- **Repeated A/B tests that always "win"** usually indicate selection bias (peeking, early stopping, metric shopping), not a world where everything works.
- **Dashboards that rank "top drivers"** almost always show correlates. Do not let them masquerade as intervention targets.

---

## When to stop and redesign

If three or more of these are true, the analysis is likely unsalvageable with the current data:

1. Identification strategy rests on assumptions the domain expert refuses to endorse
2. Overlap is poor across more than a few covariates
3. Pre-trends / first stage / continuity / balance diagnostics all fail
4. Alternative reasonable specifications give qualitatively different answers
5. Refutation checks flag the estimate

Redesigning beats patching. Options: run a real experiment; find a natural experiment; collect the missing covariate; change the estimand to one the data supports.
