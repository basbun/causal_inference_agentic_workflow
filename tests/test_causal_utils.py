"""Tests for identification-critical logic.

Guards: ATT weight construction, SMD computation, and -- most importantly --
that the AIPW estimator recovers a known true effect on simulated data with a
confounder fully in the adjustment set (no residual confounding => unbiased).
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from src.causal_utils import (  # noqa: E402
    att_ipw_weights, fit_propensity, standardized_mean_diff, estimate_all,
)


def test_att_weights_treated_are_one():
    ps = np.array([0.2, 0.8, 0.5])
    t = np.array([1, 0, 1])
    w = att_ipw_weights(ps, t)
    assert np.allclose(w[t == 1], 1.0)
    assert np.isclose(w[1], 0.8 / 0.2)  # control: ps/(1-ps)


def test_smd_zero_when_identical():
    x = np.array([1.0, 2.0, 1.0, 2.0])
    t = np.array([1, 1, 0, 0])
    assert abs(standardized_mean_diff(x, t)) < 1e-9


def test_aipw_recovers_known_effect_no_residual_confounding():
    """With the confounder fully observed and in the adjustment set, AIPW
    should be ~unbiased for the true ATT."""
    rng = np.random.default_rng(0)
    n = 4000
    x = rng.standard_normal(n)
    p = 1 / (1 + np.exp(-(0.8 * x - 0.5)))
    t = rng.binomial(1, p)
    true_att = 0.5
    y = 1.0 + 0.7 * x + true_att * t + rng.normal(0, 0.5, n)
    df = pd.DataFrame({"x": x, "t": t, "y": y})
    ps = fit_propensity(df[["x"]].values, df["t"].values)
    ests = {e.name: e for e in estimate_all(df, "y", "t", ["x"], ps, n_boot=50)}
    aipw = ests["AIPW (doubly robust)"].point
    assert abs(aipw - true_att) < 0.05, f"AIPW {aipw} far from {true_att}"
    # Naive must be visibly biased upward (confounding present).
    assert ests["Naive (unadjusted)"].point > true_att + 0.1
