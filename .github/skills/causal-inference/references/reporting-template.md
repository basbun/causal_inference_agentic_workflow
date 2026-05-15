# Reporting Causal Analyses

Assumption-first reporting. Assumptions come before the estimate, not in the appendix.

## Contents

1. [Report template](#report-template)
2. [Causal language guardrails](#causal-language-guardrails)
3. [Uncertainty intervals](#uncertainty-intervals)
4. [Audience adaptation](#audience-adaptation)
5. [Common reporting mistakes](#common-reporting-mistakes)

---

## Report template

Every causal analysis produces a report with this structure. Adapt sections as needed, but do not drop sections 1, 7, or 8 — they are non-negotiable.

### 1. Causal question

One sentence: *"What is the effect of [treatment] at [t0] on [outcome] over [window] in [population], as the [ATE / ATT / CATE / LATE]?"*

Write this before touching data. If you cannot write this sentence, you do not yet have a causal question — you have a dataset.

### 2. Study design

- Eligibility
- Treatment strategies compared (and treatment versions)
- Time zero
- Follow-up window
- Censoring / attrition handling
- SUTVA / interference assumptions
- Target-trial emulation (for observational work)

### 3. DAG and assumptions

Include the causal graph (rendered or clearly described in prose) and an **assumption transparency table**:

| Assumption | Testable? | How fragile? | Consequence if violated |
|---|---|---|---|
| No unobserved confounders | No | Often fragile | Estimate biased; direction usually unclear |
| Parallel trends (DiD) | Pre-treatment only | Moderate | Estimate biased; sign could flip |
| No anticipation (DiD) | No | Robust if policy unexpected | Effect diluted pre-treatment |
| SUTVA / no spillovers | No | Fragile if units interact | Estimate conflates direct + spillover |
| Exclusion restriction (IV) | No | Very fragile | IV estimate inconsistent |
| Continuity at cutoff (RDD) | Partially (covariates) | Moderate | Estimate biased |
| Positivity / overlap | Yes | Testable and often violated | Estimator unstable; extrapolation |

Every assumption listed must be discussed, not just listed. For each fragile one, state what evidence — if any — supports it.

### 4. Identification strategy

*"We use [method] to identify the causal effect. This is valid because [justification]."*

Be explicit about: which identification result applies (backdoor / frontdoor / IV / RDD continuity / DiD parallel trends / g-methods), which variables are adjusted for and why. Cross-reference `dags-and-identification.md` for the formal criteria.

If the effect is not point-identified, say so. Partial identification — bounding the effect rather than pinning it down — is a legitimate and honest result.

### 5. Estimation

State the specification: model family, covariates, functional form, standard-error specification (robust / clustered), any structural constraints. Summarize diagnostics (for Bayesian workflows: R-hat, ESS, divergences; for frequentist: residual plots, influence, first-stage F where relevant).

### 6. Results with uncertainty

Never report only a point estimate. Report:

- The point estimate
- At least one interval (see [Uncertainty intervals](#uncertainty-intervals))
- The effect expressed in decision-relevant units (percentage points, dollars, DAU — not just β)
- For directional decisions: the probability (Bayesian) or the rejection result at the chosen level (frequentist) of the effect being on the decision-relevant side of zero

Example:

> *"We estimate the policy increased test scores by 4.2 points (95% CI: [−0.3, 8.9]). The result does not reject zero at the 5% level, though the point estimate and the mass of the interval are positive."*

Or, for a Bayesian workflow:

> *"We estimate the policy increased test scores by 4.2 points (50% HDI: [3.1, 5.3]; 95% HDI: [−0.3, 8.9]). There is an 87% posterior probability the effect is positive."*

### 7. Refutation results

Run all applicable refutation tests (see `refutation-and-sensitivity.md`) and report *every* result — including failures. Do not cherry-pick.

| Test | Result | Interpretation |
|---|---|---|
| Placebo treatment (random assignment) | PASS | Random assignment gives near-zero effect |
| Placebo treatment time | PASS | No effect at a time when none should exist |
| Parallel trends (pre-treatment) | PASS | Pre-treatment trends are parallel |
| Random common cause | PASS | Adding a random confounder does not shift estimate |
| Data subset | PASS | Estimate stable across random subsets |
| Unobserved-confounding tipping point | 0.3 (E-value = 2.1) | A confounder ~2× stronger than any observed would be required |

### 8. Limitations and threats to validity

Mandatory, prominent, not buried. Decision-makers must see this.

Rank threats by severity. For each:

- State the assumption that might be violated
- Explain the direction of bias if violated
- Quantify if possible (tipping point, E-value, Rosenbaum Γ, bounding)
- State what additional data or design would resolve the threat

### 9. Decision relevance / plain-language conclusion

Close every report with one paragraph in plain language, regardless of audience:

> *"We estimate [treatment] causes [outcome] to change by [effect] ([interval]), assuming [key assumptions hold]. There is a [P]% probability / the 95% CI excludes zero for the effect being positive. The main threat to this conclusion is [biggest weakness]. If that assumption is violated, the true effect could be [direction and magnitude of bias]. Given the uncertainty, we recommend [action] if the cost of a false positive is less than [threshold]."*

---

## Causal language guardrails

Language strength must match identification strength. Using causal language without identification is not just imprecise — it is misleading.

| Analysis state | Language tier | Example |
|---|---|---|
| Identification + estimation + all refutations pass | **Causal** | "X causes Y to increase by Z" |
| Identification + estimation pass, some refutations marginal | **Suggestive** | "Evidence suggests X causes Y to increase by Z, though [caveat]" |
| Critical refutation fails | **Associational** | "X is associated with a Z-unit increase in Y, but causal interpretation is limited because [reason]" |
| No identification strategy | **Descriptive** | "We observe X and Y are correlated. We cannot assign a causal interpretation without a credible identification strategy." |

**Default to the more conservative tier when in doubt.** Overclaiming in a causal analysis is a more serious error than underclaiming — it drives bad decisions.

Never use the word "effect" when the state is Descriptive. "Association," "correlation," "relationship" are correct.

### Example tier-3 downgrade

**Overclaim (bad):**
> *"Our analysis shows the feature launch caused a 3.2% increase in retention (p < 0.01)."*

**Tier-3 downgrade (good):**
> *"We estimate an association between the feature launch and a 3.2 pp increase in 30-day retention (95% CI: 1.4–5.0 pp). This estimate relies on the assumption that feature adopters and non-adopters would have had parallel retention trends absent the launch — an assumption undermined by the event-study plot, which shows a 1.8 pp divergence in the six weeks before launch. We recommend treating this as suggestive and running a randomized holdout before further investment."*

The downgrade is more useful because it tells the reader both what we think we see and why they should not act on it yet.

---

## Uncertainty intervals

Do not default to a fixed interval width. Choose widths that map to intuitive probabilities for the decision context.

| Width | Natural frequency | When to use |
|---|---|---|
| 50% | "roughly 1 in 2" | Most likely range; typical effect |
| 75% | "roughly 3 in 4" | Moderate-stakes decisions |
| 89% | "roughly 9 in 10" | Moderate-to-high stakes |
| 95% | "roughly 19 in 20" | High-stakes; safety-critical |

Report multiple widths when the conclusion changes across them — that fact is itself information.

**Bayesian workflows:** report HDIs (highest density intervals); optionally the probability of direction P(effect > 0) or P(effect < threshold). These are often more interpretable than a single fixed HDI.

**Frequentist workflows:** report confidence intervals; be explicit that these are *frequentist* CIs — they do not support posterior-probability statements, and "the 95% CI contains 0" is not the same as "there's a 5% chance the effect is zero."

**Either framework:** always state *why* you chose the reported width. "We report the 75% interval because this decision requires us to act if the effect is positive with 3-in-4 confidence" is better than silently presenting a number.

---

## Audience adaptation

### Technical audience (researchers, analysts)

- Full DAG with node and edge justifications
- Formal identification result (backdoor / frontdoor / IV / RDD / DiD / g-methods) with citations where applicable
- Full diagnostic summary and model specification
- Complete refutation table with test statistics
- Sensitivity analysis (tipping point, E-values, Rosenbaum bounds, or partial-R² bounds)
- Code or link to code repository in the appendix

### Decision-makers (executives, policymakers)

- Causal question in plain language — one sentence
- Effect size translated to natural frequencies: *"For every 100 people exposed, we estimate 8 more would [outcome]"*
- Key threats in 1–2 sentences, plain: *"The main reason this could be wrong is [X]. If so, the true effect is likely [smaller / larger / the opposite direction]."*
- Actionable recommendation with explicit uncertainty: *"Given the uncertainty, we recommend [action] if the cost of a false positive is less than [threshold]."*
- Technical details (DAG, specification, diagnostics, refutation) in a clearly labeled appendix

**Both audiences get the limitations section.** Never hide limitations from decision-makers because they are "too technical." Translate, do not omit.

### Mixed audiences

Open with the plain-language conclusion and effect size. Walk through the DAG visually — most people understand arrows without training. Reserve equations and diagnostic plots for Q&A or written appendices.

---

## Common reporting mistakes

1. **Causal language without identification.** If there is no identification strategy, "effect" is wrong. Use "association."

2. **Reporting only the point estimate.** The uncertainty is the result. Always show at least one interval; ideally multiple widths when the conclusion depends on them.

3. **Hiding refutation failures.** A failed refutation is information. Report it, downgrade the language, explain what the failure means.

4. **Burying limitations.** Threats to validity belong in the body of the report, ranked by severity — not in an appendix labeled "caveats."

5. **Conflating LATE with ATE.** IV gives the Local Average Treatment Effect for compliers only. DiD often gives the ATT (Average Treatment Effect on the Treated). RDD gives a local effect at the cutoff. Be explicit about whose effect you are estimating and whether it answers the question actually asked.

6. **Ignoring spillovers.** If SUTVA is violated and units affect each other, the estimate conflates direct and spillover effects. State whether spillovers are plausible and in which direction they push the estimate.

7. **Omitting sensitivity analysis.** For observational studies, always quantify how strong an unobserved confounder would need to be to overturn the conclusion. This anchors the limitations section in something concrete rather than vague hedging.

8. **Reporting statistical significance as the magnitude.** "Significant at p < 0.01" says nothing about whether the effect matters. Report magnitude in decision units first; inference second.

9. **Forest-of-stars reporting.** Lists of coefficients with asterisks and no narrative are for technical appendices, not for decision-makers. Always lead with the question, the estimand, and the practical magnitude.
