# Study Design

The work that comes before modeling. Design is where most bad observational studies go wrong — not in the regression, but in the setup that happens before anyone writes a line of code. This file covers the disciplined way to specify the question, the estimand, and the shape of the data, so the eventual analysis has something credible to estimate.

## Contents

1. [Target trial emulation](#target-trial-emulation)
2. [Choosing the estimand](#choosing-the-estimand)
3. [Time zero and eligibility](#time-zero-and-eligibility)
4. [Treatment strategies and versions](#treatment-strategies-and-versions)
5. [Follow-up, censoring, attrition](#follow-up-censoring-attrition)
6. [SUTVA and interference](#sutva-and-interference)
7. [Power and precision](#power-and-precision)
8. [The design checklist](#the-design-checklist)

---

## Target trial emulation

The single most important design framework for observational causal inference (Hernán & Robins 2016). Every observational study is implicitly trying to estimate the effect that some randomized trial *would* have shown if it had been run. Target trial emulation makes that implicit trial explicit — which exposes design flaws before they contaminate the estimate.

### The protocol

Before touching data, write down what the ideal randomized trial would look like:

| Protocol element | Ideal trial | Observational emulation |
|---|---|---|
| Eligibility | Who can be randomized | Who meets the same criteria in the data |
| Treatment strategies | What interventions are compared | What observed behaviors map to those strategies |
| Assignment procedure | Random; blinded where possible | How to mimic "as-if random" via adjustment / design |
| Follow-up period | When observation starts and ends | Align both arms on the same clock |
| Outcome | Measured the same way in both arms | Confirm the same measurement in observed data |
| Causal contrast | ATE, ATT, per-protocol, intention-to-treat | Which contrast the data support |
| Analysis plan | Pre-specified | Pre-specify for the observational emulation too |

The observational analysis is then *the statistical approximation of the target trial given the data you have.* Deviations from the target trial are the sources of bias — which is now identifiable and discussable rather than hidden.

### Why this matters (the two biases it prevents)

**Immortal time bias.** If the target trial would randomize at time T, but in your observational data you define "treated" by any post-T behavior (e.g., "ever prescribed drug X in the follow-up window"), a treated person must have survived long enough to receive treatment. Controls get no such guarantee. The resulting survival advantage for the "treated" group is a measurement artifact, not a treatment effect.

**Fix:** define treatment and outcome measurement windows as the target trial would, with the same time-zero for all units.

**Prevalent-user bias.** If the trial enrolls people starting treatment, your observational sample must match that — not include long-term existing users whose outcomes reflect years of prior treatment. Prevalent users are survivors of whatever early adverse effects the treatment has; naively including them understates harm.

**Fix:** restrict to new users (the "new-user design"), matching the incident-cohort structure the target trial would impose.

### Applying it

```
Target trial I would run:
  Eligibility: employed 30–55, no prior training in the last 12 months
  Randomize at: hiring date
  Treatments compared: 40-hour onboarding vs 8-hour onboarding
  Follow-up: 180 days
  Outcome: voluntary attrition
  Contrast: ATE, intention-to-treat

Observational emulation using HR warehouse:
  Eligibility filter: same criteria in headcount table
  Time zero: hire_date
  Treated arm: onboarding_hours >= 40 within first 14 days
  Control arm: onboarding_hours <= 8 within first 14 days
  (Exclude 8 < hours < 40 — they represent neither strategy cleanly)
  Follow-up window: hire_date to hire_date + 180d, or separation date, whichever first
  Outcome: indicator for voluntary separation in that window
  Adjustment set: role, department, manager tenure, team size, region
  Missing adjustment (would be solved by randomization): manager's private assessment of candidate
```

Now every flaw is visible: the 14-day window to measure treatment is a design choice, not data-driven; the exclusion of the 8–40 range defines the estimand; the missing adjustment is an unobserved confounder we need to discuss. This is good — hidden choices become explicit.

### When you cannot emulate a target trial

Some observational questions map badly to any realistic trial. If no ethical or physical trial could answer the question as posed (e.g., "what is the effect of height on income?"), causal language is probably inappropriate. Sharpen the question until it maps to an intervention a regulator or manager could actually implement.

---

## Choosing the estimand

The estimand is the causal quantity you are trying to estimate. Choosing it badly is one of the most common mistakes in applied work — the analysis is technically correct but answers a question nobody asked.

### The main options

| Estimand | What it means | When it fits the decision |
|---|---|---|
| **ATE** (average treatment effect) | Effect averaged over the whole eligible population | Universal-rollout decisions; policy for everyone |
| **ATT** (average treatment effect on the treated) | Effect among those who actually got treatment | "Should we continue the program?" — concerns the people in it |
| **ATC** (ATE on controls / untreated) | Effect if we extended treatment to currently-untreated | Expansion decisions |
| **LATE** (local ATE) | Effect on compliers — those whose treatment is moved by the instrument | Best available when using IV; rarely what the decision-maker actually wants |
| **CATE** (conditional ATE) | Effect as a function of covariates | Targeting: who benefits most? |
| **ATE on the overlap region** | ATE for units with good covariate support | Honest default when overlap is limited |
| **Per-protocol effect** | Effect if everyone complied with their assigned treatment | Efficacy-style questions |
| **Intention-to-treat effect** | Effect of being assigned to treatment, regardless of compliance | Real-world rollout effectiveness |

### Mistakes to avoid

**Estimand drift.** An analyst decides to use IV because treatment is endogenous. They report the IV estimate as "the effect." But IV gives LATE, not ATE — the effect for compliers only. If compliers are a small or unrepresentative subset, this number does not support a universal-rollout decision.

**ATT reported as ATE.** A matched analysis gives the ATT (effect on those who got treated). The analyst calls it "the effect of the program" and a decision-maker reads it as "what would happen if we extended the program." The numbers can differ substantially when effects are heterogeneous.

**Ignoring overlap.** If the estimand is the full-population ATE but overlap is poor, the estimator extrapolates. Reporting the number without restricting to the overlap region passes extrapolated noise off as a causal estimate.

### Writing the estimand explicitly

Add it to the report header so there is no ambiguity:

> *"We estimate the ATT — the effect of the feature launch on 30-day retention among users who adopted the feature. This is the relevant quantity for the decision to continue supporting the feature for current adopters. It is **not** the effect that would be observed if we rolled the feature to all users (that would be the ATE or ATC, which we cannot credibly estimate from these data due to limited overlap in the pre-adoption covariate space)."*

---

## Time zero and eligibility

**Time zero (t₀)** is the moment at which eligibility is assessed, treatment is assigned, and follow-up begins. In a randomized trial it is unambiguous (the day of randomization). In observational data it is a design choice — and one that must be made carefully.

### Rules

1. **Covariates used for adjustment must be measured at or before t₀.** A post-treatment variable in the adjustment set is a timing leak. It will bias the effect — sometimes dramatically, sometimes silently.

2. **Outcomes must be measured strictly after t₀.** An outcome that was already known at t₀ is not an outcome; it is a selection variable.

3. **Eligibility must be assessable at t₀.** "Eligible" means "eligible based on what we knew then" — not "eligible based on what we later learned."

4. **Every unit must have a well-defined t₀.** If half your sample has no natural t₀, you probably need to restructure the data or change the question.

### Common t₀ choices by setting

| Setting | Natural t₀ |
|---|---|
| Clinical trial emulation | Day of "would-have-been" randomization (often first eligibility) |
| Marketing / feature experiment | Day of feature launch (for adopters) or first eligibility (for everyone) |
| Policy evaluation | Day of policy implementation |
| HR / workforce | Hire date, promotion date, or role start date |
| Education | Enrollment date |

### Example of a timing leak

You want to estimate the effect of a training program on promotion within 2 years.

**Bad:** adjust for "number of courses completed in the 2 years after program start." This is a post-treatment variable and is directly affected by treatment. Including it will underestimate the effect (it controls away the mechanism).

**Good:** adjust only for pre-treatment education, tenure, past performance reviews measured before t₀. If you want to understand the role of courses in the effect, do a formal mediation analysis — don't just stuff the mediator into the regression.

---

## Treatment strategies and versions

The target trial compares **well-defined strategies**, not vague labels. "Treated vs not treated" is a label. "40+ hours of onboarding within the first 14 days vs ≤ 8 hours" is a strategy.

### Treatment versions

If "treated" can mean many different things (different doses, different schedules, different combinations), the effect estimate is an average over whatever mix of versions appears in the data. That average is rarely interpretable.

**Consistency** requires that observed outcome under observed treatment equals the potential outcome under that treatment version. If there are multiple versions and you are treating them as one, consistency is violated.

**Solutions:**
- Define a single version as your treatment strategy
- Estimate separate effects per version
- Explicitly estimate a "policy" effect that averages over versions, weighted by their observed frequency

Write which choice you made. "We define treatment as strategy X; units receiving strategy Y are excluded from both arms" is a legitimate design decision. "We analyzed anyone who was ever treated" without specifying the version is an invitation to bias.

---

## Follow-up, censoring, attrition

### Follow-up window

Choose a window long enough for the outcome to materialize but short enough that most units are observed through it. Mismatched windows across arms are immortal time bias in disguise.

### Censoring

Units dropping out before the end of follow-up are censored. Key questions:

- **Is censoring random (with respect to treatment and outcome)?** If yes, a complete-case analysis is unbiased. If no, censoring is informative and must be modeled.
- **If informative:** use inverse probability of censoring weights (IPCW) or a joint model for outcome and censoring.

Censoring that is differential by treatment arm (treated units drop out for different reasons than controls) is one of the most common sources of bias in observational studies.

### Attrition

Similar to censoring but in panel data: units disappearing from the panel after treatment. Compare attrition rates and attrition reasons by arm. If attrition is both differential and informative, IPW on staying in the panel (analogous to IPCW) is one fix.

---

## SUTVA and interference

**SUTVA (Stable Unit Treatment Value Assumption)** has two parts:

1. **No interference.** One unit's treatment does not affect another unit's outcome.
2. **No hidden variation in treatment.** The treatment received is the same for every unit "assigned" to it.

### When SUTVA is plausible

- Clinical trials with isolated patients
- Individual-level interventions with no network effects
- Product experiments where users do not influence each other

### When SUTVA is violated

- **Network spillovers:** a user's behavior depends on their friends' behavior. Classic example: recommendation algorithm rolled out to 50% of users — unexposed users still see content from exposed ones.
- **Market-level effects:** launching a pricing change to some customers affects market equilibrium for others.
- **General equilibrium:** a training program for 5% of workers does not have the same effect as training 80% — wage effects, competition effects, etc.
- **Peer effects:** classroom, workplace, household-level interventions with within-group spillovers.

### What to do when SUTVA is violated

- **Change the unit of analysis** to one where SUTVA is plausible (classroom instead of student; market instead of user).
- **Cluster-randomize** (or cluster-assign in emulation) so treatment varies at the natural interference boundary.
- **Model the network** explicitly — peer-effects models, partial interference frameworks (Hudgens & Halloran 2008).
- **Bound the effect** — if full accounting is impossible, at least quantify how spillovers could affect the estimate.

Minimum: state whether SUTVA is plausible and in which direction spillovers would bias the estimate if present.

---

## Power and precision

Causal inference is not immune to the standard power problem: a true effect too small to detect is indistinguishable from no effect.

### Rough targets

- For an ATE in a well-powered backdoor analysis: n per arm to detect a standardized effect of 0.2 at 80% power is roughly 400. Smaller effects need more — 0.1 needs roughly 1,600 per arm.
- For IV: effective sample size is roughly `n × (first-stage R²)`. A weak instrument with first-stage R² = 0.05 on n = 10,000 gives an effective 500 — often too little.
- For DiD: power depends on the pre-period length and the within-unit correlation structure. Longer pre-periods and more units help disproportionately.
- For RDD: power is local to the cutoff, so total n is misleading. What matters is observations within the chosen bandwidth.

### When to pause

- If a rough calculation says the design is underpowered to detect plausible effect sizes, report this as a limitation. An underpowered estimate that fails to reject zero is weak evidence of no effect.
- An overpowered design (huge n) will declare statistical significance on practically negligible effects. Lead with practical magnitude, not significance.

### Precision gains from design

- Pre-registration reduces "research-degrees-of-freedom" inflation of effective sample size.
- Baseline covariate adjustment in randomized designs improves precision without bias.
- Matched designs can gain precision in observational work, at the cost of restricting the estimand to matched units.

---

## The design checklist

Before writing any code, answer:

1. **What decision does this analysis inform?** If no decision, question whether causal inference is the right framework.
2. **What is the target trial?** Specify eligibility, treatments, assignment, follow-up, outcome, estimand, analysis plan.
3. **What is t₀?** A single, unambiguous moment per unit.
4. **Are all adjustment variables measured at or before t₀?** If not, fix before proceeding.
5. **What is the outcome measurement window?** Same for every unit.
6. **Is SUTVA plausible?** If not, redesign or bound the effect.
7. **Which estimand fits the decision?** ATE, ATT, LATE, CATE, per-protocol, ITT. Not all the same.
8. **Is the design powered for plausible effect sizes?** If not, the report must lead with this.
9. **What is the analysis plan?** Written down before estimation, not after.
10. **Who is the domain expert who will pressure-test assumptions?** Book time with them now, not after the analysis is done.

Every one of these is cheaper to fix at the design stage than to patch with sophisticated modeling later. The payoff for spending an hour on design is routinely a week saved downstream.
