"""Known-answer tests for the ICI analysis core.

These pin the regression math and R/k extraction to hand-computed values, so
future refactors cannot silently change the science.
"""
import numpy as np
import pandas as pd
import pytest

from analysis.regression_analyzer import compute_single_pulse_regression, r2_score
from analysis.kinetic_analyzer import compute_R_k


def test_perfect_line_recovers_slope_and_intercept():
    # ΔV = 5 + 2*sqrt(t):  t=0,1,4,9,16,25 -> sqrt(t)=0..5 -> ΔV=5,7,9,11,13,15
    t = np.array([0.0, 1.0, 4.0, 9.0, 16.0, 25.0])
    dv = 5.0 + 2.0 * np.sqrt(t)
    rest = pd.DataFrame({"t/s": t, "ΔV": dv})

    result = compute_single_pulse_regression(rest, r1_start=0, r1_length=len(t))

    assert result["slope"] == pytest.approx(2.0, rel=1e-9)
    assert result["intercept"] == pytest.approx(5.0, rel=1e-9)
    assert result["r2"] == pytest.approx(1.0, abs=1e-12)


def test_regression_window_is_respected():
    # First 3 points lie on ΔV = 1 + 3*sqrt(t); the rest bend off that line.
    # A window over the first 3 points must recover slope 3, intercept 1 only.
    t = np.array([0.0, 1.0, 4.0, 9.0, 16.0, 25.0])
    dv = np.array([1.0, 4.0, 7.0, 7.0, 8.0, 8.5])
    rest = pd.DataFrame({"t/s": t, "ΔV": dv})

    result = compute_single_pulse_regression(rest, r1_start=0, r1_length=3)

    assert result["slope"] == pytest.approx(3.0, rel=1e-9)
    assert result["intercept"] == pytest.approx(1.0, rel=1e-9)


def test_r2_score_perfect_and_mean_prediction():
    y = np.array([1.0, 2.0, 3.0, 4.0])
    assert r2_score(y, y) == pytest.approx(1.0)
    assert r2_score(y, np.full_like(y, y.mean())) == pytest.approx(0.0)


def test_compute_R_k_known_values():
    # One pulse: an active row (10 mA) immediately before rest rows (0 mA).
    data = pd.DataFrame({
        "pulse_number": [1, 1, 1],
        "I/mA":         [10.0, 0.0, 0.0],
        "E/V":          [3.50, 3.45, 3.46],
    })
    # Known fit: intercept = -0.5 V, slope = -0.1 V/sqrt(s); zero covariance.
    regression_results = [{
        "pulse": 1, "intercept": -0.5, "slope": -0.1,
        "cov": np.zeros((2, 2)), "V0": 3.5,
    }]

    _, (R_vals, R_errs), (k_vals, k_errs) = compute_R_k(data, [1], regression_results)

    # I = 10 mA = 0.01 A -> R = -intercept/I = 50 ohm, k = -slope/I = 10 ohm s^-1/2
    assert R_vals[0] == pytest.approx(50.0, rel=1e-9)
    assert k_vals[0] == pytest.approx(10.0, rel=1e-9)
    assert R_errs[0] == pytest.approx(0.0, abs=1e-12)
    assert k_errs[0] == pytest.approx(0.0, abs=1e-12)