#!/usr/bin/env python3
"""
ICI Battery Analysis - Data Loader Module
Multi-cycle ICI data loading and processing with smart auto-detection.
Supports single-cycle (3 columns) and multi-cycle (4 columns) formats.
Pure analysis layer: run_data_analysis takes inputs as arguments and returns
a DataLoadResult (no module-level data globals).
"""

import os
import pandas as pd
import numpy as np
from collections import namedtuple

from analysis.phase_classifier import MAX_REST_DURATION  # single source of truth

# =============================================================================
# CONFIGURATION (defaults; the GUI passes its own values as arguments)
# =============================================================================

CURRENT_THRESHOLD = 1.0   # mA

# Cycle identification for files WITHOUT a cycle-number column:
#   'auto' -> detect cycles automatically from the current signal
#   'file' -> treat the whole file as a single cycle
CYCLE_DETECTION_MODE = 'auto'

# Standard column names (internal format after processing)
STANDARD_COLUMNS = ['cycle', 't/s', 'E/V', 'I/mA']

# =============================================================================
# RESULT TYPE
# =============================================================================

DataLoadResult = namedtuple(
    "DataLoadResult",
    ["df_raw", "plot_data", "ici_starts", "cycle_list", "data_format"],
)

# =============================================================================
# DATA LOADING HELPER FUNCTIONS
# =============================================================================

def inspect_data_file(file_path):
    """Inspect the data file to determine its delimiter.

    Returns (delimiter, first_lines) or (None, []) on failure.
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [f.readline().strip() for _ in range(10)]

        first_data_line = lines[1] if len(lines) > 1 else lines[0]
        if '\t' in first_data_line:
            delimiter = '\t'
        elif ',' in first_data_line:
            delimiter = ','
        else:
            delimiter = None

        return delimiter, lines

    except Exception:
        return None, []

def _is_headerless(file_path, delimiter):
    """Return True when the file's first row is entirely numeric, i.e. there is
    no header row (the first line is already data)."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            first = f.readline().strip()
    except Exception:
        return False
    fields = [x for x in first.split(delimiter) if x.strip() != '']
    if not fields:
        return False
    for x in fields:
        try:
            float(x)
        except ValueError:
            return False   # a non-numeric token -> this row is a header
    return True            # all tokens numeric -> no header row

def _read_table(file_path, delimiter):
    """Read a delimited file, auto-handling a missing header row.

    If the first row is all-numeric the file is treated as header-less: every
    row is kept as data and generic column names (col1, col2, ...) are assigned
    so nothing is lost to being mistaken for a header."""
    if _is_headerless(file_path, delimiter):
        df = pd.read_csv(file_path, delimiter=delimiter, encoding='utf-8', header=None)
        df.columns = [f'col{i + 1}' for i in range(df.shape[1])]
    else:
        df = pd.read_csv(file_path, delimiter=delimiter, encoding='utf-8')
    return df

def load_data_flexible(file_path):
    """Load data with flexible format detection. Returns a DataFrame or None."""
    delimiter, sample_lines = inspect_data_file(file_path)

    if delimiter is None:
        return None

    try:
        return _read_table(file_path, delimiter)
    except Exception:
        return None

def detect_data_format(df):
    """Detect if data is single-cycle or multi-cycle format based on column count.

    Returns (data_format, cleaned_df) where data_format is
    'single_cycle', 'multi_cycle' or 'unknown'.
    """
    df_clean = df.copy()

    columns_to_drop = []
    for col in df_clean.columns:
        if 'unnamed' in col.lower() or df_clean[col].isna().all():
            columns_to_drop.append(col)

    if columns_to_drop:
        df_clean = df_clean.drop(columns=columns_to_drop)

    num_cols = len(df_clean.columns)

    if num_cols == 3:
        data_format = "single_cycle"
    elif num_cols == 4:
        data_format = "multi_cycle"
    else:
        data_format = "unknown"

    return data_format, df_clean

