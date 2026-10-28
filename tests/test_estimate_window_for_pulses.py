"""Tests for the cycle/all-cycles shared-window helper and its support
functions: pulse_rest_data and estimate_window_for_pulses.
"""
import numpy as np
import pandas as pd

from analysis.regression_analyzer import (
    pulse_rest_data, estimate_window_for_pulses,
)


def _make_phase_data(n_pulses=4, curved=frozenset(), n_rest=60, seed=0):
    """A minimal phase DataFrame: each pulse has 2 active samples then a rest
    whose ΔV = E/V - V0 is linear in √t (or a saturating curve for `curved`)."""
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(1, n_pulses + 1):
        v0 = 3.0 + 0.01 * p
        for k in range(2):                          # active samples (I != 0)
            rows.append({'pulse_number': p, 't/s': k * 0.1, 'E/V': v0, 'I/mA': 1.0, 'V0': v0})
        t = np.linspace(0.0, 10.0, n_rest)
        if p in curved:
            dv = 0.05 * (1.0 - np.exp(-t / 0.1))    # saturates fast — not √t-linear
        else:
            dv = 0.1 + 0.02 * np.sqrt(t) + rng.normal(0, 2e-5, n_rest)
        for ti, dvi in zip(t, dv):                  # rest samples (I == 0)
            rows.append({'pulse_number': p, 't/s': 100.0 + ti, 'E/V': v0 + dvi,
                         'I/mA': 0.0, 'V0': v0})
    return pd.DataFrame(rows)


def test_pulse_rest_data_builds_delta_v():
    rest = pulse_rest_data(_make_phase_data(n_pulses=1), 1)
    assert rest is not None and 'ΔV' in rest.columns
    assert abs(rest['ΔV'].iloc[0] - 0.1) < 0.01     # dv = 0.1 + 0.02*sqrt(0)


def test_shared_window_linear_pulses():
    data = _make_phase_data(n_pulses=4)
    out = estimate_window_for_pulses(data, [1, 2, 3, 4])
    assert out is not None
    assert out['time_end'] > out['time_start']
    assert out['n_pulses'] == 4
    assert out['n_flagged'] == 0
    assert out['flags'] == []
    assert len(out['per_pulse']) == 4


def test_shared_window_flags_curved_pulse():
    data = _make_phase_data(n_pulses=4, curved={3})
    out = estimate_window_for_pulses(data, [1, 2, 3, 4])
    assert out is not None
    flagged = [pp['pulse'] for pp in out['per_pulse'] if pp['flags']]
    assert 3 in flagged                              # the curved pulse is caught
    assert out['n_flagged'] >= 1


def test_no_pulses_returns_none():
    assert estimate_window_for_pulses(_make_phase_data(n_pulses=1), []) is None
