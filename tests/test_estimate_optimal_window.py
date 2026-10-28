"""Tests for estimate_optimal_window — the opt-in auto fit-window estimator.

Covers: it recovers a wide window on clean √t-linear data, flags a curved
(non-diffusive) pulse, skips the IR-drop first point, returns None when the rest
is too short, and that the vectorised candidate scan is numerically identical to
the canonical single-pulse fit (so the accelerator changes no numbers).
"""
import numpy as np
import pandas as pd
import pytest

from analysis.regression_analyzer import (
    estimate_optimal_window, compute_single_pulse_regression, _scan_windows,
    AUTO_MIN_POINTS,
)


def _rest(t, dv):
    return pd.DataFrame({'t/s': np.asarray(t, float), 'ΔV': np.asarray(dv, float)})


def test_too_short_returns_none():
    t = np.linspace(0.0, 1.0, 4)
    assert estimate_optimal_window(_rest(t, t)) is None


def test_clean_linear_uses_wide_window_no_flags():
    rng = np.random.default_rng(0)
    t = np.linspace(0.0, 10.0, 120)
    sqrt_t = np.sqrt(t - t[0])
    dv = 0.10 + 0.02 * sqrt_t + rng.normal(0, 2e-5, t.size)   # linear in √t
    out = estimate_optimal_window(_rest(t, dv))
    assert out is not None
    assert out['flags'] == []
    assert out['n_points'] > 100                 # uses most of the rest
    assert out['slope'] == pytest.approx(0.02, rel=0.02)
    assert np.isfinite(out['k_relerr']) and out['k_relerr'] < 0.01


def test_skips_ir_drop_first_point():
    rng = np.random.default_rng(1)
    t = np.linspace(0.0, 10.0, 120)
    sqrt_t = np.sqrt(t - t[0])
    dv = 0.10 + 0.02 * sqrt_t + rng.normal(0, 1e-5, t.size)
    dv[0] -= 0.01                                # off-line instantaneous point
    out = estimate_optimal_window(_rest(t, dv))
    assert out is not None
    assert out['index_start'] >= 2               # first sample excluded


def test_curved_pulse_is_flagged():
    # A relaxation that saturates fast: almost no √t-linear region exists, so no
    # wide clean window qualifies and it must fall back with a low-confidence flag.
    t = np.linspace(0.0, 10.0, 120)
    dv = 0.10 + 0.05 * (1.0 - np.exp(-t / 0.1))
    out = estimate_optimal_window(_rest(t, dv))
    assert out is not None
    assert out['flags']                          # non-empty
    assert 'low_confidence' in out['flags']


def test_vectorised_scan_matches_canonical():
    rng = np.random.default_rng(2)
    t = np.linspace(0.0, 10.0, 80)
    sqrt_t = np.sqrt(t - t[0])
    dv = 0.1 + 0.02 * sqrt_t + rng.normal(0, 5e-4, t.size)
    rest = _rest(t, dv)
    end, n_pts, slope, intercept, r2, se_sl, se_in, valid = _scan_windows(
        sqrt_t, dv, 1, AUTO_MIN_POINTS)
    for length in (5, 20, 50, 79):
        j = length - 1
        ref = compute_single_pulse_regression(rest, 1, length)
        assert slope[j] == pytest.approx(ref['slope'], rel=1e-9, abs=1e-12)
        assert intercept[j] == pytest.approx(ref['intercept'], rel=1e-9, abs=1e-12)
        assert r2[j] == pytest.approx(ref['r2'], rel=1e-9, abs=1e-12)
        assert se_sl[j] == pytest.approx(np.sqrt(ref['cov'][0, 0]), rel=1e-9, abs=1e-12)
