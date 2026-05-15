---
name: causal-inference
description: Production-grade workflow for causal inference and treatment-effect estimation on observational or quasi-experimental data. Use whenever the user asks whether X causes Y, wants the effect of a policy/feature/treatment/intervention, interprets an A/B test or natural experiment, or talks about counterfactuals, confounders, selection bias, mediators, DAGs, backdoor criterion, propensity scores, overlap, doubly robust estimation, instrumental variables, difference-in-differences, synthetic control, regression discontinuity, interrupted time series, panel fixed effects, event studies, or mediation. Also trigger on "impact of", "effect of", "driver of", "did X work", "attribution", or when evaluating a causal claim from a study or dashboard. Do NOT skip this just because a question sounds predictive — if the user plans to act on the answer, it is causal. Prefers DoWhy for identification/refutation, statsmodels for regression, linearmodels for panel/IV, DoubleML for high-dim adjustment, econml for CATE.
---

# Causal Inference

Estimate the effect of interventions — not just predict outcomes — under explicit, testable-where-possible assumptions.

**Core principle:** do not jump from "X predicts Y" to "X causes Y". Separate study design, identification, estimation, refutation, and interpretation. A clean model on a bad design is still bad causal inference.

## Workflow at a glance

1. **Formulate** the causal question (treatment, outcome, population, time, estimand)
2. **Design** the study (eligibility, timing, follow-up, target-trial emulation if observational)
3. **Draw the DAG** and mark unobserved confounders explicitly
4. **Identify** the estimand (backdoor / IV / DiD / RDD / ITS / front-door / g-methods)
5. **Choose design + estimator** (match tool to identified problem, not to fashion)
6. **Estimate** with an appropriate package
7. **Diagnose** (overlap, functional form, balance, first-stage strength, pre-trends, continuity…)
8. **Refute** with at least one design-specific falsification or sensitivity check
9. **Interpret** in terms of estimand, supported population, decision context
10. **Report** assumption-first, with calibrated language

Steps 1–5 are thinking, not code. Resist the pull to fit something immediately.

---

## Step 1 — Formulate the causal question

Specify all of:

- Treatment / intervention (and which version of it)
- Outcome (and when it is measured)
- Target population and eligibility
- Time zero (when treatment is assigned or initiated)
- Follow-up window
- Estimand: ATE, ATT, ATC, CATE, LATE, dose-response, policy effect
- Effect type: total, direct, mediated, dynamic
- Decision context: what action will this estimate inform?

**Template**

> "What is the effect of [intervention] at [time t0] on [outcome] over [window] in [population], expressed as the [ATE / ATT / CATE / LATE]?"

**Ask the user to confirm** when any of the above is ambiguous in a way that would change the answer. One clarifying question is fine; a barrage is not.

**Red flags to call out immediately:** vague treatment definition; outcome window not defined; post-treatment variables quietly lumped into baseline; the user really wants "drivers" (descriptive) but asks for "causal effect"; no decision attached to the estimate.

---

## Step 2 — Design the study

Before touching identification, pin down the structure:

