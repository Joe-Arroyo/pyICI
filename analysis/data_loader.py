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

# =============================================================================
# CONFIGURATION (defaults; the GUI passes its own values as arguments)
# =============================================================================

MAX_REST_DURATION = 1800  # seconds
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
    """Inspect the data file to understand its structure"""
    print(f"🔍 Inspecting data file: {file_path}")

    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [f.readline().strip() for _ in range(10)]

        print("First 10 lines:")
        for i, line in enumerate(lines):
            if line:
                print(f"  {i+1}: {line}")

        first_data_line = lines[1] if len(lines) > 1 else lines[0]
        if '\t' in first_data_line:
            delimiter = '\t'
            print(f"\n📋 Detected delimiter: TAB")
        elif ',' in first_data_line:
            delimiter = ','
            print(f"\n📋 Detected delimiter: COMMA")
        else:
            delimiter = None
            print(f"\n⚠️ Could not detect delimiter")

        return delimiter, lines

    except Exception as e:
        print(f"❌ Error inspecting file: {e}")
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
        print(f"   ℹ️ No header row detected - using generic column names {list(df.columns)}")
    else:
        df = pd.read_csv(file_path, delimiter=delimiter, encoding='utf-8')
    return df

def load_data_flexible(file_path):
    """Load data with flexible format detection"""
    delimiter, sample_lines = inspect_data_file(file_path)

    if delimiter is None:
        print("❌ Could not determine file format")
        return None

    try:
        print(f"\n📖 Attempting to load data...")
        df = _read_table(file_path, delimiter)
        print(f"✅ Data loaded successfully!")
        print(f"   Shape: {df.shape}")
        print(f"   Original columns: {list(df.columns)}")
        print(f"\n📊 First 5 rows:")
        print(df.head())
        return df
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None

def detect_data_format(df):
    """Detect if data is single-cycle or multi-cycle format based on column count"""
    df_clean = df.copy()

    columns_to_drop = []
    for col in df_clean.columns:
        if 'unnamed' in col.lower() or df_clean[col].isna().all():
            columns_to_drop.append(col)

    if columns_to_drop:
        print(f"🧹 Dropping empty/unnamed columns: {columns_to_drop}")
        df_clean = df_clean.drop(columns=columns_to_drop)

    num_cols = len(df_clean.columns)

    print(f"\n🔍 Data Format Detection:")
    print(f"   Original columns: {len(df.columns)} ({list(df.columns)})")
    print(f"   Clean columns: {num_cols} ({list(df_clean.columns)})")

    if num_cols == 3:
        data_format = "single_cycle"
        print(f"   📊 Detected format: SINGLE CYCLE (3 columns)")
        print(f"   Expected structure: [time/s, voltage, current]")
    elif num_cols == 4:
        data_format = "multi_cycle"
        print(f"   📊 Detected format: MULTI CYCLE (4 columns)")
        print(f"   Expected structure: [cycle, time/s, voltage, current]")
    else:
        data_format = "unknown"
        print(f"   ❌ Unknown format: {num_cols} columns")
        print(f"   Supported formats: 3 columns (single cycle) or 4 columns (multi cycle)")

    return data_format, df_clean

def standardize_columns_by_position(df, data_format):
    """Standardize column names based on position rather than names"""
    df_std = df.copy()

    print(f"\n📋 Standardizing columns by position...")
    print(f"   Format: {data_format}")

    if data_format == "single_cycle":
        if len(df_std.columns) != 3:
            print(f"❌ Expected 3 columns for single cycle, got {len(df_std.columns)}")
            return None

        old_cols = list(df_std.columns)
        new_column_mapping = {
            old_cols[0]: 't/s',
            old_cols[1]: 'E/V',
            old_cols[2]: 'I/mA'
        }
        df_std = df_std.rename(columns=new_column_mapping)
        df_std.insert(0, 'cycle', 1)

        print(f"   ✅ Single cycle conversion:")
        for old, new in new_column_mapping.items():
            print(f"      '{old}' → '{new}'")
        print(f"      Added 'cycle' column = 1")

    elif data_format == "multi_cycle":
        if len(df_std.columns) != 4:
            print(f"❌ Expected 4 columns for multi cycle, got {len(df_std.columns)}")
            return None

        old_cols = list(df_std.columns)
        new_column_mapping = {
            old_cols[0]: 'cycle',
            old_cols[1]: 't/s',
            old_cols[2]: 'E/V',
            old_cols[3]: 'I/mA'
        }
        df_std = df_std.rename(columns=new_column_mapping)

        print(f"   ✅ Multi cycle conversion:")
        for old, new in new_column_mapping.items():
            print(f"      '{old}' → '{new}'")

    else:
        print(f"❌ Cannot standardize unknown format: {data_format}")
        return None

    required_cols = STANDARD_COLUMNS
    missing_cols = [col for col in required_cols if col not in df_std.columns]

    if missing_cols:
        print(f"❌ Missing required columns after standardization: {missing_cols}")
        print(f"Available columns: {list(df_std.columns)}")
        return None

    print(f"✅ Standardization complete. Final columns: {list(df_std.columns)}")
    print(f"\n📊 Data sample after standardization:")
    print(df_std.head())

    return df_std

