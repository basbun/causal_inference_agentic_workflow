"""Reusable causal-inference helpers for backdoor-adjustment estimators.

Kept dependency-light (numpy / pandas / scikit-learn only) so the pipeline runs
with the project's declared dependencies. All estimators target the ATT (effect
of treatment on the treated), which is the policy-relevant estimand for a
voluntary program.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


@dataclass
class Estimate:
    name: str
    estimand: str
    point: float
    se: float
    ci_low: float
    ci_high: float
    n: int

    def as_dict(self) -> dict:
        return {
            "estimator": self.name,
            "estimand": self.estimand,
            "point": round(self.point, 4),
            "se": round(self.se, 4),
            "ci_low": round(self.ci_low, 4),
            "ci_high": round(self.ci_high, 4),
            "n": self.n,
        }


def design_matrix(df: pd.DataFrame, covariates: list[str]) -> np.ndarray:
    """One-hot encode categoricals, pass numerics through."""
    return pd.get_dummies(df[covariates], drop_first=True).astype(float).values


def fit_propensity(X: np.ndarray, t: np.ndarray) -> np.ndarray:
    model = Pipeline(
        [("scale", StandardScaler()),
         ("lr", LogisticRegression(max_iter=2000, C=1.0))]
    )
    model.fit(X, t)
    return model.predict_proba(X)[:, 1]


def standardized_mean_diff(x: np.ndarray, t: np.ndarray, w: np.ndarray | None = None) -> float:
    """Weighted standardized mean difference between treated and control."""
    treated, control = t == 1, t == 0
    if w is None:
        w = np.ones_like(t, dtype=float)
    wt, wc = w[treated], w[control]
    mt = np.average(x[treated], weights=wt)
    mc = np.average(x[control], weights=wc)
    vt = np.average((x[treated] - mt) ** 2, weights=wt)
    vc = np.average((x[control] - mc) ** 2, weights=wc)
    pooled = np.sqrt((vt + vc) / 2.0)
    return float((mt - mc) / pooled) if pooled > 0 else 0.0


def att_ipw_weights(ps: np.ndarray, t: np.ndarray) -> np.ndarray:
    """ATT weights: treated get 1, controls get ps/(1-ps)."""
    w = np.where(t == 1, 1.0, ps / np.clip(1.0 - ps, 1e-6, None))
    return w


def _att_ipw_point(y, t, ps):
    w = att_ipw_weights(ps, t)
    treated, control = t == 1, t == 0
    return np.average(y[treated], weights=w[treated]) - np.average(y[control], weights=w[control])


def _att_aipw_point(y, t, X, ps):
    """Doubly-robust ATT (augmented IPW)."""
    treated = t == 1
    # Outcome model fit on controls -> predicted untreated potential outcome.
    mu0 = LinearRegression().fit(X[~treated], y[~treated]).predict(X)
    n_t = treated.sum()
    odds = ps / np.clip(1.0 - ps, 1e-6, None)
    correction = (~treated) * odds * (y - mu0)
    att = (y[treated] - mu0[treated]).sum() / n_t - correction.sum() / n_t
    return float(att)


def _att_ancova_point(y, t, X):
    """OLS / ANCOVA: regress y on treatment + covariates, read treatment coef."""
    XX = np.column_stack([t.astype(float), X])
    coef = LinearRegression().fit(XX, y).coef_
    return float(coef[0])


def _naive_point(y, t):
    return float(y[t == 1].mean() - y[t == 0].mean())


def bootstrap_ci(point_fn, n: int, n_boot: int, seed: int, cluster: np.ndarray | None = None):
    """Nonparametric bootstrap. If `cluster` given, resample whole clusters."""
    rng = np.random.default_rng(seed)
    idx_all = np.arange(n)
    boots = []
    if cluster is not None:
        groups = pd.Series(idx_all).groupby(cluster).apply(lambda s: s.values).to_list()
    for _ in range(n_boot):
        if cluster is None:
            idx = rng.choice(idx_all, size=n, replace=True)
        else:
            chosen = rng.choice(len(groups), size=len(groups), replace=True)
            idx = np.concatenate([groups[g] for g in chosen])
        try:
            boots.append(point_fn(idx))
        except Exception:
            continue
    boots = np.array(boots)
    return float(boots.std(ddof=1)), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def estimate_all(
    df: pd.DataFrame,
    outcome: str,
    treatment: str,
    covariates: list[str],
    ps: np.ndarray,
    n_boot: int = 500,
    seed: int = 7,
) -> list[Estimate]:
    """Run naive, ANCOVA, IPW, and AIPW ATT estimators with bootstrap CIs.

    For the propensity-based estimators (IPW, AIPW) the propensity model is
    **refit inside every bootstrap resample** rather than reusing the supplied
    ``ps``. Treating the estimated propensity as if it were known understates
    uncertainty; refitting propagates the first-stage estimation error into the
    confidence intervals. ``ps`` is still used only for the headline point
    estimate (it is the model fit on the full sample in the prep step).
    """
    y = df[outcome].values
    t = df[treatment].values
    X = design_matrix(df, covariates)
    n = len(df)

    def ipw(idx):
        ps_b = ps[idx] if len(idx) == n and np.array_equal(idx, np.arange(n)) \
            else fit_propensity(X[idx], t[idx])
        return _att_ipw_point(y[idx], t[idx], ps_b)

    def aipw(idx):
        ps_b = ps[idx] if len(idx) == n and np.array_equal(idx, np.arange(n)) \
            else fit_propensity(X[idx], t[idx])
        return _att_aipw_point(y[idx], t[idx], X[idx], ps_b)

    specs = {
        "Naive (unadjusted)": lambda idx: _naive_point(y[idx], t[idx]),
        "ANCOVA (OLS)": lambda idx: _att_ancova_point(y[idx], t[idx], X[idx]),
        "IPW (ATT)": ipw,
        "AIPW (doubly robust)": aipw,
    }
    results = []
    for name, fn in specs.items():
        point = fn(np.arange(n))
        se, lo, hi = bootstrap_ci(fn, n, n_boot, seed)
        results.append(Estimate(name, "ATT", point, se, lo, hi, n))
    return results
