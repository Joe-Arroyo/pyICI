"""Characterization tests against the real example files in data/.

These pin the end-to-end pipeline output (raw file -> R, k) to the values the
current code produces on the shipped datasets, so any accidental change to the
load / classify / pulse / regression / R-k chain is caught by CI. They are NOT
independent known-answer tests (that is what the synthetic tests are for) -- they
lock in *today's* numbers as a regression guard.

If the algorithm is changed on purpose, re-capture the expected values and update
the constants below in the same commit, with a note in the CHANGELOG.

Window: the default index-based regression window (r1s=2, r1l=10), i.e. the batch
path -- see DEVELOPMENT_PLAN.md F11.
"""
import os

import numpy as np
import pytest

from analysis.data_loader import run_data_analysis
from analysis.kinetic_analyzer import compute_R_k_for_cycle

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
TEN_CYCLES = "10 cycles data.txt"
ONE_CYCLE = "1 cycle data.txt"

# Tolerance for the aggregate float characterizations. Loose enough to absorb
# BLAS/platform float noise across the Python 3.9-3.13 CI matrix, tight enough
# that any real algorithmic change (window, formula, V0 definition, ...) trips it.
REL = 1e-4


def _require(fname):
    path = os.path.join(DATA_DIR, fname)
    if not os.path.exists(path):
        pytest.skip(f"example data file not present: {fname}")
    return path


@pytest.fixture(scope="module")
def ten_cycles():
    _require(TEN_CYCLES)
    result = run_data_analysis(DATA_DIR, TEN_CYCLES)
    assert result is not None
    return result


@pytest.fixture(scope="module")
def one_cycle():
    _require(ONE_CYCLE)
    result = run_data_analysis(DATA_DIR, ONE_CYCLE)
    assert result is not None
    return result


# --------------------------------------------------------------------------- #
# 10 cycles data.txt  (multi-cycle file)
# --------------------------------------------------------------------------- #
def test_ten_cycles_load(ten_cycles):
    res = ten_cycles
    assert res.data_format == "multi_cycle"
    assert res.cycle_list == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
    assert res.df_raw.shape == (57695, 4)
    assert list(res.df_raw.columns) == ["cycle", "t/s", "E/V", "I/mA"]


def test_ten_cycles_cycle0_charge(ten_cycles):
    res = compute_R_k_for_cycle(ten_cycles.df_raw, 0, "charge")
    assert res is not None
    assert len(res["pulse_nums"]) == 12
    R = np.asarray(res["R"], float)
    k = np.asarray(res["k"], float)
    r2 = np.asarray(res["r2"], float)
    assert R[0] == pytest.approx(6.052229123, rel=REL)
    assert k[0] == pytest.approx(0.2875722783, rel=REL)
    assert np.nanmean(R) == pytest.approx(4.970390061, rel=REL)
    assert np.nanmean(k) == pytest.approx(0.1270291357, rel=REL)
    assert np.nanmean(r2) == pytest.approx(0.9814368104, rel=REL)


def test_ten_cycles_cycle0_discharge(ten_cycles):
    res = compute_R_k_for_cycle(ten_cycles.df_raw, 0, "discharge")
    assert res is not None
    assert len(res["pulse_nums"]) == 11
    R = np.asarray(res["R"], float)
    k = np.asarray(res["k"], float)
    assert np.nanmean(R) == pytest.approx(5.252563355, rel=REL)
    assert np.nanmean(k) == pytest.approx(0.1745159082, rel=REL)


def test_ten_cycles_last_cycle_charge(ten_cycles):
    res = compute_R_k_for_cycle(ten_cycles.df_raw, 9, "charge")
    assert res is not None
    assert len(res["pulse_nums"]) == 10
    assert np.nanmean(np.asarray(res["R"], float)) == pytest.approx(5.790928647, rel=REL)
    assert np.nanmean(np.asarray(res["k"], float)) == pytest.approx(0.1276479291, rel=REL)


# --------------------------------------------------------------------------- #
# 1 cycle data.txt  (single-cycle, high-resolution file)
# --------------------------------------------------------------------------- #
def test_one_cycle_load(one_cycle):
    res = one_cycle
    assert res.data_format == "single_cycle"
    assert res.cycle_list == [1]
    assert res.df_raw.shape == (429379, 4)
    assert list(res.df_raw.columns) == ["cycle", "t/s", "E/V", "I/mA"]


def test_one_cycle_charge(one_cycle):
    res = compute_R_k_for_cycle(one_cycle.df_raw, 1, "charge")
    assert res is not None
    assert len(res["pulse_nums"]) == 69
    R = np.asarray(res["R"], float)
    assert R[0] == pytest.approx(6.60469031, rel=REL)
    assert np.nanmean(R) == pytest.approx(4.547972216, rel=REL)
    assert np.nanmean(np.asarray(res["r2"], float)) == pytest.approx(0.8211518116, rel=REL)
