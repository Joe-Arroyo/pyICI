#!/usr/bin/env python3
"""
ICI Battery Analysis - Data Loader Module
Multi-cycle ICI Data Loading and Processing with Smart Auto-Detection
Supports both single-cycle (3 columns) and multi-cycle (4 columns) formats
"""

# =============================================================================
# DATA LOADING AND PROCESSING MODULE
# =============================================================================

import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from IPython.display import clear_output, display
import ipywidgets as widgets
import time

# =============================================================================
# CONFIGURATION
# =============================================================================

# Analysis parameters (adjust as needed)
MAX_REST_DURATION = 1800  # seconds
CURRENT_THRESHOLD = 1.0   # mA

# Cycle identification for files WITHOUT a cycle-number column:
#   'auto' -> detect cycles automatically from the current signal
#   'file' -> treat the whole file as a single cycle (original behaviour)
CYCLE_DETECTION_MODE = 'auto'

# Manual column mapping (role -> original column name; the 'cycle' role may be
# None). Set by the GUI mapping dialog for files with more than 3 columns.
# None means: use the automatic position-based detection (3/4-column files).
COLUMN_MAP = None

# Standard column names (internal format after processing)
STANDARD_COLUMNS = ['cycle', 't/s', 'E/V', 'I/mA']

# =============================================================================
# GLOBAL VARIABLES
# =============================================================================

# Global variables (will be set during data loading)
df_raw = None
plot_data = None
ici_starts = None
cycle_list = []
data_format = None  # Track whether single-cycle or multi-cycle

# =============================================================================
# FILE SELECTION FUNCTIONS
# =============================================================================

def list_available_files(folder_path="data"):
    """List all .txt files in the specified folder"""
    if not os.path.exists(folder_path):
        print(f"📁 Folder '{folder_path}' doesn't exist")
        return []
    
    txt_files = [f for f in os.listdir(folder_path) if f.endswith('.txt')]
    return txt_files

def select_data_file(folder_path="data"):
    """Interactive file selection from available .txt files"""
    print(f"\n📁 Looking for .txt files in '{folder_path}' folder...")
    
    # Check if folder exists
    if not os.path.exists(folder_path):
        create_folder = input(f"📁 Folder '{folder_path}' doesn't exist. Create it? (y/n): ").strip().lower()
        if create_folder == 'y':
            os.makedirs(folder_path)
            print(f"✅ Created folder: {folder_path}")
            print(f"📋 Please copy your .txt data files to this folder and run again")
            return None, None
        else:
            print("❌ Cannot proceed without data folder")
            return None, None
    
    # List available files
    txt_files = list_available_files(folder_path)
    
    if not txt_files:
        print(f"❌ No .txt files found in '{folder_path}'")
        print(f"📋 Please copy your ICI data files to this folder")
        return None, None
    
    print(f"\n📄 Found {len(txt_files)} .txt file(s):")
    for i, filename in enumerate(txt_files, 1):
        print(f"  {i}. {filename}")
    
    # Get file selection
    if len(txt_files) == 1:
        selected_file = txt_files[0]
        print(f"🎯 Auto-selected: {selected_file}")
        return folder_path, selected_file
    else:
        while True:
            try:
                choice = input(f"\n🎯 Select file (1-{len(txt_files)}): ").strip()
                choice_num = int(choice)
                if 1 <= choice_num <= len(txt_files):
                    selected_file = txt_files[choice_num - 1]
                    print(f"✅ Selected: {selected_file}")
                    return folder_path, selected_file
                else:
                    print(f"❌ Please enter a number between 1 and {len(txt_files)}")
            except ValueError:
                print("❌ Please enter a valid number")