def standardize_columns_by_position(df, data_format):
    """Standardize column names based on position rather than names.

    Returns the standardized DataFrame, or None if the column count does not
    match the format.
    """
    df_std = df.copy()

    if data_format == "single_cycle":
        if len(df_std.columns) != 3:
            return None

        old_cols = list(df_std.columns)
        new_column_mapping = {
            old_cols[0]: 't/s',
            old_cols[1]: 'E/V',
            old_cols[2]: 'I/mA'
        }
        df_std = df_std.rename(columns=new_column_mapping)
        df_std.insert(0, 'cycle', 1)

    elif data_format == "multi_cycle":
        if len(df_std.columns) != 4:
            return None

        old_cols = list(df_std.columns)
        new_column_mapping = {
            old_cols[0]: 'cycle',
            old_cols[1]: 't/s',
            old_cols[2]: 'E/V',
            old_cols[3]: 'I/mA'
        }
        df_std = df_std.rename(columns=new_column_mapping)

    else:
        return None

    required_cols = STANDARD_COLUMNS
    missing_cols = [col for col in required_cols if col not in df_std.columns]

    if missing_cols:
        return None

    return df_std

def peek_columns(file_path):
    """Return the usable column names of a data file (after dropping unnamed /
    all-NaN columns), or [] on failure. Used by the GUI column-mapping dialog."""
    delimiter, _ = inspect_data_file(file_path)
    if delimiter is None:
        return []
    try:
        df = _read_table(file_path, delimiter)
    except Exception:
        return []
    drop = [c for c in df.columns
            if 'unnamed' in str(c).lower() or df[c].isna().all()]
    if drop:
        df = df.drop(columns=drop)
    return list(df.columns)

def build_df_from_map(df, col_map):
    """Build the standard [cycle, t/s, E/V, I/mA] DataFrame from a manual column
    mapping supplied by the GUI.

    col_map keys: 'time', 'voltage', 'current', 'cycle'. 'cycle' may be None,
    in which case a single cycle is created and cycles are detected downstream
    from the current signal. Any column not referenced is ignored.
    """
    out = pd.DataFrame()
    out['t/s']  = pd.to_numeric(df[col_map['time']],    errors='coerce')
    out['E/V']  = pd.to_numeric(df[col_map['voltage']], errors='coerce')
    out['I/mA'] = pd.to_numeric(df[col_map['current']], errors='coerce')
    if col_map.get('cycle'):
        out.insert(0, 'cycle', pd.to_numeric(df[col_map['cycle']], errors='coerce'))
    else:
        out.insert(0, 'cycle', 1)
    return out[['cycle', 't/s', 'E/V', 'I/mA']]

# =============================================================================
# CORE ANALYSIS FUNCTIONS
# =============================================================================

