"""Known-answer tests for ``assign_valid_pulses`` (the ICI pulse segmenter).

A pulse = a run of active-current samples (I != 0) immediately followed by a run
of rest samples (I == 0) whose duration is <= MAX_REST_DURATION; both runs share
the pulse number. These pin the exact labelling of the tricky boundary cases so
the (vectorized) implementation can't silently drift.
"""
import numpy as np
import pandas as pd

from analysis.regression_analyzer import assign_valid_pulses, MAX_REST_DURATION


def _df(currents, dt=1.0):
    currents = np.asarray(currents, dtype=float)
    return pd.DataFrame({"t/s": np.arange(len(currents)) * dt, "I/mA": currents})


def _pulses(currents, dt=1.0):
    return assign_valid_pulses(_df(currents, dt))["pulse_number"].tolist()


def test_two_clean_pulses_with_leading_and_trailing_rest():
    # active,active, rest,rest -> pulse 1 ; active,active, rest -> pulse 2
    assert _pulses([0, 0, 5, 5, 0, 0, 3, 3, 0]) == [0, 0, 1, 1, 1, 1, 2, 2, 0]


def test_trailing_active_run_without_rest_is_dropped():
    # the final active run has no following rest -> left as 0
    assert _pulses([0, 5, 5, 0, 5, 5]) == [0, 1, 1, 1, 0, 0]


def test_rest_run_reaching_end_labels_only_the_active_part():
    # rest extends to the end of the data: active labelled, trailing rest not
    assert _pulses([5, 5, 0, 0, 0]) == [1, 1, 0, 0, 0]


def test_rest_longer_than_max_is_not_a_pulse():
    # first rest spans 4*500 = 2000 s > 1800 s -> that block stays 0; the next
    # active+rest (within the limit) becomes pulse 1
    assert MAX_REST_DURATION == 1800
    assert _pulses([5, 5, 0, 0, 0, 0, 0, 5, 5, 0], dt=500.0) == [0, 0, 0, 0, 0, 0, 0, 1, 1, 0]


def test_degenerate_inputs_have_no_pulses():
    assert _pulses([]) == []
    assert _pulses([0]) == [0]
    assert _pulses([5]) == [0]            # single active, no rest
    assert _pulses([0, 0, 0]) == [0, 0, 0]
    assert _pulses([1, 2, 3]) == [0, 0, 0]  # all active, no rest
