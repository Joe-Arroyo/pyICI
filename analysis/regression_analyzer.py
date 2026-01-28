#!/usr/bin/env python3
"""
ICI Battery Analysis - Regression Analyzer Module (Version 28 COMPLETE)
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
import matplotlib.pyplot as plt
import os
import warnings
warnings.filterwarnings('ignore')

# =============================================================================
# CONFIGURATION
# =============================================================================

# Regression parameters
DEFAULT_R1_START = 2   # R1S - Short regression window start
DEFAULT_R1_LENGTH = 10  # R1L - Long regression window length
MAX_REST_DURATION = 1800  # seconds
ZERO_THRESHOLD = 1e-5

# =============================================================================
# GLOBAL VARIABLES
# =============================================================================

# Data from data_loader
df_raw = None
cycle_list = []

# Current analysis state
current_cycle = None

# Processed pulse data
charge_data_pulse = None
discharge_data_pulse = None
charge_pulse_nums = []
discharge_pulse_nums = []

# Storage for regression results
regression_results = {'Charge': [], 'Discharge': []}
saved_reg_params = {}

# =============================================================================
# PHASE CLASSIFICATION FUNCTION (from Cell 2)
# =============================================================================

def classify_charge_discharge(df, current_col='I/mA'):
    """
    Classify data points as charge, discharge, or rest based on current.
    This is CRITICAL for proper pulse separation.
    """
    current = df[current_col].values
    labels = np.empty(len(current), dtype=object)
    
    i = 0
    while i < len(current):
        if current[i] > 0:
            start = i
            while i < len(current) and current[i] >= 0:
                i += 1
            labels[start:i] = 'charge'
        elif current[i] < 0:
            start = i
            while i < len(current) and current[i] <= 0:
                i += 1
            labels[start:i] = 'discharge'
        else:
            # Current is zero - assign same as previous or 'rest'
            labels[i] = 'rest' if i == 0 else labels[i-1]
            i += 1
    
    return labels

# =============================================================================
# PULSE PROCESSING FUNCTIONS
# =============================================================================

def assign_valid_pulses(df, max_rest=MAX_REST_DURATION):
    """Assign pulse numbers to valid pulses based on rest duration."""
    df = df.copy()
    pulse_number = np.zeros(len(df), dtype=int)
    pulse_counter = 0
    i = 0
    n = len(df)
    
    while i < n:
        if df['I/mA'].iloc[i] != 0:
            start = i
            while i < n and df['I/mA'].iloc[i] != 0:
                i += 1
            rest_start = i
            while i < n and df['I/mA'].iloc[i] == 0:
                i += 1
            
            if rest_start < n:
                rest_duration = df['t/s'].iloc[i-1] - df['t/s'].iloc[rest_start] if i > rest_start else 0
                if rest_duration <= max_rest:
                    pulse_counter += 1
                    pulse_number[start:rest_start] = pulse_counter
                    if i < n:
                        pulse_number[rest_start:i] = pulse_counter
        else:
            i += 1
    
    df['pulse_number'] = pulse_number
    return df

def compute_V0_t0(df):
    """Compute V0 and t0 for each pulse."""
    df = df.copy()
    V0_list, t0_list = [], []
    
    for p in df['pulse_number'].unique():
        pulse_df = df[df['pulse_number'] == p].copy()
        nonzero = pulse_df[pulse_df['I/mA'] != 0]
        
        if not nonzero.empty:
            V0 = nonzero['E/V'].iloc[-1]
            t0 = nonzero['t/s'].iloc[-1]
        else:
            V0, t0 = np.nan, np.nan
            
        V0_list.extend([V0] * len(pulse_df))
        t0_list.extend([t0] * len(pulse_df))
    
    df['V0'] = V0_list
    df['t0'] = t0_list
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
        
    except Exception as e:
        print(f"Error in regression: {e}")
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

def load_cycle_for_regression(cycle_num):
    """Load and prepare cycle data for regression analysis."""
    global current_cycle, charge_data_pulse, discharge_data_pulse
    global charge_pulse_nums, discharge_pulse_nums
    
    if df_raw is None:
        print("❌ No data loaded")
        return False
    
    # Get cycle data
    cycle_df = df_raw[df_raw['cycle'] == cycle_num].copy()
    
    if len(cycle_df) == 0:
        print(f"❌ No data found for cycle {cycle_num}")
        return False
    
    current_cycle = cycle_num
    
    print(f"Analyzing cycle {cycle_num}...")
    print(f"  Cycle {cycle_num} has {len(cycle_df)} data points")
    
    # CRITICAL: Add phase classification if not present
    if 'cycle_phase' not in cycle_df.columns:
        print("  Adding phase classification...")
        cycle_df['cycle_phase'] = classify_charge_discharge(cycle_df)
    
    # Show phase distribution
    phase_dist = cycle_df['cycle_phase'].value_counts().to_dict()
    print(f"  Phase distribution: {phase_dist}")
    
    # Separate charge and discharge data using cycle_phase
    charge_df = cycle_df[cycle_df['cycle_phase'] == 'charge'].copy()
    discharge_df = cycle_df[cycle_df['cycle_phase'] == 'discharge'].copy()
    
    print(f"Assigning pulse numbers with max rest duration: {MAX_REST_DURATION}s")
    
    # Process charge pulses
    if len(charge_df) > 0:
        charge_data_pulse = assign_valid_pulses(charge_df, MAX_REST_DURATION)
        charge_pulse_nums = [p for p in charge_data_pulse['pulse_number'].unique() if p > 0]
        print(f"Assigned {len(charge_pulse_nums)} valid charge pulses")
        
        if len(charge_pulse_nums) > 0:
            print("Computing V0 and t0 values for charge pulses...")
            charge_data_pulse = compute_V0_t0(charge_data_pulse)
            print(f"Computed V0/t0 for {len(charge_pulse_nums)} charge pulse measurements")
    else:
        charge_data_pulse = pd.DataFrame()
        charge_pulse_nums = []
        print("No charge data found")
    
    # Process discharge pulses
    if len(discharge_df) > 0:
        discharge_data_pulse = assign_valid_pulses(discharge_df, MAX_REST_DURATION)
        discharge_pulse_nums = [p for p in discharge_data_pulse['pulse_number'].unique() if p > 0]
        print(f"Assigned {len(discharge_pulse_nums)} valid discharge pulses")
        
        if len(discharge_pulse_nums) > 0:
            print("Computing V0 and t0 values for discharge pulses...")
            discharge_data_pulse = compute_V0_t0(discharge_data_pulse)
            print(f"Computed V0/t0 for {len(discharge_pulse_nums)} discharge pulse measurements")
    else:
        discharge_data_pulse = pd.DataFrame()
        discharge_pulse_nums = []
        print("No discharge data found")
    
    # Summary
    print(f"Cycle {cycle_num} loaded:")
    print(f"  • Charge pulses: {len(charge_pulse_nums)} - {charge_pulse_nums}")
    print(f"  • Discharge pulses: {len(discharge_pulse_nums)} - {discharge_pulse_nums}")
    
    if len(charge_pulse_nums) == 0 and len(discharge_pulse_nums) == 0:
        print("  • No valid pulses found")
        return False
    
    return True

# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def plot_pulse_r2_analysis(cycle_data, pulse_num, r1s, r1l, phase=""):
    """Plot detailed R² analysis for a single pulse"""
    pulse_data = cycle_data[cycle_data['pulse_number'] == pulse_num]
    
    if len(pulse_data) == 0:
        print(f"❌ No data for pulse {pulse_num}")
        return
    
    rest_data = pulse_data[pulse_data['I/mA'] == 0].copy()
    
    if len(rest_data) == 0:
        print(f"❌ No rest data for pulse {pulse_num}")
        return
    
    rest_data = rest_data.reset_index(drop=True)
    
    # Get V0 and compute ΔV
    V0 = get_V0(cycle_data, pulse_num)
    rest_data['ΔV'] = rest_data['E/V'] - V0
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15, 6))
    
    # Plot 1: Full pulse view
    ax1.plot(pulse_data['t/s'], pulse_data['E/V'], 'b-', linewidth=2, label='Full Pulse')
    ax1.plot(rest_data['t/s'], rest_data['E/V'], 'ro', markersize=4, label='Rest Period')
    
    # Highlight regression windows
    if len(rest_data) >= r1s:
        ax1.plot(rest_data['t/s'][:r1s], rest_data['E/V'][:r1s], 'go', 
                markersize=6, label=f'Short Reg. (r1s={r1s})')
    
    if len(rest_data) >= r1l:
        ax1.plot(rest_data['t/s'][:r1l], rest_data['E/V'][:r1l], 'mo', 
                markersize=4, label=f'Long Reg. (r1l={r1l})', alpha=0.7)
    
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Voltage (V)')
    ax1.set_title(f'{phase} Pulse {pulse_num} - Full View')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Regression analysis with sqrt(time)
    times_sqrt = np.sqrt(rest_data['t/s'].values - rest_data['t/s'].values[0])
    
    ax2.plot(times_sqrt, rest_data['ΔV'].values, 'ro-', markersize=4, label='ΔV vs √t')
    
    # Compute and plot regression
    regression_result = compute_single_pulse_regression(rest_data, r1s, r1l)
    
    if not np.isnan(regression_result['r2']) and len(rest_data) >= r1s + r1l:
        X_fit = times_sqrt[r1s:r1s + r1l]
        y_fit = regression_result['slope'] * X_fit + regression_result['intercept']
        ax2.plot(X_fit, y_fit, 'g-', linewidth=2, 
                label=f'Regression: R²={regression_result["r2"]:.3f}')
    
    ax2.set_xlabel('√Time (√s)')
    ax2.set_ylabel('ΔV (V)')
    ax2.set_title(f'{phase} Pulse {pulse_num} - R² Analysis')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print results
    print(f"\n📊 R² Analysis Results for {phase} Pulse {pulse_num}:")
    print(f"   • R² = {regression_result['r2']:.4f}")
    print(f"   • Slope = {regression_result['slope']:.4f}")
    print(f"   • V0 = {V0:.3f} V")
    print(f"   • Rest data points: {len(rest_data)}")

def plot_all_cycles_r2_overview(cycle_range, r1s, r1l):
    """Plot R² overview for multiple cycles"""
    if df_raw is None:
        print("❌ No data loaded")
        return
    
    all_results = []
    
    for cycle_num in cycle_range:
        success = load_cycle_for_regression(cycle_num)
        if not success:
            continue
        
        # Compute R² for charge pulses
        if len(charge_pulse_nums) > 0:
            charge_results = compute_r2_all_pulses(charge_data_pulse, charge_pulse_nums, r1s, r1l)
            for r in charge_results:
                r['cycle'] = cycle_num
            all_results.extend(charge_results)
        
        # Compute R² for discharge pulses
        if len(discharge_pulse_nums) > 0:
            discharge_results = compute_r2_all_pulses(discharge_data_pulse, discharge_pulse_nums, r1s, r1l)
            for r in discharge_results:
                r['cycle'] = cycle_num
            all_results.extend(discharge_results)
    
    if not all_results:
        print("❌ No results to plot")
        return
    
    # Convert to DataFrame
    df_results = pd.DataFrame(all_results)
    
    fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(16, 12))
    
    # Separate by phase
    charge_data = df_results[df_results['phase'] == 'charge']
    discharge_data = df_results[df_results['phase'] == 'discharge']
    
    # Plot 1: R² vs Pulse Index
    if len(charge_data) > 0:
        ax1.scatter(charge_data.index, charge_data['r2'], color='red', 
                   alpha=0.6, label='Charge', s=30)
    if len(discharge_data) > 0:
        ax1.scatter(discharge_data.index, discharge_data['r2'], color='blue', 
                   alpha=0.6, label='Discharge', s=30)
    
    ax1.set_xlabel('Pulse Index')
    ax1.set_ylabel('R²')
    ax1.set_title(f'R² Analysis (r1s={r1s}, r1l={r1l})')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: R² vs Cycle
    if len(charge_data) > 0:
        ax2.scatter(charge_data['cycle'], charge_data['r2'], color='red', 
                   alpha=0.6, label='Charge', s=30)
    if len(discharge_data) > 0:
        ax2.scatter(discharge_data['cycle'], discharge_data['r2'], color='blue', 
                   alpha=0.6, label='Discharge', s=30)
    
    ax2.set_xlabel('Cycle')
    ax2.set_ylabel('R²')
    ax2.set_title('R² vs Cycle Number')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    
    # Plot 3: V0 distribution
    if len(charge_data) > 0:
        ax3.hist(charge_data['V0'].dropna(), bins=20, alpha=0.6, color='red', label='Charge')
    if len(discharge_data) > 0:
        ax3.hist(discharge_data['V0'].dropna(), bins=20, alpha=0.6, color='blue', label='Discharge')
    
    ax3.set_xlabel('V0 (V)')
    ax3.set_ylabel('Frequency')
    ax3.set_title('V0 Distribution')
    ax3.legend()
    ax3.grid(True, alpha=0.3)
    
    # Plot 4: R² histogram
    if len(df_results) > 0:
        ax4.hist(df_results['r2'].dropna(), bins=30, alpha=0.7, color='purple', edgecolor='black')
        ax4.axvline(df_results['r2'].mean(), color='red', linestyle='--', linewidth=2, 
                   label=f'Mean: {df_results["r2"].mean():.3f}')
    
    ax4.set_xlabel('R²')
    ax4.set_ylabel('Frequency')
    ax4.set_title('R² Distribution')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()
    
    # Print summary
    print(f"\n📊 R² Analysis Summary for Cycles {cycle_range}:")
    print(f"   • Total pulses analyzed: {len(df_results)}")
    print(f"   • Charge pulses: {len(charge_data)}")
    print(f"   • Discharge pulses: {len(discharge_data)}")
    if len(df_results) > 0:
        print(f"   • R² Mean: {df_results['r2'].mean():.3f}, Std: {df_results['r2'].std():.3f}")

# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

def export_regression_results(cycle_range, r1s, r1l, output_folder="exports"):
    """Export regression results to CSV"""
    if df_raw is None:
        print("❌ No data to export")
        return False
    
    try:
        os.makedirs(output_folder, exist_ok=True)
        
        all_results = []
        
        for cycle_num in cycle_range:
            success = load_cycle_for_regression(cycle_num)
            if not success:
                continue
            
            # Export charge results
            if len(charge_pulse_nums) > 0:
                charge_results = compute_r2_all_pulses(charge_data_pulse, charge_pulse_nums, r1s, r1l)
                for r in charge_results:
                    r['cycle'] = cycle_num
                all_results.extend(charge_results)
            
            # Export discharge results
            if len(discharge_pulse_nums) > 0:
                discharge_results = compute_r2_all_pulses(discharge_data_pulse, discharge_pulse_nums, r1s, r1l)
                for r in discharge_results:
                    r['cycle'] = cycle_num
                all_results.extend(discharge_results)
        
        if not all_results:
            print("❌ No results to export")
            return False
        
        # Create DataFrame and export
        df_export = pd.DataFrame(all_results)
        filename = f"r2_regression_results_r1s{r1s}_r1l{r1l}.csv"
        output_path = os.path.join(output_folder, filename)
        
        df_export.to_csv(output_path, index=False)
        
        print(f"✅ Exported {len(df_export)} regression results to: {output_path}")
        print(f"   • Columns: {list(df_export.columns)}")
        print(f"   • Cycles: {sorted(df_export['cycle'].unique())}")
        
        return True
        
    except Exception as e:
        print(f"❌ Export error: {e}")
        return False

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

# =============================================================================
# CONSOLE INTERFACE
# =============================================================================

def run_regression_analysis(df_input=None, interactive=True):
    """
    Main function to run regression analysis.
    Can be called from GUI or run interactively.
    """
    global df_raw, cycle_list
    
    # Use provided data or try to import from data_loader
    if df_input is not None:
        df_raw = df_input
        cycle_list = sorted(df_raw['cycle'].unique())
    else:
        try:
            from analysis.data_loader import df_raw as loader_df, cycle_list as loader_cycles
            if loader_df is None:
                print("❌ No data loaded. Please run data_loader first.")
                return False
            df_raw = loader_df
            cycle_list = loader_cycles
        except ImportError:
            print("❌ Could not import data from data_loader")
            return False
    
    print("\n" + "="*70)
    print("📊 R² REGRESSION ANALYSIS MODULE")
    print("="*70)
    print(f"✅ Data loaded: {len(df_raw)} points across {len(cycle_list)} cycles")
    print(f"Available cycles: {cycle_list}")
    print(f"Default parameters: R1S={DEFAULT_R1_START}, R1L={DEFAULT_R1_LENGTH}")
    
    if not interactive:
        return True
    
    # Interactive console
    r1s = DEFAULT_R1_START
    r1l = DEFAULT_R1_LENGTH
    
    print("\nOPTIONS:")
    print("1. Analyze single cycle")
    print("2. Analyze multiple cycles")
    print("3. Show detailed pulse analysis")
    print("4. Change global parameters")
    print("5. Show parameter status")
    print("6. Export results")
    print("7. Exit")
    
    while True:
        try:
            choice = input("\nEnter choice (1-7): ").strip()
            
            if choice == '7':
                print("👋 Exiting regression analysis")
                break
            
            elif choice == '1':
                cycle_num = int(input(f"Enter cycle number {cycle_list}: "))
                if cycle_num in cycle_list:
                    success = load_cycle_for_regression(cycle_num)
                    if success:
                        # Compute R² for all pulses
                        if len(charge_pulse_nums) > 0:
                            charge_results = compute_r2_all_pulses(charge_data_pulse, charge_pulse_nums, r1s, r1l)
                            print(f"\n✅ Charge R² analysis complete:")
                            for r in charge_results[:3]:  # Show first 3
                                print(f"   Pulse {r['pulse']}: R²={r['r2']:.4f}")
                        
                        if len(discharge_pulse_nums) > 0:
                            discharge_results = compute_r2_all_pulses(discharge_data_pulse, discharge_pulse_nums, r1s, r1l)
                            print(f"\n✅ Discharge R² analysis complete:")
                            for r in discharge_results[:3]:  # Show first 3
                                print(f"   Pulse {r['pulse']}: R²={r['r2']:.4f}")
                else:
                    print(f"❌ Cycle {cycle_num} not in available cycles")
            
            elif choice == '2':
                range_str = input(f"Enter cycle range (e.g., '0-5' or '0,2,4'): ")
                cycle_range = parse_range_input(range_str, cycle_list)
                if cycle_range:
                    print(f"📊 R² overview for cycles: {cycle_range}")
                    plot_all_cycles_r2_overview(cycle_range, r1s, r1l)
                else:
                    print(f"❌ No valid cycles in range")
            
            elif choice == '3':
                if current_cycle is None:
                    print("❌ No cycle loaded. Use option 1 first.")
                else:
                    pulse_num = int(input(f"Enter pulse number: "))
                    
                    # Check if pulse exists in charge or discharge
                    if pulse_num in charge_pulse_nums:
                        plot_pulse_r2_analysis(charge_data_pulse, pulse_num, r1s, r1l, "Charge")
                    elif pulse_num in discharge_pulse_nums:
                        plot_pulse_r2_analysis(discharge_data_pulse, pulse_num, r1s, r1l, "Discharge")
                    else:
                        print(f"❌ Pulse {pulse_num} not found in current cycle")
                        print(f"Available charge pulses: {charge_pulse_nums}")
                        print(f"Available discharge pulses: {discharge_pulse_nums}")
            
            elif choice == '4':
                new_r1s = input(f"Enter R1S (short window start) [current: {r1s}]: ")
                new_r1l = input(f"Enter R1L (long window length) [current: {r1l}]: ")
                
                if new_r1s:
                    r1s = int(new_r1s)
                if new_r1l:
                    r1l = int(new_r1l)
                
                print(f"✅ Updated: R1S={r1s}, R1L={r1l}")
            
            elif choice == '5':
                print(f"\n📋 Current parameters:")
                print(f"  R1S (short window): {r1s}")
                print(f"  R1L (long window): {r1l}")
                if current_cycle:
                    print(f"  Current cycle: {current_cycle}")
                    print(f"  Charge pulses: {len(charge_pulse_nums)} - {charge_pulse_nums}")
                    print(f"  Discharge pulses: {len(discharge_pulse_nums)} - {discharge_pulse_nums}")
                else:
                    print(f"  No cycle currently loaded")
            
            elif choice == '6':
                range_str = input(f"Enter cycle range to export (e.g., '0-5' or '0,2,4'): ")
                cycle_range = parse_range_input(range_str, cycle_list)
                if cycle_range:
                    print(f"📊 Exporting regression results for cycles: {cycle_range}")
                    success = export_regression_results(cycle_range, r1s, r1l)
                    if success:
                        print(f"✅ Export completed successfully")
                    else:
                        print(f"❌ Export failed")
                else:
                    print(f"❌ No valid cycles in range")
            
            else:
                print("❌ Invalid choice")
        
        except KeyboardInterrupt:
            print("\n👋 Exiting")
            break
        except ValueError as e:
            print(f"❌ Invalid input: {e}")
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
    
    return True

# =============================================================================
# MAIN EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("="*70)
    print("Running Regression Analyzer Module (Version 28 COMPLETE)")
    print("="*70)
    run_regression_analysis(interactive=True)