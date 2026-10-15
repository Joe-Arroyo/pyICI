"""Known-answer tests for the per-pulse helpers vectorized for performance:

* ``regression_analyzer.compute_V0_t0`` — V0/t0 = the last active (I != 0) sample
  of each pulse, broadcast to every row of that pulse (NaN if the pulse has no
  active sample).
* ``kinetic_analyzer.get_pre_pulse_currents`` — the pre-interruption current
  (amps) and voltage: the sample immediately before each pulse's first rest
  sample.
"""
import numpy as np
import pandas as pd

from analysis.regression_analyzer import compute_V0_t0
from analysis.kinetic_analyzer import get_pre_pulse_currents


def _phase():
    # pulse 1: active(10,10) then rest(0,0); pulse 2: active(5,5,5) then rest(0,0);
    # pulse 3: all rest (no active -> NaN V0/t0, NaN pre-pulse current)
    return pd.DataFrame({
        "t/s":   [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
        "I/mA":  [10, 10, 0, 0, 5, 5, 5, 0, 0, 0, 0],
        "E/V":   [3.00, 3.05, 3.08, 3.06, 3.20, 3.25, 3.30, 3.28, 3.26, 3.10, 3.09],
        "pulse_number": [1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3],
    })


def test_compute_V0_t0_last_active_broadcast():
    out = compute_V0_t0(_phase())
    # pulse 1 -> last active at idx 1 (3.05 V, t=1); pulse 2 -> idx 6 (3.30 V, t=6)
    assert out.loc[out["pulse_number"] == 1, "V0"].eq(3.05).all()
    assert out.loc[out["pulse_number"] == 1, "t0"].eq(1).all()
    assert out.loc[out["pulse_number"] == 2, "V0"].eq(3.30).all()
    assert out.loc[out["pulse_number"] == 2, "t0"].eq(6).all()
    # pulse 3 has no active sample -> NaN
    assert out.loc[out["pulse_number"] == 3, "V0"].isna().all()
    assert out.loc[out["pulse_number"] == 3, "t0"].isna().all()


def test_compute_V0_t0_empty():
    empty = pd.DataFrame({"t/s": [], "I/mA": [], "E/V": [], "pulse_number": []})
    out = compute_V0_t0(empty)
    assert list(out["V0"]) == [] and list(out["t0"]) == []


def test_get_pre_pulse_currents_amps_and_voltage():
    cur, volt = get_pre_pulse_currents(_phase(), [1, 2])
    # pulse 1: sample before first rest (idx 1) -> 10 mA = 0.010 A, 3.05 V
    # pulse 2: sample before first rest (idx 6) ->  5 mA = 0.005 A, 3.30 V
    assert np.allclose(cur, [0.010, 0.005])
    assert np.allclose(volt, [3.05, 3.30])


def test_get_pre_pulse_currents_no_rest_or_no_predecessor():
    # pulse 3 is all rest with a sample before it (idx 8) -> uses that; but a pulse
    # that doesn't exist, and a leading-rest pulse with no predecessor, give NaN.
    df = pd.DataFrame({
        "t/s":   [0, 1, 2],
        "I/mA":  [0, 0, 5],       # starts with rest: pulse 9's first rest is idx 0 -> no predecessor
        "E/V":   [3.0, 3.0, 3.1],
        "pulse_number": [9, 9, 7],
    })
    cur, volt = get_pre_pulse_currents(df, [9, 7, 42])
    assert np.isnan(cur[0]) and np.isnan(volt[0])   # pulse 9: first rest at idx 0, no predecessor
    assert np.isnan(cur[1]) and np.isnan(volt[1])   # pulse 7: active only, no rest
    assert np.isnan(cur[2]) and np.isnan(volt[2])   # pulse 42: absent
