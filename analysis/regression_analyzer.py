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

# ---- auto fit-window estimation (opt-in "Estimate optimal window") ----------
# Defaults for estimate_optimal_window(). The auto window finds the ΔV-vs-√t fit
# window with the smallest fit error AMONG windows that stay in the linear
# (√t-diffusion) region, so it never trades physical validity for a smaller
# error bar. These are presentation/assist defaults; the analysis itself is
# unchanged (same R = -intercept/I, k = -slope/I, same covariance errors).
AUTO_SKIP_INITIAL = 1     # samples skipped at the start (IR-drop / instantaneous point)
AUTO_MIN_POINTS = 5       # minimum points in a candidate window
AUTO_ADJ_R2_MIN = 0.995   # minimum adjusted R² for a window to count as "linear"
AUTO_EDGE_POINTS = 3      # points at each window end used for the curvature check
AUTO_EDGE_Z_MAX = 3.0     # max edge-curvature z-score before a window is rejected
AUTO_MAX_START = 2        # how far past AUTO_SKIP_INITIAL the window start may move

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
# AUTO FIT-WINDOW ESTIMATION  ("Estimate optimal window")
# =============================================================================

def _edge_curvature_z(residuals, edge_points):
    """Edge-curvature diagnostic for a fit window.

    Returns the larger of the two window-end mean residuals, expressed in units
    of its own standard error. A large value means the data bends systematically
    away from the straight line at one end of the window — i.e. the window has
    reached the non-√t (curved) region. Returns 0.0 for a degenerate window.
    """
    r = np.asarray(residuals, dtype=float)
    k = edge_points
    if len(r) < 2 * k:
        k = max(2, len(r) // 3)
    s = np.std(r, ddof=1)
    if s == 0 or not np.isfinite(s):
        return 0.0
    first = abs(np.mean(r[:k]))
    last = abs(np.mean(r[-k:]))
    return float(max(first, last) / (s / np.sqrt(k)))


def _scan_windows(sqrt_t, dv, start, min_points):
    """Vectorised OLS of ΔV vs √t for every window ``[start : e]`` (e running to
    the end) with at least ``min_points`` points.

    Computed with prefix sums in O(n) for the whole scan, giving results
    numerically identical to :func:`compute_single_pulse_regression` (the single
    canonical fit) — it is only an accelerator for the candidate search, and the
    finally-chosen window is always re-fit through that canonical function.

    Returns arrays aligned to the window end index ``end`` (0-based):
    ``end, n_points, slope, intercept, r2, slope_err, intercept_err, valid``.
    """
    x = sqrt_t[start:]
    y = dv[start:]
    m = len(x)
    n_pts = np.arange(1, m + 1)
    Sx = np.cumsum(x); Sy = np.cumsum(y)
    Sxx = np.cumsum(x * x); Syy = np.cumsum(y * y); Sxy = np.cumsum(x * y)
    with np.errstate(all='ignore'):
        mean_x = Sx / n_pts
        mean_y = Sy / n_pts
        Sxx_c = Sxx - Sx * Sx / n_pts
        Sxy_c = Sxy - Sx * Sy / n_pts
        Syy_c = Syy - Sy * Sy / n_pts
        slope = Sxy_c / Sxx_c
        intercept = mean_y - slope * mean_x
        ss_res = np.clip(Syy_c - Sxy_c * Sxy_c / Sxx_c, 0.0, None)
        r2 = 1.0 - ss_res / Syy_c
        s2 = ss_res / (n_pts - 2)
        slope_err = np.sqrt(s2 / Sxx_c)
        intercept_err = np.sqrt(s2 * (1.0 / n_pts + mean_x * mean_x / Sxx_c))
    end = start + np.arange(m)
    valid = ((n_pts >= min_points) & (Sxx_c > 0)
             & np.isfinite(r2) & np.isfinite(slope_err) & np.isfinite(intercept_err))
    return end, n_pts, slope, intercept, r2, slope_err, intercept_err, valid


def estimate_optimal_window(rest_data, *, skip_initial=AUTO_SKIP_INITIAL,
                            min_points=AUTO_MIN_POINTS, adj_r2_min=AUTO_ADJ_R2_MIN,
                            edge_points=AUTO_EDGE_POINTS, edge_z_max=AUTO_EDGE_Z_MAX,
                            max_start=AUTO_MAX_START):
    """Suggest the ΔV-vs-√t fit window with the smallest fit error among windows
    that stay in the linear (√t-diffusion) region.

    ``rest_data`` is one pulse's rest period, carrying ``'t/s'`` and ``'ΔV'``
    columns (as prepared for :func:`compute_single_pulse_regression`). The search:

    1. skips the first ``skip_initial`` samples (the IR-drop / instantaneous point),
    2. keeps only windows with at least ``min_points`` points, an adjusted R² of
       at least ``adj_r2_min``, and no edge curvature (``edge_z <= edge_z_max``),
    3. returns the qualifying window with the smallest combined relative standard
       error on slope and intercept.

    If no window qualifies it returns the most-linear fallback window with a
    non-empty ``flags`` list, so a weak pulse is surfaced rather than silently
    mis-fit. The science is unchanged: this only *chooses* a window; R and k are
    still computed by the usual pipeline from the returned window.

    Parameters mirror the ``AUTO_*`` module defaults.

    Returns ``None`` if the rest is too short, otherwise a dict with:
        ``r1_start``, ``r1_length`` : 0-based window for compute_single_pulse_regression
        ``index_start``, ``index_end`` : 1-based inclusive index window (GUI index mode)
        ``time_start``, ``time_end`` : window bounds, seconds from the first rest sample
        ``n_points``, ``r2``, ``adj_r2``, ``slope``, ``intercept``
        ``k_relerr``, ``R_relerr`` : relative std error on slope (k) and intercept (R)
        ``edge_z`` : edge-curvature z-score of the chosen window
        ``flags`` : list of QC flags ('too_few_points', 'poor_fit',
            'edge_curvature', 'low_confidence'); empty when every gate passed.

    Note: the physical QC flags that need the pulse current (negative R/k —
    'non_physical' — and a near-zero current step — 'degenerate_dI') are added by
    the caller, which knows the current; this function reports only fit-based flags.
    """
    if rest_data is None or len(rest_data) < skip_initial + min_points:
        return None
    t = rest_data['t/s'].values.astype(float)
    sqrt_t = np.sqrt(t - t[0])
    dv = rest_data['ΔV'].values.astype(float)
    n = len(dv)

    def _build(start, end, flags):
        length = end - start + 1
        # Re-fit the chosen window through the single canonical implementation.
        fit = compute_single_pulse_regression(rest_data, start, length)
        cov = fit.get('cov')
        slope, intercept, r2 = fit['slope'], fit['intercept'], fit['r2']
        if cov is None:
            return None
        se_slope = float(np.sqrt(cov[0, 0]))
        se_intercept = float(np.sqrt(cov[1, 1]))
        resid = dv[start:end + 1] - (slope * sqrt_t[start:end + 1] + intercept)
        adj = 1.0 - (1.0 - r2) * (length - 1) / (length - 2) if length > 2 else float('nan')
        return {
            'r1_start': int(start), 'r1_length': int(length),
            'index_start': int(start) + 1, 'index_end': int(end) + 1,
            'time_start': float(sqrt_t[start] ** 2), 'time_end': float(sqrt_t[end] ** 2),
            'n_points': int(length), 'r2': float(r2), 'adj_r2': float(adj),
            'slope': float(slope), 'intercept': float(intercept),
            'k_relerr': float(se_slope / abs(slope)) if slope else float('nan'),
            'R_relerr': float(se_intercept / abs(intercept)) if intercept else float('nan'),
            'edge_z': _edge_curvature_z(resid, edge_points),
            'flags': list(flags),
        }

    candidates = []      # (combined_rel_err, start, end) passing adj_r2 + min_points
    fallback = None      # (adj_r2, start, end) — most-linear window seen
    start_hi = min(skip_initial + max_start, n - min_points)
    for start in range(skip_initial, start_hi + 1):
        end, n_pts, slope, intercept, r2, se_sl, se_in, valid = _scan_windows(
            sqrt_t, dv, start, min_points)
        for j in np.nonzero(valid)[0]:
            sl, ic = slope[j], intercept[j]
            if not (np.isfinite(sl) and sl != 0 and np.isfinite(ic) and ic != 0):
                continue
            length = int(n_pts[j])
            adj = 1.0 - (1.0 - r2[j]) * (length - 1) / (length - 2) if length > 2 else np.nan
            if fallback is None or (np.isfinite(adj) and adj > fallback[0]):
                fallback = (adj, start, int(end[j]))
            if np.isfinite(adj) and adj >= adj_r2_min:
                rel = se_sl[j] / abs(sl) + se_in[j] / abs(ic)
                candidates.append((rel, start, int(end[j]), float(sl), float(ic)))

    # smallest error first; take the first that also passes the edge-curvature gate
    candidates.sort(key=lambda c: c[0])
    for _rel, start, end, sl, ic in candidates:
        resid = dv[start:end + 1] - (sl * sqrt_t[start:end + 1] + ic)
        if _edge_curvature_z(resid, edge_points) <= edge_z_max:
            return _build(start, end, [])

    if fallback is None:
        return None
    adj, start, end = fallback
    flags = ['low_confidence']
    if (end - start + 1) <= min_points:
        flags.append('too_few_points')
    if not (np.isfinite(adj) and adj >= adj_r2_min):
        flags.append('poor_fit')
    rec = _build(start, end, flags)
    if rec is not None and rec['edge_z'] > edge_z_max and 'edge_curvature' not in flags:
        rec['flags'].append('edge_curvature')
    return rec


def pulse_rest_data(data, pulse_num):
    """Return one pulse's rest-period samples with a ``'ΔV' = E - V0`` column,
    ready for :func:`estimate_optimal_window` / :func:`compute_single_pulse_regression`.

    ``data`` is a phase DataFrame carrying ``pulse_number``, ``I/mA``, ``E/V`` and
    a ``V0`` column (as produced by :func:`compute_V0_t0`). Returns ``None`` if the
    pulse has no rest samples or V0 is undefined.
    """
    pulse = data[data['pulse_number'] == pulse_num]
    rest = pulse[pulse['I/mA'] == 0].copy()
    if len(rest) == 0:
        return None
    v0 = get_V0(data, pulse_num)
    if np.isnan(v0):
        return None
    rest['ΔV'] = rest['E/V'] - v0
    return rest


def _window_flags(rest_data, r1_start, r1_length, *, adj_r2_min=AUTO_ADJ_R2_MIN,
                  edge_points=AUTO_EDGE_POINTS, edge_z_max=AUTO_EDGE_Z_MAX,
                  min_points=AUTO_MIN_POINTS):
    """QC flags a *given* window would raise on one pulse (used to check a shared
    window on every pulse in a cycle). Returns a list: 'too_few_points',
    'poor_fit' and/or 'edge_curvature' (empty when the window fits that pulse well).
    """
    if r1_length < min_points or len(rest_data) < r1_start + r1_length:
        return ['too_few_points']
    fit = compute_single_pulse_regression(rest_data, r1_start, r1_length)
    if fit.get('cov') is None or not np.isfinite(fit['r2']):
        return ['poor_fit']
    length = r1_length
    adj = 1.0 - (1.0 - fit['r2']) * (length - 1) / (length - 2) if length > 2 else float('nan')
    sqrt_t = np.sqrt(rest_data['t/s'].values - rest_data['t/s'].values[0])
    dv = rest_data['ΔV'].values
    resid = dv[r1_start:r1_start + length] - (
        fit['slope'] * sqrt_t[r1_start:r1_start + length] + fit['intercept'])
    flags = []
    if not (np.isfinite(adj) and adj >= adj_r2_min):
        flags.append('poor_fit')
    if _edge_curvature_z(resid, edge_points) > edge_z_max:
        flags.append('edge_curvature')
    return flags


def estimate_window_for_pulses(data, pulse_numbers, *, skip_initial=AUTO_SKIP_INITIAL,
                               min_points=AUTO_MIN_POINTS, adj_r2_min=AUTO_ADJ_R2_MIN,
                               edge_points=AUTO_EDGE_POINTS, edge_z_max=AUTO_EDGE_Z_MAX,
                               max_start=AUTO_MAX_START):
    """Suggest ONE fit window shared by several pulses — for the "this cycle" and
    "all cycles" Auto actions.

    Each pulse's own optimal window is found with :func:`estimate_optimal_window`;
    the shared window is the **median time span** of the cleanly-fit pulses, so a
    single odd pulse can't drag it. Because pulses differ in length, the shared
    window is defined in **time** (seconds from each rest's start) and re-mapped to
    indices per pulse. That shared window is then checked on every pulse to report
    which ones it fits poorly.

    Returns ``None`` if no pulse can be fit, else a dict:
        ``time_start``, ``time_end`` : the shared window (seconds)
        ``n_pulses``, ``n_flagged``  : counts
        ``per_pulse`` : list of ``{'pulse', 'flags'}`` for every input pulse
        ``flags`` : overall flags ('low_confidence' when the shared window had to
            be taken from pulses that were themselves flagged).
    """
    pulse_numbers = list(pulse_numbers)
    kw = dict(skip_initial=skip_initial, min_points=min_points, adj_r2_min=adj_r2_min,
              edge_points=edge_points, edge_z_max=edge_z_max, max_start=max_start)
    rests = {}
    clean_spans, all_spans = [], []
    for p in pulse_numbers:
        rest = pulse_rest_data(data, p)
        rests[p] = rest
        if rest is None:
            continue
        o = estimate_optimal_window(rest, **kw)
        if o is None:
            continue
        all_spans.append((o['time_start'], o['time_end']))
        if not o['flags']:
            clean_spans.append((o['time_start'], o['time_end']))

    spans = clean_spans or all_spans
    if not spans:
        return None
    t_start = float(np.median([s for s, _ in spans]))
    t_end = float(np.median([e for _, e in spans]))

    per_pulse, n_flagged = [], 0
    for p in pulse_numbers:
        rest = rests.get(p)
        if rest is None:
            per_pulse.append({'pulse': p, 'flags': ['no_data']}); n_flagged += 1; continue
        r1s, r1l = time_to_indices(rest, t_start, t_end)
        flags = _window_flags(rest, r1s, r1l, adj_r2_min=adj_r2_min,
                              edge_points=edge_points, edge_z_max=edge_z_max,
                              min_points=min_points)
        if flags:
            n_flagged += 1
        per_pulse.append({'pulse': p, 'flags': flags})

    return {
        'time_start': t_start, 'time_end': t_end,
        'n_pulses': len(pulse_numbers), 'n_flagged': n_flagged,
        'per_pulse': per_pulse,
        'flags': [] if clean_spans else ['low_confidence'],
    }

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

