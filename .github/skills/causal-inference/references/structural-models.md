# Structural Causal Models

Optional reference for cases where quasi-experimental methods don't apply: unit-level counterfactuals, mediation via full structural decomposition, or mechanism simulation. Requires PyMC. For the default workflow, prefer quasi-experimental designs — fewer assumptions.

## Contents

1. [When to use structural models](#when-to-use-structural-models)
2. [pm.do() for interventions](#pmdo-for-interventions)
3. [pm.observe() for conditioning](#pmobserve-for-conditioning)
4. [Counterfactual queries](#counterfactual-queries)
5. [Mediation via SCM](#mediation-via-scm)
6. [Structural vs quasi-experimental: decision guide](#structural-vs-quasi-experimental-decision-guide)

---

## When to use structural models

Choose a structural causal model (SCM) when:

- You have a credible causal theory and want to model mechanisms explicitly
- The problem does not fit a quasi-experimental template (no natural experiment, no discontinuity, no instrument)
- You need **counterfactual queries** — "what would have happened to *this specific unit* if X had been different?" — which quasi-experimental methods cannot answer
- You need to **decompose effects** into direct and indirect paths (mediation with flexible functional forms)

**Advantage:** flexible, answers counterfactuals, decomposes effects, transparent about assumptions via the DAG.

**Disadvantage:** requires specifying the full structural model — more assumptions, more ways to be wrong. If a quasi-experimental design is available, prefer it. Fewer assumptions is better.

All examples use PyMC (tested on PyMC ≥ 5.10 where `pm.do` and `pm.observe` are part of the public API). Nothing here depends on CausalPy.

---

## pm.do() for interventions

`pm.do()` implements the do-calculus: it cuts incoming edges to the intervened variable, simulating an ideal randomized experiment on the existing model graph.

```python
import pymc as pm
import numpy as np

RANDOM_SEED = sum(map(ord, "causal-structural-v1"))
rng = np.random.default_rng(RANDOM_SEED)

# 1. Define the generative (observational) model
with pm.Model() as scm:
    Z = pm.Normal("Z", mu=0, sigma=1)                    # confounder
    X = pm.Normal("X", mu=0.5 * Z, sigma=0.5)            # treatment caused by Z
    Y = pm.Normal("Y", mu=0.3 * X + 0.7 * Z, sigma=0.5)  # outcome

# 2. Intervene: set X = 1 (do-calculus)
scm_do_1 = pm.do(scm, {"X": 1})
with scm_do_1:
    idata_do_1 = pm.sample_prior_predictive(samples=2000, random_seed=rng)

# 3. Compare do(X=1) vs do(X=0) for the Average Treatment Effect
scm_do_0 = pm.do(scm, {"X": 0})
with scm_do_0:
    idata_do_0 = pm.sample_prior_predictive(samples=2000, random_seed=rng)

ate = idata_do_1.prior["Y"].mean() - idata_do_0.prior["Y"].mean()
print(f"ATE: {float(ate):.3f}")   # Should recover ≈ 0.3 (the direct X→Y coefficient)
```

**Note.** `sample_prior_predictive` here gives the ATE under the prior (forward simulation). For posterior-based counterfactuals — using observed data to sharpen the estimate — condition with `pm.observe()` first, then intervene with `pm.do()`.

---

## pm.observe() for conditioning

`pm.observe()` conditions the model on observed data, fixing variables to their measured values. This is the standard way to incorporate data into an SCM before counterfactual reasoning.

```python
scm_obs = pm.observe(scm, {"Y": y_observed})
with scm_obs:
    idata_obs = pm.sample(nuts_sampler="nutpie", random_seed=rng)
```

Use `pm.observe()` when you want to:

- Fit the structural model to data (standard Bayesian inference)
- Perform the **abduction** step of a counterfactual query (see below)
- Infer latent confounders from observed variables

---

## Counterfactual queries

A counterfactual query asks: *"What would Y have been for **this specific unit** if X had been different?"* This is a unit-level question, not a population average — quasi-experimental methods cannot answer it.

The answer requires the **three-step abduction-action-prediction** procedure (Pearl):

1. **Abduction**: condition on the unit's factual observations to infer their latent factors.
2. **Action**: intervene on the treatment using `pm.do()`.
3. **Prediction**: forward-simulate the outcome under the counterfactual treatment, using the inferred latent factors from step 1.

```python
# Step 1: Abduction — infer this unit's latent confounder Z
scm_unit = pm.observe(scm, {"X": x_factual, "Y": y_factual})
with scm_unit:
    idata_abduction = pm.sample(nuts_sampler="nutpie", random_seed=rng)

# Steps 2 & 3: Action + Prediction
z_post = idata_abduction.posterior["Z"]
y_counterfactual = 0.3 * x_counterfactual + 0.7 * z_post   # using the known structural form

print(f"Counterfactual Y mean: {float(y_counterfactual.mean()):.3f}")
print(f"Counterfactual Y 95% interval: "
      f"[{float(y_counterfactual.quantile(0.025)):.3f}, "
      f"{float(y_counterfactual.quantile(0.975)):.3f}]")
```

**Critical assumption:** the structural equations and noise distributions are the same in the factual and counterfactual worlds. Misspecify the model, and the counterfactual inherits every flaw.

---

## Mediation via SCM

Mediation decomposes the total treatment effect into:

- **Total effect (TE)**: the full effect of T on Y through all paths
- **Natural direct effect (NDE)**: the effect of T on Y that does NOT pass through the mediator M
- **Natural indirect effect (NIE)**: the effect of T on Y that operates through M

Additive decomposition (linear case): `TE ≈ NDE + NIE`.

```python
# Schematic DAG: T → Y (direct), T → M → Y (indirect)
# NDE: intervene do(T=1) but hold M fixed at its distribution under do(T=0)
# NIE: intervene do(T=0) but let M take its distribution under do(T=1)

with pm.Model() as mediation_scm:
    T = pm.Bernoulli("T", p=0.5)
    M = pm.Normal("M", mu=0.6 * T, sigma=0.5)            # mediator
    Y = pm.Normal("Y", mu=0.4 * T + 0.5 * M, sigma=0.5)  # outcome

# Sketch — full implementation chains pm.do() calls:
# 1) Sample M under do(T=0)
# 2) Use that M in Y's equation under do(T=1)  -> NDE
# 3) Sample M under do(T=1)
# 4) Use that M in Y's equation under do(T=0)  -> NIE
```

Alternative: Bayesian SEM with chained structural equations, computing NDE/NIE from posterior draws of structural coefficients (a·b for indirect, c for direct). `pm.do()` is preferred because it makes the interventional logic explicit and avoids manual algebra; both approaches agree when the model is correctly specified.

**Strong assumptions for mediation — make them explicit:**

1. No unmeasured T–M confounding
2. No unmeasured M–Y confounding
3. No unmeasured T–Y confounding
4. No effect of T on M–Y confounders (a particularly restrictive condition in longitudinal settings)

Violation of any of these invalidates the NDE/NIE decomposition. Always communicate these assumptions to the user before reporting mediated effects.

---

## Structural vs quasi-experimental: decision guide

| Situation | Recommendation |
|---|---|
| Natural experiment available (policy change, geographic cutoff, lottery) | Quasi-experimental — fewer assumptions |
| Estimate mechanisms (through which path does T affect Y?) | Structural — decompose effects via mediation |
| Counterfactual for a specific unit, not a population average | Structural — quasi-experiments give population-level estimates only |
| Limited domain knowledge of the full causal mechanism | Quasi-experimental — avoid specifying a model you cannot defend |
| Complex DAG with multiple mediators and confounders | Structural — can model the full graph explicitly |
| External validity matters (does the effect generalize under distribution shift?) | Structural — simulate under shifts via `pm.do()` |
| Speed and robustness are priorities over mechanism | Quasi-experimental — simpler identification assumptions |

**When in doubt, ask: "Do I have a credible natural experiment?"** If yes, start there. If no, build the SCM and be explicit about every assumption in the DAG.
