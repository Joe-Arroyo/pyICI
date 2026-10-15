#!/usr/bin/env python3
"""
ICI Battery Analysis - Regression Analyzer Module 
R² Regression Analysis with Phase Classification
Converted from cell4_regression.py

CRITICAL DEPENDENCY: Requires phase classification (cycle_phase column)
This module includes classify_charge_discharge() to ensure proper pulse separation.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import numpy as np
import pandas as pd
from collections import namedtuple

# Single source of truth for phase classification (F1): the canonical
# classify_charge_discharge lives in analysis.phase_classifier. It is imported
# (and thereby re-exported) here so existing callers that do
# `from analysis.regression_analyzer import classify_charge_discharge`
# keep working, now against the one shared implementation.
from analysis.phase_classifier import classify_charge_discharge, MAX_REST_DURATION

# =============================================================================
# CONFIGURATION
# =============================================================================

# Regression parameters
DEFAULT_R1_START = 2   # R1S - Short regression window start (0-based, legacy)
DEFAULT_R1_LENGTH = 10  # R1L - Long regression window length (legacy)
# MAX_REST_DURATION imported from phase_classifier above (single source of truth)
ZERO_THRESHOLD = 1e-5

# Regression window (F11). The fit window is specified as a *mode* plus two
# bounds and resolved per pulse to 0-based sample indices by resolve_window().
#   - "index" bounds are 1-based and INCLUSIVE (user-friendly: point 1, 2, 3, …)
#   - "time" bounds are seconds from the first rest sample
# The analysis never branches on the mode beyond resolve_window; everything
# downstream works in indices, exactly as before.
DEFAULT_WINDOW_MODE = "index"   # "index" | "time"
DEFAULT_INDEX_START = 2         # 1-based, inclusive
DEFAULT_INDEX_END = 10          # 1-based, inclusive
DEFAULT_TIME_START = 0.1        # seconds
DEFAULT_TIME_END = 1.0          # seconds
MIN_WINDOW_POINTS = 3           # < 3 pts -> NaN (s2 = Σr²/(n-2) is undefined at n=2)

# =============================================================================
# GLOBAL VARIABLES
# =============================================================================

# Storage for regression results
regression_results = {'Charge': [], 'Discharge': []}
saved_reg_params = {}

# =============================================================================
# PHASE CLASSIFICATION  (single source of truth — see import at top of module)
# =============================================================================
# classify_charge_discharge is imported from analysis.phase_classifier (F1: one
# implementation, imported everywhere). It remains available as
# regression_analyzer.classify_charge_discharge for existing callers.

# =============================================================================
# WINDOW RESOLUTION (F11) — single source of truth for time<->index windows
# =============================================================================

def time_to_indices(rest_data, start_time, end_time):
    """Convert a time window to a 0-based (r1_start, r1_length) sample window.

    Times are seconds relative to the first rest sample. Each endpoint snaps to
    the nearest sample (the historical pyICI behaviour); the END sample is
    INCLUDED in the window. The window is clamped to the available span. No
    minimum size is forced here — a window that ends up with fewer than
    MIN_WINDOW_POINTS points is left as-is and returns NaN from
    compute_single_pulse_regression (whose >= 3-point guard handles it).

    Parameters
    ----------
    rest_data : pandas.DataFrame
        The rest-period samples of one pulse (must have a ``t/s`` column).
    start_time, end_time : float
        Window bounds in seconds, relative to the first rest sample.

    Returns
    -------
    tuple of int
        ``(r1_start, r1_length)`` — 0-based start index and point count, as
        consumed by ``compute_single_pulse_regression``. ``(0, 0)`` for empty
        data.
    """
    n = len(rest_data)
    if n == 0:
        return 0, 0
    t_rel = rest_data['t/s'].values - rest_data['t/s'].values[0]
    max_time = t_rel[-1]
    start_time = max(0.0, min(start_time, max_time))
    end_time = max(start_time, min(end_time, max_time))
    start_idx = int(np.argmin(np.abs(t_rel - start_time)))
    end_idx = int(np.argmin(np.abs(t_rel - end_time)))
    r1_start = start_idx
    r1_length = (end_idx - start_idx) + 1   # inclusive of the end sample
    return r1_start, r1_length


def resolve_window(rest_data, mode=DEFAULT_WINDOW_MODE, start=None, end=None):
    """Resolve a (mode, start, end) window spec to a 0-based (r1_start, r1_length).

    This is the one place that understands "time" vs "index"; everything
    downstream works purely in sample indices.

    Parameters
    ----------
    rest_data : pandas.DataFrame
        The rest-period samples of one pulse (needs ``t/s`` for time mode).
    mode : {'index', 'time'}
        'index' — ``start``/``end`` are 1-based, INCLUSIVE sample positions.
        'time'  — ``start``/``end`` are seconds from the first rest sample.
    start, end : number, optional
        Window bounds in the unit implied by ``mode``. When ``None`` they fall
        back to the module ``DEFAULT_*`` constants for that mode.

    Returns
    -------
    tuple of int
        ``(r1_start, r1_length)`` for ``compute_single_pulse_regression``.
    """
    if mode == "time":
        start = DEFAULT_TIME_START if start is None else start
        end = DEFAULT_TIME_END if end is None else end
        return time_to_indices(rest_data, start, end)
    # index mode (default): 1-based inclusive -> 0-based start + length
    start = DEFAULT_INDEX_START if start is None else int(start)
    end = DEFAULT_INDEX_END if end is None else int(end)
    r1_start = max(0, start - 1)
    r1_length = max(0, end - start + 1)
    return r1_start, r1_length


# =============================================================================
# PULSE PROCESSING FUNCTIONS
# =============================================================================

def assign_valid_pulses(df, max_rest=MAX_REST_DURATION):
    """Assign pulse numbers to valid pulses based on rest duration.

    A pulse is a run of active-current samples (``I != 0``) immediately followed
    by a run of rest samples (``I == 0``); both runs share the pulse number,
    provided the rest run's duration is ``<= max_rest``. Leading rest samples, a
    trailing active run with no following rest, and active+rest blocks whose rest
    is too long are left as 0 (unassigned). A rest run that reaches the end of the
    data labels only its active part (preserving the original behaviour).

    Vectorized over contiguous current runs: the previous element-by-element
    ``df['...'].iloc[i]`` walk went through pandas scalar indexing once per row and
    was by far the pipeline's dominant cost. Output is byte-for-byte unchanged.
    """
    df = df.copy()
    n = len(df)
    pulse_number = np.zeros(n, dtype=int)
    if n == 0:
        df['pulse_number'] = pulse_number
        return df

    cur = df['I/mA'].to_numpy()
    t = df['t/s'].to_numpy()
    active = cur != 0

    # Maximal runs of constant active/rest state; adjacent runs always alternate.
    # Run k spans [starts[k], ends[k]).
    changes = np.flatnonzero(active[1:] != active[:-1]) + 1
    starts = np.concatenate(([0], changes))
    ends = np.concatenate((changes, [n]))

    pulse_counter = 0
    for k in range(len(starts)):
        if not active[starts[k]]:
            continue                                   # a rest run on its own
        if k + 1 >= len(starts):
            continue                                   # trailing active, no rest -> dropped
        a_start, a_end = starts[k], ends[k]
        r_start, r_end = starts[k + 1], ends[k + 1]    # the following rest run
        if t[r_end - 1] - t[r_start] <= max_rest:
            pulse_counter += 1
            # A rest run reaching the end labels only its active part (matches the
            # original's `if i < n` guard); otherwise active + rest together.
            end_idx = a_end if r_end == n else r_end
            pulse_number[a_start:end_idx] = pulse_counter

    df['pulse_number'] = pulse_number
    return df

def compute_V0_t0(df):
    """Compute V0 and t0 for each pulse.

    V0 / t0 are the voltage / time of the LAST active-current sample (``I != 0``)
    of each pulse — the point just before the interruption. Every row of a pulse
    carries its pulse's V0/t0; a pulse with no active sample gets NaN.

    Vectorized: one pass finds each pulse's last active sample, then a mapped
    broadcast fills the columns — instead of re-filtering the frame once per
    pulse. Output is unchanged.
    """
    df = df.copy()
    if len(df) == 0:
        df['V0'] = np.array([], dtype=float)
        df['t0'] = np.array([], dtype=float)
        return df

    pulse = df['pulse_number'].to_numpy()
    cur = df['I/mA'].to_numpy()
    volt = df['E/V'].to_numpy()
    tsec = df['t/s'].to_numpy()

    v0_map, t0_map = {}, {}
    active_idx = np.flatnonzero(cur != 0)
    if active_idx.size:
        # Last active sample per pulse: scan active positions in reverse and keep
        # the first seen for each pulse (= the last in forward order).
        rev = active_idx[::-1]
        uniq, first_in_rev = np.unique(pulse[rev], return_index=True)
        last_idx = rev[first_in_rev]
        v0_map = {int(p): volt[i] for p, i in zip(uniq, last_idx)}
        t0_map = {int(p): tsec[i] for p, i in zip(uniq, last_idx)}

    df['V0'] = df['pulse_number'].map(v0_map)
    df['t0'] = df['pulse_number'].map(t0_map)
    return df

def get_V0(data, pulse_number):
    """Get V0 value for a specific pulse."""
    pulse_data = data[data['pulse_number'] == pulse_number]
    if len(pulse_data) > 0 and 'V0' in pulse_data.columns:
        v0_values = pulse_data['V0'].dropna()
        if len(v0_values) > 0:
            return v0_values.iloc[0]
    return np.nan

# =============================================================================
# REGRESSION ANALYSIS FUNCTIONS
# =============================================================================

def r2_score(y_true, y_pred):
    """Calculate R² score."""
    if len(y_true) != len(y_pred) or len(y_true) == 0:
        return np.nan
    ss_res = np.sum((y_true - y_pred) ** 2)
    ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
    return 1 - (ss_res / ss_tot) if ss_tot != 0 else np.nan

def compute_single_pulse_regression(rest_data, r1_start, r1_length):
    """
    Compute regression for a single pulse rest period.
    Uses sqrt(time) transformation for regression.
    """
    try:
        if len(rest_data) < r1_start + r1_length:
            return {'r2': np.nan, 'slope': np.nan, 'intercept': np.nan, 'cov': None}
        
        # Get sqrt(time) and ΔV data
        times = np.sqrt(rest_data['t/s'].values - rest_data['t/s'].values[0])
        voltages = rest_data['ΔV'].values
        
        # Select regression window
        X = times[r1_start:r1_start + r1_length].reshape(-1, 1)
        y = voltages[r1_start:r1_start + r1_length]

        # Need >= 3 points for a meaningful fit: s2 = Σr²/(n-2) divides by zero
        # at n=2, and a degenerate (zero-variance) x-window blows up the slope /
        # covariance. Either way the fit and its error bars are meaningless, so
        # return NaN rather than inf/nan.
        if len(y) < 3 or np.ptp(X) == 0:
            return {'r2': np.nan, 'slope': np.nan, 'intercept': np.nan, 'cov': None}

        # Linear regression
        X_mean = np.mean(X)
        y_mean = np.mean(y)
        slope = np.sum((X.flatten() - X_mean) * (y - y_mean)) / np.sum((X.flatten() - X_mean) ** 2)
        intercept = y_mean - slope * X_mean
        
        # Predictions and R²
        y_pred = slope * X.flatten() + intercept
        r2 = r2_score(y, y_pred)
        
        # Covariance matrix (for error propagation)
        residuals = y - y_pred
        s2 = np.sum(residuals ** 2) / (len(y) - 2)  # variance of residuals
        X_centered = X.flatten() - X_mean
        var_slope = s2 / np.sum(X_centered ** 2)
        var_intercept = s2 * (1/len(X) + X_mean**2 / np.sum(X_centered ** 2))
        cov_slope_intercept = -s2 * X_mean / np.sum(X_centered ** 2)
        
        cov_matrix = np.array([
            [var_slope, cov_slope_intercept],
            [cov_slope_intercept, var_intercept]
        ])
        
        return {
            'r2': r2,
            'slope': slope,
            'intercept': intercept,
            'cov': cov_matrix
        }
        
    except Exception:
        return {'r2': np.nan, 'slope': np.nan, 'intercept': np.nan, 'cov': None}

def compute_r2_for_pulse(data, pulse_num, r1_start, r1_length):
    """Compute R² for a single pulse."""
    pulse_data = data[data['pulse_number'] == pulse_num]
    rest_data = pulse_data[pulse_data['I/mA'] == 0].copy()
    
    if len(rest_data) < r1_start + r1_length:
        return {'pulse': pulse_num, 'r2': np.nan, 'slope': np.nan}
    
    # Get V0 and compute ΔV
    V0 = get_V0(data, pulse_num)
    if np.isnan(V0):
        return {'pulse': pulse_num, 'r2': np.nan, 'slope': np.nan}
    
    rest_data['ΔV'] = rest_data['E/V'] - V0
    
    # Compute regression
    result = compute_single_pulse_regression(rest_data, r1_start, r1_length)
    
    return {
        'pulse': pulse_num,
        'r2': result['r2'],
        'slope': result['slope'],
        'intercept': result['intercept'],
        'V0': V0
    }

def compute_r2_all_pulses(data, pulse_numbers, r1_start, r1_length):
    """Compute R² for all pulses in the data."""
    results = []
    
    for pulse_num in pulse_numbers:
        if pulse_num == 0:
            continue
        
        result = compute_r2_for_pulse(data, pulse_num, r1_start, r1_length)
        
        # Determine phase
        pulse_data = data[data['pulse_number'] == pulse_num]
        avg_current = pulse_data['I/mA'].mean()
        result['phase'] = 'charge' if avg_current > 0 else 'discharge'
        
        results.append(result)
    
    return results

# =============================================================================
# CYCLE LOADING AND PROCESSING
# =============================================================================

CycleRegression = namedtuple(
    "CycleRegression",
    ["cycle", "charge_data", "charge_pulses", "discharge_data", "discharge_pulses"],
)


def load_cycle_for_regression(df_raw, cycle_num):
    """Prepare one cycle's charge/discharge pulses for regression.

    Returns a CycleRegression with the per-phase pulse DataFrames (each carrying
    pulse_number, V0 and t0) and their valid pulse-number lists, or None if the
    cycle has no data or no valid pulses.
    """
    if df_raw is None:
        return None

    cycle_df = df_raw[df_raw['cycle'] == cycle_num].copy()
    if len(cycle_df) == 0:
        return None

    if 'cycle_phase' not in cycle_df.columns:
        cycle_df['cycle_phase'] = classify_charge_discharge(cycle_df)

    charge_df = cycle_df[cycle_df['cycle_phase'] == 'charge'].copy()
    discharge_df = cycle_df[cycle_df['cycle_phase'] == 'discharge'].copy()

    if len(charge_df) > 0:
        charge_data = assign_valid_pulses(charge_df, MAX_REST_DURATION)
        charge_pulses = [p for p in charge_data['pulse_number'].unique() if p > 0]
        if charge_pulses:
            charge_data = compute_V0_t0(charge_data)
    else:
        charge_data = pd.DataFrame()
        charge_pulses = []

    if len(discharge_df) > 0:
        discharge_data = assign_valid_pulses(discharge_df, MAX_REST_DURATION)
        discharge_pulses = [p for p in discharge_data['pulse_number'].unique() if p > 0]
        if discharge_pulses:
            discharge_data = compute_V0_t0(discharge_data)
    else:
        discharge_data = pd.DataFrame()
        discharge_pulses = []

    if not charge_pulses and not discharge_pulses:
        return None

    return CycleRegression(
        cycle=cycle_num,
        charge_data=charge_data,
        charge_pulses=charge_pulses,
        discharge_data=discharge_data,
        discharge_pulses=discharge_pulses,
    )

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def parse_range_input(range_str, available_items):
    """Parse range input like '1-5' or '1,3,7' into list"""
    try:
        items = []
        
        if '-' in range_str:
            start, end = map(int, range_str.split('-'))
            items = list(range(start, end + 1))
        elif ',' in range_str:
            items = [int(x.strip()) for x in range_str.split(',')]
        else:
            items = [int(range_str)]
        
        # Filter to available items
        valid_items = [item for item in items if item in available_items]
        return valid_items
        
    except (ValueError, IndexError):
        return []