- Eligibility criteria
- Treatment strategies and their versions
- Assignment timing
- Measurement timing for covariates vs outcome
- Follow-up period and censoring/attrition rules
- Interference assumptions (SUTVA: does one unit's treatment spill over to another?)

For observational data, emulate a **target trial** (Hernán & Robins): describe the hypothetical randomized trial you would run, then explain how the observational dataset approximates it. This single habit prevents most immortal-time and selection biases.

See `references/study-design.md` for target trial emulation protocol, estimand selection (ATE vs ATT vs LATE vs CATE — these are not interchangeable), t₀ specification, censoring handling, SUTVA assessment, and the design checklist to run before any estimation.

---

## Step 3 — Draw the DAG

Build an explicit causal graph with:

- Treatment and outcome
- Pre-treatment confounders
- Post-treatment mediators (mark them; do not adjust for them in a total-effect analysis)
- Colliders / selection variables
- **Unobserved** common causes when they are plausible — drawing them makes identification honesty-checked
- Important non-edges (assumptions of no direct effect)
- Time ordering for evolving variables

**Prefer substantive constructs over raw warehouse columns.** `tenure_days` is often a proxy; the true cause may be `accumulated_skill` or `role_fit`. Model the construct and note which observed variable proxies it.

**DoWhy can formalize the graph, but it does not prove the assumptions.** It only makes them machine-readable.

No estimation until the causal structure is agreed. If the user resists, explain: the DAG is not decoration — it determines which adjustment sets are admissible and whether the estimand is even recoverable.

See `references/dags-and-identification.md` for the four common causal structures (confounder / mediator / collider / instrument), DoWhy setup, the collider-bias warning, and the **user prompt templates for DAG and assumption confirmation** — use those prompts verbatim when you need the user's input on the graph.

---

## Step 4 — Identify

Determine whether the estimand is identified and by what logic.

| Route | Use when | Key assumptions |
|---|---|---|
| Backdoor adjustment | Confounders are all observed | No unmeasured confounding, positivity, consistency |
| Front-door | A mediator intercepts the full effect and has no unblocked backdoor | Strong structural claims |
| Instrumental variables | Unmeasured confounding, but an instrument affects treatment only | Relevance, exclusion, independence, (often) monotonicity |
| Difference-in-differences | Panel or repeated cross-sections with a treatment onset | Parallel trends (counterfactually), no anticipation |
| Regression discontinuity | Assignment is driven by a cutoff on a running variable | No manipulation at cutoff, continuity of potential outcomes |
| Interrupted time series | Single series with a known intervention time | No coincident confounding shock, stable trend model |
| Synthetic control | One or a few treated aggregate units | Donor pool approximates the untreated counterfactual |
| g-methods / MSM | Time-varying confounding affected by prior treatment | Sequential exchangeability, positivity at each time |

**Output this explicitly** before estimation:

```
Identification strategy: <one of the above>
Required assumptions:
  1. ...
  2. ...
  3. ...
Identification status: identified / partially identified / not identified
```

Do not proceed to estimation while status is "not identified" without flagging it loudly.

---

## Step 5 — Choose design + estimator

Match the identified problem to an estimator. See `references/design-playbook.md` for full assumption lists, diagnostics, and refutation menus per design.

| Design | Estimator | Python |
|---|---|---|
| Backdoor, low-dim | OLS / GLM with regression adjustment | `statsmodels` |
| Backdoor, many covariates | Doubly robust / Double ML | `DoubleML` + `sklearn` |
| Backdoor, balance-focused | IPW, AIPW, matching | `statsmodels`, `sklearn`, `DoWhy` |
| IV | 2SLS, LIML, weak-IV-robust CIs | `linearmodels.iv` |
| DiD (two-period) | Two-way FE | `linearmodels.panel`, `statsmodels` |
| DiD (staggered) | Callaway–Sant'Anna, Sun–Abraham, de Chaisemartin–D'Haultfœuille | `differences` package; else roll your own carefully |
| Synthetic control | SC, augmented SC, synthetic DiD | `pysyncon`, `causalimpact` (Bayesian structural) |
| RDD | Local linear / quadratic with bandwidth selection | `rdrobust` (Python port) or `statsmodels` manually |
| ITS | Segmented regression | `statsmodels` |
| Front-door | Two-stage with mediator | `DoWhy`, custom |
| Mediation | Natural direct/indirect effects | `DoWhy`, custom |
| Heterogeneous effects (CATE) | Causal Forest, DR-learner, X-learner | `econml` |
| Longitudinal / dynamic treatment | IPTW-MSM, g-computation | custom; `zepid` for some cases |

**Pick by fit to the problem, not by library popularity.** Double ML is not better than OLS if you have 6 covariates and a clean design; CATE estimators are useless with sparse support.

**When none of these designs fit** — you want a unit-level counterfactual ("what would have happened to *this specific user* had we intervened?"), or you want to decompose mechanisms explicitly via mediation — consult `references/structural-models.md` for the PyMC `pm.do()` / `pm.observe()` path. SCMs are more flexible but carry more assumptions; prefer quasi-experimental designs when available.

---

## Step 6 — Estimate

Only now write estimation code. See `references/code-recipes.md` for ready-to-adapt patterns.

Rules for regression-style adjustment:

- Include only **causally admissible** covariates. A variable that is a collider or a mediator does not belong in the adjustment set just because it improves fit.
- Do not control for post-treatment mediators in a **total-effect** analysis.
- Use flexible functional forms when relationships are nonlinear (splines, polynomials, treatment × covariate interactions). Linearity is an assumption, not a default.
- Separate identification variables (admissible set) from nuisance complexity (ML models inside DML).
- Robust standard errors (or cluster-robust where appropriate); do not report naive SEs for panel or clustered data.

**High-dimensional adjustment:** prefer Double ML with cross-fitting and sensible nuisance learners (gradient-boosted trees, regularized regressions). Report nuisance model performance — if the treatment model has AUC near 0.5 you have an overlap problem, not a good experiment.

---

## Step 7 — Diagnose

Diagnostics are not optional. Always check:

- **Overlap / positivity** — propensity-score densities by treatment group; trim or re-specify the estimand if there is no common support. More important than any collinearity statistic.
- **Balance** (for matching / IPW) — standardized mean differences < 0.1 across covariates
- **Functional-form misspecification** — residual plots, partial-dependence checks, comparison to flexible model
- **Multicollinearity** — high VIF is **not** a reason to drop a true confounder. It is a signal to inspect the data.
- **Design-specific checks** — first-stage F-statistic and weak-IV concerns; pre-trend tests (*not* proof of parallel trends, only a consistency check); McCrary density test near an RDD cutoff; placebo intervention dates for ITS.
- **Timing leakage** — a post-treatment variable quietly in the adjustment set will silently bias the effect.

See `references/diagnostics.md` for full detail on every procedure, code snippets, and a diagnostic checklist by design. See `references/gotchas-and-diagnostics.md` for what failures mean (symptom → cause → fix) and the conceptual errors that most commonly produce them.

---

## Step 8 — Refute

Run at least one **design-specific** refutation before calling anything causal. The minimum menu:

| Design | Minimum refutation |
|---|---|
| Backdoor / regression | Alternative adjustment sets; placebo outcome; unobserved-confounding sensitivity (E-value, Rosenbaum bounds, or DoWhy's `add_unobserved_common_cause`) |
| Propensity / IPW | Balance after weighting; overlap trimming; alternative propensity specification |
| Double ML | Alternate nuisance learners; stability of point estimate across folds |
| IV | Weak-IV-robust CIs (Anderson-Rubin); placebo outcome; discussion of exclusion restriction |
| DiD | Event-study plot with pre-period coefficients; placebo treatment date; placebo untreated units |
| Staggered DiD | Re-estimate with Callaway–Sant'Anna or Sun–Abraham if main spec is TWFE |
| Synthetic control | Placebo unit permutation; pre-period fit (RMSPE); donor-pool sensitivity |
| ITS | Placebo intervention time; check for coincident shocks; alternative trend specification |
| RDD | Bandwidth sensitivity; polynomial order sensitivity; McCrary density test |
| Mediation | Sensitivity to unmeasured mediator-outcome confounding |

**Negative control outcomes** (an outcome the treatment should not affect) and **negative control exposures** (an exposure that should not affect the outcome) are powerful universal falsifiers — use them when available.

If refutation flags a problem, **downgrade the language** in reporting. Never bury failed stress tests.

See `references/refutation-and-sensitivity.md` for detailed code per design, the tipping-point sensitivity procedure, the critical-vs-marginal test classification, and the step-by-step response when refutation fails.

---

## Step 9 — Interpret

Express results in terms of:

- The **estimand** (ATE vs ATT vs LATE — LATE ≠ ATE in almost every realistic IV setting)
- The **supported population** (inside overlap / inside bandwidth / in the donor pool)
- **Decision-relevant units** (percentage points, absolute risk, dollars, DAU — not just β)
- **Uncertainty** as intervals, not stars
- **Practical significance** — a tight zero is a useful result and deserves the same airtime as a positive finding

---

## Step 10 — Report

Use **assumption-first reporting**. Assumptions come before results, not in the appendix. See `references/reporting-template.md` for the full template and language guardrails.

**Language calibration:**

- Strong assumptions hold, diagnostics clean, refutation clean → "estimated causal effect of X on Y was …"
- Assumptions plausible, one or two concerns → "consistent with a causal effect of …"
- Weak design or failed refutation → "association that is not robust to …"; recommend a stronger design before acting

Avoid "proved," "true causal effect," or unhedged "X causes Y" unless the evidence genuinely justifies it.

---

## Critical rules

1. **No estimation without a causal structure.** DAG or DAG-equivalent argument required.
2. **No causal claim without identification logic.** Association + controls is not enough.
3. **No design without timing.** Ambiguity in treatment or outcome timing → pause and clarify.
4. **Overlap beats VIF.** Diagnose common support before worrying about multicollinearity.
5. **Refute before reporting.** At least one design-specific falsification.
6. **Assumptions first, estimate second.** In the report and in the conversation.
7. **Downgrade when warranted.** Fragile results get hedged language.
8. **Ask when domain knowledge is load-bearing.** Instrument validity, parallel trends credibility, and confounder lists come from experts, not code.

---

## Reference files

Load these only when the workflow calls for them. Each file has a single purpose — no overlap.

- `references/study-design.md` — target trial emulation, estimand selection (ATE / ATT / LATE / CATE), t₀ and eligibility, treatment strategies, censoring, SUTVA, power, design checklist. **Load at Steps 1–2.**
- `references/dags-and-identification.md` — DAG concepts, common causal structures, identification criteria (backdoor / frontdoor / IV / design-based), DoWhy setup, collider warning, user prompt templates for DAG confirmation. **Load at Steps 3–4.**
- `references/design-playbook.md` — per-design *concepts* (when to use, assumptions, pitfalls, what to diagnose). No code. Covers backdoor, DML, IV, DiD, staggered DiD, synthetic control, RDD, regression kink, ITS, front-door, mediation, g-methods. **Load at Step 5.**
- `references/code-recipes.md` — all estimation *code*: `statsmodels`, `linearmodels`, `DoubleML`, `econml`, `DoWhy`, `rdrobust`. **Load at Step 6.**
- `references/diagnostics.md` — detailed procedures for Step 7: overlap/positivity, covariate balance, functional-form checks, first-stage strength, pre-trends, density continuity, covariate continuity at cutoffs, residual autocorrelation, influence, clustering, nuisance-model quality, plus a checklist by design. **Load at Step 7.**
- `references/refutation-and-sensitivity.md` — detailed refutation *code* per design; unobserved-confounding sensitivity (tipping-point, E-value); specification curve, multiverse analysis, partial identification / bounds; critical-vs-marginal-test classification; what to do when refutation fails. **Load at Step 8.**
- `references/structural-models.md` — optional: PyMC `pm.do()` / `pm.observe()` for unit-level counterfactuals and explicit mechanism decomposition. **Load only for counterfactual queries about specific units, or mediation via full SCM.**
- `references/gotchas-and-diagnostics.md` — when a diagnostic fails or a result surprises you: symptom → cause → fix table, common conceptual errors (adjusting for mediators / colliders, LATE ≠ ATE, post-LASSO OLS, etc.), product/HR traps, when to stop and redesign. **Load when something breaks.**
- `references/reporting-template.md` — full reporting template, language guardrails (three-tier ladder), interval-width guidance, audience adaptation, common mistakes. **Load at Step 10.**

---

## Environment check

Before estimation, verify the needed libraries are available:

```bash
python - <<'PY'
mods = ["dowhy", "statsmodels", "doubleml", "linearmodels", "econml", "sklearn",
        "pandas", "numpy", "scipy", "matplotlib"]
for m in mods:
    try:
        __import__(m); print(f"OK   {m}")
    except Exception as e:
        print(f"MISS {m}: {type(e).__name__}")
PY
```

Install missing packages with `pip install <pkg>` only if the user confirms; otherwise substitute the closest installed alternative and state the substitution.

---

## Default output structure when asked to "do" causal analysis

1. Causal question (one sentence)
2. Study design (eligibility, timing, follow-up)
3. DAG / causal assumptions (verbal if not rendered)
4. Identification strategy + required assumptions
5. Estimation plan (design, estimator, package)
6. Diagnostics plan
7. Refutation plan
8. Estimate + interval
9. Interpretation in decision units
10. Limits and language calibration

When code is requested, the code should follow this order too: design → identify → estimate → diagnose → refute → interpret.
