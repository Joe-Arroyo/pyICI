"""Known-answer tests for phase_classifier (classification + capacity)."""
import numpy as np
import pandas as pd
import pytest

from analysis.phase_classifier import classify_charge_discharge, calculate_capacity


def test_classify_charge_discharge_labels():
    # +current -> charge; -current -> discharge; a 0 following -current is
    # absorbed into the discharge run.
    df = pd.DataFrame({"I/mA": [1.0, 1.0, -1.0, -1.0, 0.0]})
    labels = classify_charge_discharge(df)
    assert list(labels) == ["charge", "charge", "discharge", "discharge", "discharge"]


def test_classify_leading_zero_is_rest():
    df = pd.DataFrame({"I/mA": [0.0, 2.0, -2.0]})
    labels = classify_charge_discharge(df)
    assert list(labels) == ["rest", "charge", "discharge"]


def test_calculate_capacity_charge_segment():
    # constant 10 mA charge, 1 h steps -> 10 mAh accrued per step, cumulative
    df = pd.DataFrame({
        "I/mA": [10.0, 10.0, 10.0, 10.0],
        "t/s":  [0.0, 3600.0, 7200.0, 10800.0],
    })
    out = calculate_capacity(df, mass_mg=1000)     # specific = capacity / (1000/1000)
    assert out["capacity_mAh"].tolist() == pytest.approx([0.0, 10.0, 20.0, 30.0])
    assert out["specific_capacity"].tolist() == pytest.approx([0.0, 10.0, 20.0, 30.0])


def test_calculate_capacity_resets_at_phase_change():
    # charge then discharge -> capacity restarts at 0 for the discharge segment
    df = pd.DataFrame({
        "I/mA": [10.0, 10.0, -10.0, -10.0],
        "t/s":  [0.0, 3600.0, 7200.0, 10800.0],
    })
    out = calculate_capacity(df, mass_mg=0)
    assert out["capacity_mAh"].tolist() == pytest.approx([0.0, 10.0, 0.0, 10.0])
    assert out["specific_capacity"].isna().all()   # no mass -> NaN