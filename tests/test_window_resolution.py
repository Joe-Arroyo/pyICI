"""Tests for the F11 window resolver (time<->index) — the single source of truth
that both the Regression display and the batch export use to turn a (mode, start,
end) window spec into a 0-based (r1_start, r1_length) for the regression."""
import numpy as np
import pandas as pd

from analysis.regression_analyzer import (
    resolve_window, time_to_indices,
    DEFAULT_INDEX_START, DEFAULT_INDEX_END,
    DEFAULT_TIME_START, DEFAULT_TIME_END,
)


def _rest(times):
    return pd.DataFrame({"t/s": np.asarray(times, dtype=float)})


# --------------------------------------------------------------------------- #
# index mode — 1-based INCLUSIVE bounds -> 0-based (start, length)
# --------------------------------------------------------------------------- #
def test_index_default_2_to_10():
    rd = _rest(np.arange(20) * 0.1)
    # 1-based 2..10 inclusive -> 0-based indices 1..9 -> start=1, 9 points
    assert resolve_window(rd, "index", 2, 10) == (1, 9)


def test_index_defaults_fallback_to_constants():
    rd = _rest(np.arange(20) * 0.1)
    expected = (DEFAULT_INDEX_START - 1, DEFAULT_INDEX_END - DEFAULT_INDEX_START + 1)
    assert resolve_window(rd) == expected == (1, 9)


def test_index_first_ten_points():
    rd = _rest(np.arange(20) * 0.1)
    assert resolve_window(rd, "index", 1, 10) == (0, 10)


def test_index_legacy_equivalent():
    # 1-based 3..12 reproduces the historical 0-based [2:12] (start=2, length=10)
    rd = _rest(np.arange(20) * 0.1)
    assert resolve_window(rd, "index", 3, 12) == (2, 10)


# --------------------------------------------------------------------------- #
# time mode — nearest-sample snap, end INCLUSIVE, clamped to span
# --------------------------------------------------------------------------- #
def test_time_window_inclusive():
    rd = _rest(np.round(np.arange(0, 1.01, 0.1), 2))   # 0.0 .. 1.0, 11 points
    # 0.1 s -> idx 1, 1.0 s -> idx 10, inclusive -> length 10
    assert time_to_indices(rd, 0.1, 1.0) == (1, 10)
    assert resolve_window(rd, "time", 0.1, 1.0) == (1, 10)


def test_time_defaults_fallback_to_constants():
    rd = _rest(np.round(np.arange(0, 1.01, 0.1), 2))
    assert resolve_window(rd, "time") == time_to_indices(
        rd, DEFAULT_TIME_START, DEFAULT_TIME_END)


def test_time_clamps_to_available_span():
    rd = _rest(np.round(np.arange(0, 0.51, 0.1), 2))   # max 0.5 s (6 points)
    # end 1.0 s clamped to 0.5 s (idx 5); start 0.1 s -> idx 1; inclusive -> 5
    assert time_to_indices(rd, 0.1, 1.0) == (1, 5)


def test_empty_rest_returns_zero():
    assert time_to_indices(_rest([]), 0.1, 1.0) == (0, 0)