def get_analysis_parameters():
    """Interactive parameter setting for analysis"""
    print(f"\n⚙️ Analysis Parameters Setup:")
    print(f"Current defaults:")
    print(f"  • Max rest duration: {MAX_REST_DURATION} seconds")
    print(f"  • Current threshold: {CURRENT_THRESHOLD} mA")
    
    # Ask if user wants to change parameters
    change_params = input(f"\nWould you like to modify these parameters? (y/n): ").strip().lower()
    
    if change_params != 'y':
        return MAX_REST_DURATION, CURRENT_THRESHOLD
    
    # Get max rest duration
    while True:
        try:
            rest_input = input(f"\n📏 Enter max rest duration in seconds (default {MAX_REST_DURATION}): ").strip()
            if not rest_input:  # Use default
                max_rest = MAX_REST_DURATION
                break
            else:
                max_rest = float(rest_input)
                if max_rest > 0:
                    break
                else:
                    print("❌ Rest duration must be positive")
        except ValueError:
            print("❌ Please enter a valid number")
    
    # Get current threshold
    while True:
        try:
            current_input = input(f"⚡ Enter current threshold in mA (default {CURRENT_THRESHOLD}): ").strip()
            if not current_input:  # Use default
                current_thresh = CURRENT_THRESHOLD
                break
            else:
                current_thresh = float(current_input)
                if current_thresh >= 0:
                    break
                else:
                    print("❌ Current threshold must be non-negative")
        except ValueError:
            print("❌ Please enter a valid number")
    
    print(f"\n✅ Parameters set:")
    print(f"  • Max rest duration: {max_rest} seconds")
    print(f"  • Current threshold: {current_thresh} mA")
    
    return max_rest, current_thresh

# =============================================================================
# DATA LOADING HELPER FUNCTIONS
# =============================================================================

def inspect_data_file(file_path):
    """Inspect the data file to understand its structure"""
    print(f"🔍 Inspecting data file: {file_path}")
    
    try:
        # Read first few lines to understand structure
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = [f.readline().strip() for _ in range(10)]
        
        print("First 10 lines:")
        for i, line in enumerate(lines):
            if line:
                print(f"  {i+1}: {line}")
        
        # Try to detect delimiter
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
        # Try different approaches to load the data
        print(f"\n📖 Attempting to load data...")
        
        # Method 1: Use pandas with detected delimiter (auto-handles no header)
        df = _read_table(file_path, delimiter)
        
        print(f"✅ Data loaded successfully!")
        print(f"   Shape: {df.shape}")
        print(f"   Original columns: {list(df.columns)}")
        
        # Show first few rows for verification
        print(f"\n📊 First 5 rows:")
        print(df.head())
        
        return df
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        return None

