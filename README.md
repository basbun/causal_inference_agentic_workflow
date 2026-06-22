# impact-eval-causal-inference-template

A reproducible starter repository for **impact evaluation / causal inference** projects with:

- design-first analysis driven by a 10-step canonical workflow
- strong project hygiene for assumptions, diagnostics, and reporting
- a data pipeline layout that separates raw / interim / processed data
- VS Code + GitHub Copilot custom agents and prompts tailored to causal work

This template is intentionally opinionated. It assumes:

1. you want **design-first** analysis rather than "run models until something works"
2. you care about **identification assumptions**, not just effect estimates
3. you want artifacts that survive handoff to collaborators, reviewers, or your future self

---

## How to use this repo

**Try it first with the included example.** This repo ships with a populated `configs/project.yaml` for a manager leadership development program evaluation — a realistic observational setup with voluntary participation and uneven program uptake across departments. The raw data is **not** committed (everything under `data/` is git-ignored, by design — raw data stays out of version control), so generate the matching dummy dataset with one command:

```bash
pip install -e .                          # install dependencies
python scripts/00_generate_dummy_data.py  # writes data/raw/manager_data.csv
```

A complete, already-run worked example of the full workflow on this data lives in `scripts/`, `docs/plans/`, and `reports/` — see [`docs/walkthrough.html`](docs/walkthrough.html) for an interactive end-to-end explainer. To run the pipeline yourself end to end, see [Running the worked example](#running-the-worked-example). To use the repo on your own project, replace `project.yaml` and the contents of `data/raw/` as described below.

## Running the worked example

The repo includes a fully worked run of the canonical workflow on the
manager-leadership dataset, so you can see real outputs before pointing it at
your own data. From the repo root:

```bash
pip install -e .                            # numpy, pandas, scikit-learn, matplotlib, ...
python scripts/00_generate_dummy_data.py    # data/raw/manager_data.csv (synthetic, known true effect)
python scripts/01_prepare_data.py           # propensity score + common-support flag -> data/processed/
python scripts/02_estimate.py               # estimators, diagnostics, refutation -> results/ + reports/
pytest                                       # identification-critical guard tests
```

Outputs: machine-readable results in `results/summary.json`, tables/figures in
`reports/`, the approved plan in `docs/plans/manager-leadership.md`, and a
narrative report in `reports/manager-leadership-report.md`. Because the dummy
data is generated with a **known true effect**, you can check the estimates
against ground truth. For a guided, interactive explanation of every step and
the underlying concepts, open [`docs/walkthrough.html`](docs/walkthrough.html).

---

### 1. Fill in configs/project.yaml

This is your **single source of truth**. The repo ships with an example project.yaml for the included manager-leadership dataset — replace it with your own project's details before running the agents on your data.
- what the intervention is and how it was assigned
- who was treated and who was not
- what outcomes you care about and when they are measured
- what pre-treatment covariates you have
- where your raw data files live

The agents read this file first and will not re-ask questions already answered here.

### 2. Drop raw data into data/raw/

Place your source data files in `data/raw/` and register their paths under `raw_data_files` in `project.yaml`.
These files are **immutable** — never edit them. All transformations go into scripts.

### 3. Ask the Planner to read project.yaml and prepare a plan

Open Copilot Chat, switch to the **Planner** agent, and say:

> "Read configs/project.yaml and prepare a causal estimation plan."

The Planner will:
- Read `project.yaml` for everything already known.
- Formulate the causal question and estimand.
- Run structural EDA on your raw data to check positivity and eligibility.
- Emulate a target trial (for observational data).
- Draw a DAG and confirm it with you.
- Output an identification block (strategy, assumptions, identification status).
- Choose an estimator matched to the identified problem.
- Ask clarifying questions via the VS Code `askQuestions` interface for any design-critical unknowns not covered by `project.yaml`. **Answer these before proceeding.**
- Write the approved plan to `docs/plans/<slug>.md` and design decisions to `docs/plans/<slug>-design.yaml`.

### 4. Hand off to the Implementer

Once the plan is approved, switch to the **Implementer** agent and say:

> "Implement the plan in docs/plans/<slug>.md."

The Implementer will run an environment check, then implement in order: data preparation,
estimation, diagnostics, refutation, and reporting. If any diagnostic guardrail fails it stops
and surfaces the failure — no summary artifact is emitted until the issues are resolved.

### 5. Route to the Reviewer

Switch to the **Reviewer** agent. It checks both the design and the implementation, classifies
every finding as design-level (back to Planner) or code-level (back to Implementer), and emits
a routing block. Iterate until the Reviewer emits `terminal: true`. Then ask the Reviewer to use 
all relevant files and artifacts to create a Word document describing the methodology and results of the analysis.

### Optional: use the Orchestrator as a single entry point

Use the **Impact Eval Orchestrator** agent instead of addressing Planner / Implementer / Reviewer
directly. The Orchestrator reads `project.yaml`, checks what already exists in `docs/plans/`,
and routes to the right agent at each stage.

---

## configs/project.yaml schema

```yaml
project:
  name: "Your project name"

task:
  problem: "The business or policy problem being addressed."
  solution: "The intervention or program being evaluated."
  ask: "What decision will this estimate inform?"

scope:
  treated_population: "Who received the treatment and how many."
  control_population: "Who did not receive the treatment and how many."
  notes:
    - "Any known facts about selection into treatment (opt-in, nomination, lottery, etc.)."

key_variables:
  pre_treatment_covariates:
    - "List covariates measured before treatment, with timing."
  outcomes:
    - "Outcome name, measurement timing, scale."
  treatment:
    - "Treatment variable name and definition."

raw_data_files:
  your_dataset: "data/raw/your_file.csv"

preferences:
  explain_results_simply: true
  ask_for_missing_important_info: true
```

---

## Repository layout

```
configs/
  project.yaml          <- fill this in first
data/
  raw/                  <- immutable source files; register paths in project.yaml
  interim/              <- intermediate transformations
  processed/            <- analysis-ready datasets
docs/
  plans/
    <slug>.md           <- approved plan (written by Planner)
    <slug>-design.yaml  <- answered design decisions (written by Planner)
results/                <- machine-readable outputs (JSON, CSV)
reports/
  tables/
  figures/
scripts/                <- pipeline scripts
src/                    <- reusable modules
tests/                  <- tests for identification-critical logic
.github/
  agents/               <- Orchestrator, Planner, Implementer, Reviewer
  skills/
    causal-inference/
      SKILL.md          <- 10-step workflow; all agents load this first
      references/       <- reference files loaded per step
```

---

## Hard stops the agents enforce

| Condition | Blocks |
|---|---|
| No DAG or DAG-equivalent argument | Identification step |
| Identification status not "identified" | Estimation |
| Structural positivity violation unresolved | Estimation |
| Environment check not passed | Estimation |
| Diagnostic guardrail breached | Reporting |

---

## Conventions

- Never edit files in `data/raw/`.
- All design decisions are saved before any estimation code is written.
- Robustness checks are first-class deliverables, not afterthoughts.
- Every table and figure is reproducible from code.
- All output artifacts record the plan version they were produced against.

---

## License

Add your preferred license before publishing externally.