def peek_columns(file_path):
    """Return the usable column names of a data file (after dropping unnamed /
    all-NaN columns), or [] on failure. Used by the GUI column-mapping dialog."""
    delimiter, _ = inspect_data_file(file_path)
    if delimiter is None:
        return []
    try:
        df = _read_table(file_path, delimiter)
    except Exception as e:
        print(f"❌ peek_columns error: {e}")
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
    print(f"   ✅ Columns mapped -> time:'{col_map['time']}', "
          f"voltage:'{col_map['voltage']}', current:'{col_map['current']}', "
          f"cycle:'{col_map.get('cycle')}'")
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
        print("   ⚠️ No current above threshold - treating as a single cycle")
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

    print(f"\n🔧 Processing cycle structure (mode = '{mode}', format = '{data_format}')...")

    if 'cycle' not in df_fixed.columns:
        print(f"❌ No cycle column found in data")
        return df_fixed

    before_len = len(df_fixed)
    df_fixed = df_fixed.dropna(subset=['cycle'])
    after_len = len(df_fixed)
    if after_len != before_len:
        print(f"🧹 Removed {before_len - after_len} rows with NaN cycle numbers")

    if len(df_fixed) == 0:
        print(f"❌ No valid cycle data found")
        return df_fixed

    if data_format == 'single_cycle' and mode == 'auto':
        print(f"   🤖 No cycle column in file - detecting cycles from current "
              f"(threshold = {current_threshold} mA)")
        df_fixed['cycle'] = detect_cycles_from_current(
            df_fixed, current_threshold=current_threshold).astype(int)
        print(f"   ✅ Detected {df_fixed['cycle'].nunique()} cycle(s) from the signal")
    else:
        print(f"   📄 Using existing cycle labels")

    cycle_nums = sorted(df_fixed['cycle'].unique())
    print(f"Detected cycles: {cycle_nums}")

    if len(cycle_nums) == 1:
        print(f"✅ Single cycle detected - no structure fixes needed")
    else:
        print(f"✅ Multi-cycle data - {len(cycle_nums)} cycles found")

    return df_fixed

def find_ici_starts(df, current_threshold=1.0):
    """Find ICI start points in each cycle"""
    ici_starts = {}

    if len(df) == 0:
        return ici_starts

    print(f"\n🎯 Finding ICI start points (current > {current_threshold} mA)...")

    for cycle_num in sorted(df['cycle'].unique()):
        cycle_data = df[df['cycle'] == cycle_num]

        charge_start_idx = None
        for idx, row in cycle_data.iterrows():
            if row['I/mA'] > current_threshold:
                charge_start_idx = idx
                break

        if charge_start_idx is not None:
            ici_starts[cycle_num] = charge_start_idx
            print(f"   Cycle {cycle_num}: ICI start at index {charge_start_idx}")
        else:
            print(f"   Cycle {cycle_num}: No ICI start found (no current > {current_threshold} mA)")

    print(f"✅ Found {len(ici_starts)} ICI start points")
    return ici_starts

def downsample_data(data, max_points=10000, target_points=5000):
    """Keep all data points - no downsampling for complete analysis"""
    print(f"   Keeping all {len(data)} data points (no downsampling)")
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
    print("🔋 ICI Battery Analysis - Data Loading")
    print("=" * 50)

    if not folder_path or not txt_file_name:
        print("❌ folder_path and txt_file_name are required")
        return None

    print(f"\n🚀 Starting analysis with:")
    print(f"  📁 Folder: {folder_path}")
    print(f"  📄 File: {txt_file_name}")
    print(f"  ⚡ Current threshold: {current_threshold} mA")

    try:
        txt_path = os.path.join(folder_path, txt_file_name)
        if not os.path.exists(txt_path):
            print(f"❌ File not found: {txt_path}")
            return None

        print("\n📖 Reading data file...")
        df_loaded = load_data_flexible(txt_path)
        if df_loaded is None:
            return None

        if column_map is not None:
            print(f"🗂️ Using manual column mapping: {column_map}")
            _, df_cleaned = detect_data_format(df_loaded)   # reuse the cleaning step
            df_raw = build_df_from_map(df_cleaned, column_map)
            data_format = 'multi_cycle' if column_map.get('cycle') else 'single_cycle'
        else:
            data_format, df_cleaned = detect_data_format(df_loaded)
            if data_format == "unknown":
                print("❌ Unsupported data format")
                return None
            df_raw = standardize_columns_by_position(df_cleaned, data_format)

        if df_raw is None:
            return None

        print(f"✅ Data loaded and standardized successfully")
        print(f"   Format: {data_format}")
        print(f"   Shape: {df_raw.shape}")
        print(f"   Columns: {list(df_raw.columns)}")

        df_raw = detect_and_fix_cycle_structure(
            df_raw, current_threshold,
            mode=cycle_detection_mode, data_format=data_format)
        if len(df_raw) == 0:
            print("❌ No valid data after cycle processing")
            return None

        ici_starts = find_ici_starts(df_raw, current_threshold)

        cycle_list = sorted(df_raw['cycle'].unique())
        if len(cycle_list) == 0:
            print("❌ No valid cycles found")
            return None

        plot_data = downsample_data(df_raw, max_points=10000, target_points=5000)

        try:
            cycle_list = [int(c) for c in cycle_list if not pd.isna(c)]
        except Exception:
            pass

        print(f"\n✅ Data analysis completed successfully!")
        print(f"   • Data format: {data_format.replace('_', ' ').title()}")
        print(f"   • Loaded {len(cycle_list)} cycle(s)")
        print(f"   • Found {len(ici_starts)} ICI start point(s)")
        print(f"   • Total data points: {len(df_raw)}")

        return DataLoadResult(df_raw, plot_data, ici_starts, cycle_list, data_format)

    except Exception as e:
        print(f"❌ Error in data analysis: {e}")
        import traceback
        traceback.print_exc()
        return None