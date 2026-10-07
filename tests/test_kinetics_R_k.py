"""Characterization test for kinetic_analyzer's de-globalized R/k entry points."""
import numpy as np
import pandas as pd

from analysis.kinetic_analyzer import compute_R_k_for_cycle, compute_R_k_for_cycles


def _synthetic_charge_cycle():
    # One cycle, one clean charge pulse: 3 active samples (I = +10 mA, rising E),
    # 6 rest samples (I = 0, relaxing E), then one more active sample so the rest
    # of pulse 1 is closed off and labelled (assign_valid_pulses only labels a
    # rest that is followed by another sample).
    return pd.DataFrame({
        "cycle": [1] * 10,
        "t/s":   [0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0],
        "I/mA":  [10, 10, 10, 0, 0, 0, 0, 0, 0, 10],
        "E/V":   [3.00, 3.05, 3.10, 3.08, 3.06, 3.05, 3.045, 3.042, 3.040, 3.20],
    })


def test_compute_R_k_for_cycle_returns_finite_R_k():
    df = _synthetic_charge_cycle()
    # window: index mode, 1-based inclusive points 1-4 (= 0-based [0:4], 4 pts)
    result = compute_R_k_for_cycle(df, cycle_num=1, phase="charge",
                                   window_mode="index", window_start=1, window_end=4)
    assert result is not None
    assert [int(p) for p in result["pulse_nums"]] == [1]
    assert len(result["R"]) == 1 and len(result["k"]) == 1
    # Charge pulse relaxes downward -> intercept & slope < 0, current > 0,
    # so R = -intercept/I and k = -slope/I both come out positive.
    assert np.isfinite(result["R"][0]) and result["R"][0] > 0
    assert np.isfinite(result["k"][0]) and result["k"][0] > 0


def test_compute_R_k_for_cycle_none_cases():
    df = _synthetic_charge_cycle()
    assert compute_R_k_for_cycle(None, cycle_num=1, phase="charge") is None
    assert compute_R_k_for_cycle(df, cycle_num=99, phase="charge") is None


def test_compute_R_k_for_cycles_wraps_cycle():
    df = _synthetic_charge_cycle()
    results = compute_R_k_for_cycles(df, [1], "charge",
                                     window_mode="index", window_start=1, window_end=4)
    assert len(results) == 1
    assert results[0]["cycle"] == 1