def detect_data_format(df):
    """Detect if data is single-cycle or multi-cycle format based on column count"""
    # Remove any unnamed/empty columns first
    df_clean = df.copy()
    
    # Drop columns that are unnamed or mostly NaN
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
        # 3 columns: [time/s, voltage, current] → add cycle column
        if len(df_std.columns) != 3:
            print(f"❌ Expected 3 columns for single cycle, got {len(df_std.columns)}")
            return None
        
        # Assign standard names by position
        old_cols = list(df_std.columns)
        new_column_mapping = {
            old_cols[0]: 't/s',     # First column → time
            old_cols[1]: 'E/V',     # Second column → voltage  
            old_cols[2]: 'I/mA'     # Third column → current
        }
        
        # Apply mapping
        df_std = df_std.rename(columns=new_column_mapping)
        
        # Add artificial cycle column with value 1
        df_std.insert(0, 'cycle', 1)
        
        print(f"   ✅ Single cycle conversion:")
        for old, new in new_column_mapping.items():
            print(f"      '{old}' → '{new}'")
        print(f"      Added 'cycle' column = 1")
        
    elif data_format == "multi_cycle":
        # 4 columns: [cycle, time/s, voltage, current]
        if len(df_std.columns) != 4:
            print(f"❌ Expected 4 columns for multi cycle, got {len(df_std.columns)}")
            return None
        
        # Assign standard names by position
        old_cols = list(df_std.columns)
        new_column_mapping = {
            old_cols[0]: 'cycle',   # First column → cycle
            old_cols[1]: 't/s',     # Second column → time
            old_cols[2]: 'E/V',     # Third column → voltage
            old_cols[3]: 'I/mA'     # Fourth column → current
        }
        
        # Apply mapping
        df_std = df_std.rename(columns=new_column_mapping)
        
        print(f"   ✅ Multi cycle conversion:")
        for old, new in new_column_mapping.items():
            print(f"      '{old}' → '{new}'")
    
    else:
        print(f"❌ Cannot standardize unknown format: {data_format}")
        return None
    
    # Verify we have all required columns
    required_cols = STANDARD_COLUMNS  # ['cycle', 't/s', 'E/V', 'I/mA']
    missing_cols = [col for col in required_cols if col not in df_std.columns]
    
    if missing_cols:
        print(f"❌ Missing required columns after standardization: {missing_cols}")
        print(f"Available columns: {list(df_std.columns)}")
        return None
    
    print(f"✅ Standardization complete. Final columns: {list(df_std.columns)}")
    
    # Show data sample
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

    Steps:
      1. macro-phase per point: |I| <= threshold -> rest, I > 0 -> charge,
         I < 0 -> discharge
      2. forward-fill rests into the preceding active phase
      3. count a half-cycle boundary at every charge<->discharge flip
      4. full cycle = (half_index // 2) + 1   (pairs every two half-cycles)

    Returns a numpy int array (cycles 1..N), one per row of df.
    """
    current = df[current_col].to_numpy(dtype=float)
    n = len(current)
    if n == 0:
        return np.ones(0, dtype=int)

    # 1) macro-phase: +1 charge, -1 discharge, 0 rest
    phase = np.where(current > current_threshold, 1,
             np.where(current < -current_threshold, -1, 0)).astype(int)

    nz = np.flatnonzero(phase != 0)
    if nz.size == 0:
        print("   ⚠️ No current above threshold - treating as a single cycle")
        return np.ones(n, dtype=int)

    # 2) forward-fill rests with the preceding active phase (vectorized)
    ff = np.zeros(n, dtype=int)
    ff[nz] = nz
    ff = np.maximum.accumulate(ff)
    filled = phase[ff]
    filled[:nz[0]] = phase[nz[0]]        # leading rests -> first active phase

    # 3) half-cycle index: +1 at each charge<->discharge flip
    changed = np.zeros(n, dtype=bool)
    changed[1:] = filled[1:] != filled[:-1]
    half_index = np.cumsum(changed)

    # 4) pair two half-cycles into one full cycle
    cycles = (half_index // 2) + 1
    return cycles.astype(int)


def detect_and_fix_cycle_structure(df, current_threshold=1.0,
                                   mode=None, data_format=None):
    """Process cycle structure.

    For 3-column (single-cycle format) files, cycles can be auto-detected from
    the current signal when mode == 'auto'. 4-column files keep their own
    cycle-number column unchanged.
    """
    df_fixed = df.copy()

    if mode is None:
        mode = globals().get('CYCLE_DETECTION_MODE', 'auto')
    if data_format is None:
        data_format = globals().get('data_format', None)

    print(f"\n🔧 Processing cycle structure (mode = '{mode}', format = '{data_format}')...")

    if 'cycle' not in df_fixed.columns:
        print(f"❌ No cycle column found in data")
        return df_fixed

    # Remove rows with NaN cycle numbers
    before_len = len(df_fixed)
    df_fixed = df_fixed.dropna(subset=['cycle'])
    after_len = len(df_fixed)
    if after_len != before_len:
        print(f"🧹 Removed {before_len - after_len} rows with NaN cycle numbers")

    if len(df_fixed) == 0:
        print(f"❌ No valid cycle data found")
        return df_fixed

    # Signal-based detection: only for 3-column files (no real cycle column)
    # and only when the user asked for automatic detection.
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
        
        # Find first point where current is above threshold (start of charge)
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
# PLOTTING FUNCTIONS
# =============================================================================

def create_overview_plot(plot_data, ici_starts, cycle_list):
    """Create overview plot of all cycles"""
    if len(plot_data) == 0 or len(cycle_list) == 0:
        print("⚠️ No data to plot")
        return
    
    print(f"📈 Creating overview plot for {len(cycle_list)} cycles...")
    
    plt.figure(figsize=(12, 8))
    
    colors = plt.cm.tab10(np.linspace(0, 1, len(cycle_list)))
    
    for i, cycle_num in enumerate(cycle_list):
        cycle_data = plot_data[plot_data['cycle'] == cycle_num]
        if len(cycle_data) > 0:
            plt.plot(cycle_data['t/s'], cycle_data['E/V'], 
                    label=f'C{cycle_num}', color=colors[i], alpha=0.7)
            
            # Mark ICI start if available
            if cycle_num in ici_starts:
                start_idx = ici_starts[cycle_num]
                if start_idx in cycle_data.index:
                    start_point = cycle_data.loc[start_idx]
                    plt.scatter(start_point['t/s'], start_point['E/V'], 
                              color=colors[i], s=50, marker='o', edgecolor='black')
    
    plt.xlabel('Time (s)')
    plt.ylabel('Voltage (V)')
    plt.title('ICI Analysis - Overview: All Cycles')
    plt.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.show()

def plot_cycle(cycle_num, plot_data, ici_starts):
    """Plot individual cycle with detailed information"""
    cycle_data = plot_data[plot_data['cycle'] == cycle_num]
    
    if len(cycle_data) == 0:
        print(f"❌ No data for cycle {cycle_num}")
        return
    
    print(f"📊 Plotting detailed view for cycle {cycle_num}...")
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    
    # Plot 1: Voltage vs Time
    ax1.plot(cycle_data['t/s'], cycle_data['E/V'], 'b-', linewidth=2)
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Voltage (V)')
    ax1.set_title(f'Cycle {cycle_num} - Voltage vs Time')
    ax1.grid(True, alpha=0.3)
    
    # Mark ICI start if available
    if cycle_num in ici_starts:
        start_idx = ici_starts[cycle_num]
        if start_idx in cycle_data.index:
            start_point = cycle_data.loc[start_idx]
            ax1.scatter(start_point['t/s'], start_point['E/V'], 
                       color='red', s=100, marker='o', 
                       label=f'ICI Start', zorder=5)
            ax1.legend()
    
    # Plot 2: Current vs Time
    ax2.plot(cycle_data['t/s'], cycle_data['I/mA'], 'g-', linewidth=2)
    ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Current (mA)')
    ax2.set_title(f'Cycle {cycle_num} - Current vs Time')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Show cycle statistics
    print(f"\n📊 Cycle {cycle_num} Statistics:")
    print(f"   • Duration: {cycle_data['t/s'].max() - cycle_data['t/s'].min():.1f} seconds")
    print(f"   • Data points: {len(cycle_data)}")
    print(f"   • Voltage range: {cycle_data['E/V'].min():.3f} - {cycle_data['E/V'].max():.3f} V")
    
    # Current analysis
    pos_current = cycle_data[cycle_data['I/mA'] > 0]['I/mA']
    neg_current = cycle_data[cycle_data['I/mA'] < 0]['I/mA']
    
    if len(pos_current) > 0:
        print(f"   • Positive current: {pos_current.mean():.2f} ± {pos_current.std():.2f} mA")
    if len(neg_current) > 0:
        print(f"   • Negative current: {neg_current.mean():.2f} ± {neg_current.std():.2f} mA")

# =============================================================================
# INTERACTIVE CONSOLE INTERFACE
# =============================================================================

def console_cycle_explorer():
    """Console interface for exploring individual cycles"""
    global df_raw, plot_data, ici_starts, cycle_list
    
    if df_raw is None or len(cycle_list) == 0:
        print("❌ No data loaded or no cycles available")
        return
    
    print(f"\n🎮 Cycle Explorer Interface")
    print(f"=" * 40)
    print(f"Available cycles: {cycle_list}")
    print(f"Commands:")
    print(f"  • Enter cycle number (e.g., '1', '2', '3')")
    print(f"  • 'all' - Show overview of all cycles")
    print(f"  • 'help' - Show this help")
    print(f"  • 'q' - Quit explorer")
    print(f"=" * 40)
    
    while True:
        try:
            user_input = input(f"\n🎯 Enter cycle number or command: ").strip().lower()
            
            if user_input == 'q' or user_input == 'quit':
                print("👋 Exiting cycle explorer")
                break
            elif user_input == 'help':
                print(f"\n📋 Available commands:")
                print(f"  • Cycle numbers: {cycle_list}")
                print(f"  • 'all' - Overview plot")
                print(f"  • 'q' - Quit")
            elif user_input == 'all':
                print(f"📈 Showing overview of all cycles...")
                create_overview_plot(plot_data, ici_starts, cycle_list)
            else:
                try:
                    cycle_num = int(user_input)
                    if cycle_num in cycle_list:
                        plot_cycle(cycle_num, plot_data, ici_starts)
                    else:
                        print(f"❌ Cycle {cycle_num} not available. Available: {cycle_list}")
                except ValueError:
                    print("❌ Invalid input. Enter a cycle number or command.")
                    
        except KeyboardInterrupt:
            print("\n👋 Exiting cycle explorer")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

# =============================================================================
# MAIN EXECUTION FUNCTION
# =============================================================================

def run_data_analysis(folder_path=None, txt_file_name=None, interactive=True):
    """
    Main function to execute data loading and analysis functionality
    
    Parameters:
    - folder_path: Path to data folder (default: "data")
    - txt_file_name: Name of data file (default: interactive selection)  
    - interactive: If True, prompts for file and parameter selection
    
    Returns:
    - bool: True if successful, False otherwise
    """
    global df_raw, plot_data, ici_starts, cycle_list, data_format
    
    print("🔋 ICI Battery Analysis - Data Loading")
    print("=" * 50)
    
    # Interactive mode: let user select file and parameters
    if interactive and (folder_path is None or txt_file_name is None):
        print("🎯 Interactive mode - selecting file and parameters...")
        
        # File selection
        folder_path, txt_file_name = select_data_file("data")
        if folder_path is None or txt_file_name is None:
            return False
        
        # Parameter selection
        max_rest_duration, current_threshold = get_analysis_parameters()
    else:
        print("🤖 Non-interactive mode - using provided parameters...")
        
        # Use provided parameters or defaults
        if folder_path is None:
            folder_path = "data"
        if txt_file_name is None:
            # If no file specified and not interactive, try to auto-select
            txt_files = list_available_files(folder_path)
            if len(txt_files) == 1:
                txt_file_name = txt_files[0]
                print(f"📄 Auto-selected single file: {txt_file_name}")
            elif len(txt_files) > 1:
                print(f"❌ Multiple files found, but not in interactive mode")
                print(f"Available files: {txt_files}")
                print("Please specify txt_file_name or run in interactive mode")
                return False
            else:
                txt_file_name = "your_data.txt"
        max_rest_duration = MAX_REST_DURATION
        current_threshold = CURRENT_THRESHOLD
    
    print(f"\n🚀 Starting analysis with:")
    print(f"  📁 Folder: {folder_path}")
    print(f"  📄 File: {txt_file_name}")
    print(f"  ⏱️ Max rest duration: {max_rest_duration} seconds")
    print(f"  ⚡ Current threshold: {current_threshold} mA")
    
    try:
        # Construct file path
        txt_path = os.path.join(folder_path, txt_file_name)
        
        if not os.path.exists(txt_path):
            print(f"❌ File not found: {txt_path}")
            return False
        
        print("\n📖 Reading data file...")
        
        # Load data with flexible format detection
        df_loaded = load_data_flexible(txt_path)
        if df_loaded is None:
            return False

        if COLUMN_MAP is not None:
            # Manual column mapping supplied by the GUI (files with >3 columns)
            print(f"🗂️ Using manual column mapping: {COLUMN_MAP}")
            _, df_cleaned = detect_data_format(df_loaded)   # reuse the cleaning step
            df_raw = build_df_from_map(df_cleaned, COLUMN_MAP)
            # No cycle column mapped -> treat as single_cycle so signal-based
            # detection runs; a mapped cycle column -> use it (multi_cycle).
            data_format = 'multi_cycle' if COLUMN_MAP.get('cycle') else 'single_cycle'
        else:
            # Detect data format (single-cycle vs multi-cycle) and clean data
            data_format, df_cleaned = detect_data_format(df_loaded)
            if data_format == "unknown":
                print("❌ Unsupported data format")
                return False
            # Standardize columns based on position (this replaces the old name-based mapping)
            df_raw = standardize_columns_by_position(df_cleaned, data_format)

        if df_raw is None:
            return False
        
        print(f"✅ Data loaded and standardized successfully")
        print(f"   Format: {data_format}")
        print(f"   Shape: {df_raw.shape}")
        print(f"   Columns: {list(df_raw.columns)}")
        
        # Process cycle structure
        df_raw = detect_and_fix_cycle_structure(
            df_raw, current_threshold,
            mode=CYCLE_DETECTION_MODE, data_format=data_format)
        if len(df_raw) == 0:
            print("❌ No valid data after cycle processing")
            return False
        
        # Find ICI starts
        ici_starts = find_ici_starts(df_raw, current_threshold)
        
        # Get cycle list
        cycle_list = sorted(df_raw['cycle'].unique())
        print(f"✅ Available cycles: {cycle_list}")
        
        if len(cycle_list) == 0:
            print("❌ No valid cycles found")
            return False
        
        # Create downsampled data for plotting
        print(f"\n📊 Preparing plot data...")
        plot_data = downsample_data(df_raw, max_points=10000, target_points=5000)
        
        # Convert cycle_list to integers for console interface
        try:
            cycle_list_int = [int(c) for c in cycle_list if not pd.isna(c)]
            cycle_list = cycle_list_int
        except:
            pass  # Keep original if conversion fails
        
        print(f"✅ Final processed cycles: {cycle_list}")
        
        # Create overview plot
        create_overview_plot(plot_data, ici_starts, cycle_list)
        
        # Analysis summary
        print(f"\n✅ Data analysis completed successfully!")
        print(f"   • Data format: {data_format.replace('_', ' ').title()}")
        print(f"   • Loaded {len(cycle_list)} cycle(s)")
        print(f"   • Found {len(ici_starts)} ICI start point(s)")
        print(f"   • Total data points: {len(df_raw)}")
        print(f"   • Plot data points: {len(plot_data)}")
        
        # Ask user if they want to explore cycles (only in interactive mode)
        if interactive:
            explore = input(f"\nWould you like to explore individual cycles? (y/n): ").strip().lower()
            if explore == 'y' or explore == 'yes':
                console_cycle_explorer()
            else:
                print(f"💡 Tip: Run again and choose 'y' to explore individual cycles interactively!")
        
        return True
        
    except Exception as e:
        print(f"❌ Error in data analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

# =============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# =============================================================================

def run_cell1(folder_path=None, txt_file_name=None):
    """
    Backward compatibility wrapper - calls run_data_analysis with non-interactive mode
    """
    return run_data_analysis(folder_path, txt_file_name, interactive=False)

# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Running ICI Battery Analysis - Data Loading Module")
    print("Supports both single-cycle (3 columns) and multi-cycle (4 columns) formats")
    print("Interactive mode - will prompt for file selection and parameters")
    
    # Run in interactive mode - user selects file and parameters
    success = run_data_analysis()
    if success:
        print("✅ Data loading module completed successfully")
    else:
        print("❌ Data loading module failed")