def detect_cycles_from_current(df, current_threshold=1.0, current_col='I/mA'):
    """Signal-based, start-agnostic cycle detection.

    A full cycle = two half-cycles (one charge + one discharge, in whichever
    order they occur). Current interruptions and CV-taper points sit at/near
    zero, count as 'rest', and are absorbed into the surrounding half-cycle so
    they never create a false boundary.
    """
    current = df[current_col].to_numpy(dtype=float)
    n = len(current)
    if n == 0:
        return np.ones(0, dtype=int)

    phase = np.where(current > current_threshold, 1,
             np.where(current < -current_threshold, -1, 0)).astype(int)

    nz = np.flatnonzero(phase != 0)
    if nz.size == 0:
        # No current above threshold - treat as a single cycle
        return np.ones(n, dtype=int)

    ff = np.zeros(n, dtype=int)
    ff[nz] = nz
    ff = np.maximum.accumulate(ff)
    filled = phase[ff]
    filled[:nz[0]] = phase[nz[0]]

    changed = np.zeros(n, dtype=bool)
    changed[1:] = filled[1:] != filled[:-1]
    half_index = np.cumsum(changed)

    cycles = (half_index // 2) + 1
    return cycles.astype(int)


def detect_and_fix_cycle_structure(df, current_threshold=1.0,
                                   mode='auto', data_format=None):
    """Process cycle structure.

    For 3-column (single-cycle format) files, cycles can be auto-detected from
    the current signal when mode == 'auto'. 4-column files keep their own
    cycle-number column unchanged.
    """
    df_fixed = df.copy()

    if 'cycle' not in df_fixed.columns:
        return df_fixed

    # Remove rows with a NaN cycle number
    df_fixed = df_fixed.dropna(subset=['cycle'])

    if len(df_fixed) == 0:
        return df_fixed

    if data_format == 'single_cycle' and mode == 'auto':
        df_fixed['cycle'] = detect_cycles_from_current(
            df_fixed, current_threshold=current_threshold).astype(int)

    return df_fixed

def find_ici_starts(df, current_threshold=1.0):
    """Find ICI start points (first sample above the current threshold) per cycle.

    Returns {cycle_num: row_index}.
    """
    ici_starts = {}

    if len(df) == 0:
        return ici_starts

    for cycle_num in sorted(df['cycle'].unique()):
        cycle_data = df[df['cycle'] == cycle_num]

        charge_start_idx = None
        for idx, row in cycle_data.iterrows():
            if row['I/mA'] > current_threshold:
                charge_start_idx = idx
                break

        if charge_start_idx is not None:
            ici_starts[cycle_num] = charge_start_idx

    return ici_starts

def downsample_data(data, max_points=10000, target_points=5000):
    """Keep all data points - no downsampling for complete analysis."""
    return data

# =============================================================================
# MAIN EXECUTION FUNCTION
# =============================================================================

def run_data_analysis(folder_path, txt_file_name, *,
                      current_threshold=CURRENT_THRESHOLD,
                      cycle_detection_mode=CYCLE_DETECTION_MODE,
                      column_map=None):
    """Load and process an ICI data file into the standard
    [cycle, t/s, E/V, I/mA] form.

    Parameters
    ----------
    folder_path, txt_file_name : location of the data file.
    current_threshold : mA threshold for signal-based cycle detection / ICI starts.
    cycle_detection_mode : 'auto' or 'file' (only affects 3-column files).
    column_map : optional dict {'time','voltage','current','cycle'} from the GUI
        mapping dialog for files with more than 3 columns ('cycle' may be None).

    Returns
    -------
    DataLoadResult(df_raw, plot_data, ici_starts, cycle_list, data_format), or
    None on failure.
    """
    if not folder_path or not txt_file_name:
        return None

    try:
        txt_path = os.path.join(folder_path, txt_file_name)
        if not os.path.exists(txt_path):
            return None

        df_loaded = load_data_flexible(txt_path)
        if df_loaded is None:
            return None

        if column_map is not None:
            _, df_cleaned = detect_data_format(df_loaded)   # reuse the cleaning step
            df_raw = build_df_from_map(df_cleaned, column_map)
            data_format = 'multi_cycle' if column_map.get('cycle') else 'single_cycle'
        else:
            data_format, df_cleaned = detect_data_format(df_loaded)
            if data_format == "unknown":
                return None
            df_raw = standardize_columns_by_position(df_cleaned, data_format)

        if df_raw is None:
            return None

        df_raw = detect_and_fix_cycle_structure(
            df_raw, current_threshold,
            mode=cycle_detection_mode, data_format=data_format)
        if len(df_raw) == 0:
            return None

        ici_starts = find_ici_starts(df_raw, current_threshold)

        cycle_list = sorted(df_raw['cycle'].unique())
        if len(cycle_list) == 0:
            return None

        plot_data = downsample_data(df_raw, max_points=10000, target_points=5000)

        try:
            cycle_list = [int(c) for c in cycle_list if not pd.isna(c)]
        except Exception:
            pass

        return DataLoadResult(df_raw, plot_data, ici_starts, cycle_list, data_format)

    except Exception:
        return None