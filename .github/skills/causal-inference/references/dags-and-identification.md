# DAGs and Causal Identification

Concepts, structures, and identification criteria. For code to *estimate* the effect once identified, see `code-recipes.md`. For refutation, see `refutation-and-sensitivity.md`.

## Contents

1. [Drawing causal graphs](#drawing-causal-graphs)
2. [DAG specification in code](#dag-specification-in-code)
3. [Common causal structures](#common-causal-structures)
4. [Identification strategies](#identification-strategies)
5. [Finding adjustment sets](#finding-adjustment-sets)
6. [Collider bias warning](#collider-bias-warning)
7. [Prompt templates for DAG confirmation](#prompt-templates-for-dag-confirmation)

---

## Drawing causal graphs

A Directed Acyclic Graph (DAG) encodes causal structure with nodes (variables) and directed edges (direct causal effects). Arrows point from cause to effect.

**The most important rule: missing edges are the STRONGEST assumptions.** Omitting an edge asserts that one variable has no direct causal effect on another — a strong claim that must be justified by domain knowledge, not by convenience and never by the data.

Every edge and every non-edge requires a justification. Before touching data, be able to answer for each pair of variables: *why do I believe X does (or does not) directly cause Y?*

The DAG encodes domain knowledge, not statistical patterns. It cannot be learned from data alone. Two datasets with identical joint distributions can correspond to different causal DAGs. Fitting models and reading off a DAG is pattern matching, not causal inference.

---

## DAG specification in code

```python
import networkx as nx
from dowhy import CausalModel

dag = nx.DiGraph()
dag.add_edges_from([
    ("treatment", "outcome"),
    ("confounder", "treatment"),
    ("confounder", "outcome"),
])

model = CausalModel(
    data=df,
    treatment="treatment",
    outcome="outcome",
    graph=dag,
)
```

**Always add unobserved confounders explicitly.** DoWhy assumes no unobserved confounding unless you put a `U` node in the graph — a strong assumption that is almost never defensible in observational data.

```python
dag.add_edges_from([
    ("U_unobserved", "treatment"),
    ("U_unobserved", "outcome"),
])
```

For a graph string format (sometimes more readable in docs):

```python
graph_str = """digraph {
    treatment -> outcome;
    confounder -> treatment;
    confounder -> outcome;
    U -> treatment;
    U -> outcome;
}"""
model = CausalModel(data=df, treatment="treatment", outcome="outcome", graph=graph_str)
```

---

## Common causal structures

The four structures every causal graph is built from.

### 1. Confounder (fork)

```
   C
  / \
 v   v
 T → Y
```

C affects both treatment and outcome. Without adjusting for C, the T→Y estimate is biased. **Adjust for C** using regression, matching, IPW, or any valid backdoor method.

Example: age confounds exercise (T) and cardiovascular health (Y) — older people exercise less and have worse health independently.

### 2. Mediator (chain)

```
T → M → Y
```

M lies on a causal path from T to Y. **Do NOT adjust for M if you want the total effect.** Adjusting for a mediator blocks the indirect path and gives you only the direct effect — which may not be what you want.

Example: a training program (T) improves income (Y) partly through employment (M). Conditioning on employment removes the very mechanism you care about.

### 3. Collider (inverted fork)

```
 T   Y
  \ /
   v
   C
```

C is caused by both T and Y. **NEVER adjust for C.** Conditioning on a collider opens a non-causal path between T and Y, inducing spurious association even when T and Y are independent. See [Collider bias warning](#collider-bias-warning).

### 4. Instrument

```
Z → T → Y
```

Z is a valid instrument when:
1. **Relevance**: Z affects T
2. **Independence**: Z is as-good-as-randomly assigned with respect to potential outcomes
3. **Exclusion**: Z affects Y only through T

See the IV sections in `design-playbook.md` and `code-recipes.md`.

---

## Identification strategies

### Backdoor criterion

A set of variables S satisfies the backdoor criterion if:
1. No variable in S is a descendant of T
2. S blocks every path between T and Y that has an arrow into T (backdoor paths)

When S satisfies the backdoor criterion, adjusting for S identifies the causal effect. This is the most common identification strategy in observational studies.

### Frontdoor criterion

When all paths from T to Y go through a mediator M, and M has no unobserved confounders with Y, the frontdoor criterion applies. Rare in practice, but it permits identification even when T and Y have unobserved common causes. The estimator chains two regressions: T→M and M→Y, adjusting for T in the second.

### Instrumental variables

When a valid instrument Z exists (relevance + independence + exclusion), use 2SLS or an equivalent. IV yields the Local Average Treatment Effect (LATE) — the effect for compliers only, not the population ATE. Be explicit about this restriction when reporting.

### Design-based identification

Randomized assignment, regression discontinuity (RDD), difference-in-differences (DiD), synthetic control, and interrupted time series (ITS) provide identification through study design rather than adjustment. These require design-specific assumptions (parallel trends, continuity at a cutoff, stable trend model) that must be stated and diagnosed. See `design-playbook.md`.

### Structural / g-methods

For time-varying confounding affected by prior treatment, standard adjustment fails and g-methods (IPTW with marginal structural models, g-computation, g-estimation) are required. For unit-level counterfactuals or explicit mechanism decomposition, see `structural-models.md`.

---

## Finding adjustment sets

```python
identified_estimand = model.identify_effect(
    proceed_when_unidentifiable=False,   # NEVER set to True silently
)
print(identified_estimand)
```

DoWhy enumerates valid adjustment sets given your DAG and tells you which identification strategy it found.

**`proceed_when_unidentifiable=True` is scientific misconduct if used silently.** It instructs DoWhy to continue even when causal identification fails. If you use it, you must explicitly warn the reader that the resulting estimate is not causally identified and should be interpreted as an association.

When DoWhy reports the effect is not identifiable, the correct response is to revise the DAG (add instruments, rethink confounders, consider a design-based approach) — not to override the check.

---

## Collider bias warning

Adjusting for a collider **opens** a non-causal path between treatment and outcome, creating spurious associations that do not exist in the population. This is one of the most common and most damaging mistakes in causal inference.

**Classic example.** You study the effect of a disease (T) on recovery (Y) using data from a hospital. You "control for hospitalization" (H) because your sample is conditioned on it. But H is a collider — both disease severity and potential recovery affect who gets hospitalized. Conditioning on H induces a spurious negative association between disease and recovery even when none exists in the general population.

```
Severity → H ← Recovery
       T → H
       T → Y
```

This mistake is especially easy to make when:
- You filter the sample on a post-treatment variable
- You include a variable "to control for sample selection"
- You condition on any common effect of T and Y (or of their causes)

Always trace paths in your DAG before adding any variable to an adjustment set. When in doubt, use DoWhy's `identify_effect` — it will refuse to include a collider in its adjustment set.

---

## Prompt templates for DAG confirmation

Before proceeding with any causal analysis, confirm the DAG and its assumptions with the user. Use these verbatim or adapt them.

### DAG confirmation prompt

> Here is the causal graph I'm proposing:
>
> **Nodes:** [list all variables]
> **Edges (direct causal effects):** [list all arrows, e.g., 'age → treatment', 'treatment → outcome']
> **Non-edges (explicit no-direct-effect assumptions):** [list key omitted edges, e.g., 'income does NOT directly affect outcome, only through treatment']
>
> I'm assuming [X] does NOT directly cause [Y] — is that correct? Please confirm or correct each assumption before I proceed. Changing even one edge can change which variables to adjust for and whether the effect is identified at all.

### Assumption confirmation prompt

> This analysis rests on the following untestable assumptions:
>
> 1. [Assumption 1, e.g., 'No unobserved confounders of the treatment–outcome relationship other than those listed.']
> 2. [Assumption 2, e.g., 'The instrument Z affects Y only through T (exclusion restriction).']
> 3. [Assumption 3, e.g., 'The DAG is acyclic — no feedback loops exist between any variables.']
>
> Are you comfortable defending these in a peer review or stakeholder context? If any feel fragile, I will flag them prominently in the report and, where possible, run a sensitivity analysis to quantify how much hidden confounding would be needed to overturn the conclusion.

### When domain knowledge is insufficient

If the user says "I don't know if X causes Y" for a critical edge, stop and surface the problem:

> The DAG depends on whether [X] directly affects [Y]. This is not something I can infer from the data — the data are consistent with both versions. Can you point me to a domain expert, a literature review, or a mechanism-based argument that would settle this? If not, I can run the analysis both ways and report how the conclusion depends on this assumption.

This is better than proceeding on a guess. Silent assumptions are the source of most broken causal analyses.
