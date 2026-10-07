"""Characterization test for pulse_analyzer's de-globalized analyze_cycle_pulses."""
import pandas as pd

from analysis.pulse_analyzer import analyze_cycle_pulses


def _synthetic_charge_cycle():
    # One cycle, one clean charge pulse: 3 active samples (I = +10 mA), 6 rest
    # samples (I = 0). cycle_phase is set explicitly so the test is isolated from
    # whichever classifier get_phase_classifier() imports.
    return pd.DataFrame({
        "cycle": [1] * 9,
        "t/s":   [0.0, 1, 2, 3, 4, 5, 6, 7, 8],
        "I/mA":  [10, 10, 10, 0, 0, 0, 0, 0, 0],
        "E/V":   [3.00, 3.05, 3.10, 3.08, 3.06, 3.05, 3.045, 3.042, 3.040],
        "cycle_phase": ["charge"] * 9,
    })


def test_analyze_cycle_returns_expected_pulses():
    result = analyze_cycle_pulses(_synthetic_charge_cycle(), cycle_num=1)
    assert result.cycle == 1
    assert result.charge_pulses == [1]
    assert result.discharge_pulses == []
    assert not result.charge_data.empty
    for col in ("pulse_number", "V0", "t0"):
        assert col in result.charge_data.columns


def test_analyze_cycle_none_and_missing_are_empty():
    df = _synthetic_charge_cycle()
    for r in (analyze_cycle_pulses(None, 1), analyze_cycle_pulses(df, 99)):
        assert r.charge_pulses == [] and r.discharge_pulses == []
        assert r.charge_data.empty and r.discharge_data.empty


def test_single_source_of_truth():
    """F1 guard: each core algorithm has exactly ONE implementation, imported
    everywhere. If a divergent copy is reintroduced, these identity checks fail."""
    import analysis.pulse_analyzer as pa
    import analysis.regression_analyzer as ra
    import analysis.phase_classifier as pc

    # pulse segmentation: pulse_analyzer reuses regression_analyzer's functions
    assert pa.assign_valid_pulses is ra.assign_valid_pulses
    assert pa.compute_V0_t0 is ra.compute_V0_t0
    # phase classification: regression_analyzer re-exports phase_classifier's
    assert ra.classify_charge_discharge is pc.classify_charge_discharge