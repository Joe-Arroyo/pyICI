"""Characterization test for load_cycle_for_regression (data-in / return-out API)."""
import pandas as pd
import pytest

from analysis.regression_analyzer import load_cycle_for_regression


def _synthetic_cycle():
    # One cycle: two charge pulses (10 mA active + rest), then one discharge pulse.
    return pd.DataFrame({
        "cycle": [1] * 12,
        "t/s":   [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11],
        "I/mA":  [10, 10, 0, 0, 10, 10, 0, 0, -10, -10, 0, 0],
        "E/V":   [3.00, 3.01, 3.02, 3.03, 3.10, 3.11, 3.12, 3.13,
                  3.40, 3.41, 3.42, 3.43],
    })


def test_load_cycle_returns_expected_pulses():
    result = load_cycle_for_regression(_synthetic_cycle(), cycle_num=1)
    assert result is not None
    assert result.cycle == 1
    assert [int(p) for p in result.charge_pulses] == [1, 2]
    assert [int(p) for p in result.discharge_pulses] == [1]
    for col in ("pulse_number", "V0", "t0"):
        assert col in result.charge_data.columns
        assert col in result.discharge_data.columns


def test_load_cycle_missing_cycle_returns_none():
    result = load_cycle_for_regression(_synthetic_cycle(), cycle_num=99)
    assert result is None