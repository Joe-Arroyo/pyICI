#!/usr/bin/env python3
"""
ICI Battery Analysis - Pulse Analyzer Module
Interactive Pulse Analysis & Visualization with Multi-Cycle Support
Complete rewrite with proper organization and functionality
"""

# =============================================================================
# IMPORTS
# =============================================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import ipywidgets as widgets
from IPython.display import display, clear_output

# =============================================================================
# CONFIGURATION
# =============================================================================

MAX_REST_DURATION = 1800  # seconds

# =============================================================================
# GLOBAL VARIABLES
# =============================================================================

# Data from data_loader
df_raw = None
cycle_list = []

# Current analysis state
current_cycle = None
current_cycle_data = None

# Processed pulse data
charge_data_rest = None
discharge_data_rest = None
charge_pulse_nums = []
discharge_pulse_nums = []

# Legacy variables for compatibility
pulse_data_charge = {}
pulse_data_discharge = {}

# =============================================================================
# PULSE ASSIGNMENT FUNCTIONS
# =============================================================================

def assign_valid_pulses(df, max_rest=MAX_REST_DURATION):
    """
    Assign pulse numbers to valid pulses based on rest duration
    Returns dataframe with only valid pulses (pulse_number > 0)
    """
    print(f"Assigning pulse numbers with max rest duration: {max_rest}s")
    
    df = df.copy()
    pulse_number = np.zeros(len(df), dtype=int)
    pulse_counter = 0
    i = 0
    n = len(df)
    
    while i < n:
        if df['I/mA'].iloc[i] != 0:  # Start of active period
            start = i
            # Find end of active period
            while i < n and df['I/mA'].iloc[i] != 0:
                i += 1
            rest_start = i
            # Find end of rest period
            while i < n and df['I/mA'].iloc[i] == 0:
                i += 1
            
            # Check if rest duration is within limit
            if rest_start < n:
                rest_duration = df['t/s'].iloc[i-1] - df['t/s'].iloc[rest_start]
                if 0 < rest_duration <= max_rest:
                    pulse_counter += 1
                    pulse_number[start:i] = pulse_counter
        else:
            i += 1
    
    df['pulse_number'] = pulse_number
    valid_df = df[df['pulse_number'] > 0].copy()
    
    valid_pulses = len(np.unique(valid_df['pulse_number']))
    print(f"Assigned {valid_pulses} valid pulses")
    
    return valid_df

def compute_V0_t0(df):
    """
    Compute V0 and t0 for each pulse
    V0 = voltage at end of active period
    t0 = time at end of active period
    """
    print(f"Computing V0 and t0 values for pulses...")
    
    df = df.copy()
    V0_list, t0_list = [], []
    
    for pulse_num in df['pulse_number'].unique():
        pulse_df = df[df['pulse_number'] == pulse_num].copy()
        nonzero = pulse_df[pulse_df['I/mA'] != 0]
        
        if not nonzero.empty:
            V0 = nonzero['E/V'].iloc[-1]  # Last voltage in active period
            t0 = nonzero['t/s'].iloc[-1]  # Last time in active period
        else:
            V0, t0 = np.nan, np.nan
            
        # Assign V0 and t0 to all points in this pulse
        pulse_length = len(pulse_df)
        V0_list.extend([V0] * pulse_length)
        t0_list.extend([t0] * pulse_length)
    
    df['V0'] = V0_list
    df['t0'] = t0_list
    df['rest'] = (df['I/mA'] == 0)
    
    valid_V0_count = sum(1 for v in V0_list if not np.isnan(v))
    print(f"Computed V0/t0 for {valid_V0_count} pulse measurements")
    
    return df

# =============================================================================
# PHASE CLASSIFICATION FUNCTIONS
# =============================================================================

def get_phase_classifier():
    """Get phase classification function with fallback"""
    try:
        from .phase_classifier import classify_charge_discharge
        print("Imported phase classifier from module")
        return classify_charge_discharge
    except ImportError:
        try:
            from phase_classifier import classify_charge_discharge
            print("Imported phase classifier directly")
            return classify_charge_discharge
        except ImportError:
            print("Using fallback phase classifier")
            def classify_charge_discharge(df):
                labels = []
                for current in df['I/mA']:
                    if current > 0:
                        labels.append('charge')
                    elif current < 0:
                        labels.append('discharge')
                    else:
                        labels.append('rest')
                return labels
            return classify_charge_discharge

# =============================================================================
# MAIN ANALYSIS FUNCTIONS
# =============================================================================

# =============================================================================
# REPLACE THIS FUNCTION IN: analysis/pulse_analyzer.py
# Location: Around line 70-120 (in the "MAIN ANALYSIS FUNCTIONS" section)
# =============================================================================

def analyze_cycle_pulses(cycle_num):
    """
    Main function to analyze all pulses in a cycle
    Sets global variables for charge and discharge data
    NOW WITH IMPROVED ERROR HANDLING AND AUTOMATIC CLASSIFICATION
    """
    global current_cycle, current_cycle_data
    global charge_data_rest, discharge_data_rest, charge_pulse_nums, discharge_pulse_nums
    
    print(f"\n{'='*60}")
    print(f"PULSE ANALYSIS FOR CYCLE {cycle_num}")
    print(f"{'='*60}")
    
    # Input validation
    if df_raw is None:
        print("❌ ERROR: No data available for analysis")
        print("   → Please load data first using Data Loader tab")
        return None, [], []
    
    # Get cycle data
    cycle_data = df_raw[df_raw['cycle'] == cycle_num].copy()
    if len(cycle_data) == 0:
        available = sorted(df_raw['cycle'].unique().tolist())
        print(f"❌ ERROR: No data found for cycle {cycle_num}")
        print(f"   → Available cycles: {available}")
        return None, [], []
    
    print(f"✓ Found {len(cycle_data)} data points for cycle {cycle_num}")
    
    # Phase classification with comprehensive error handling
    needs_classification = 'cycle_phase' not in cycle_data.columns
    
    if needs_classification:
        print(f"⚠  Cycle {cycle_num} not yet classified - classifying now...")
        
        try:
            # Try to get classifier function
            classify_func = get_phase_classifier()
            cycle_data['cycle_phase'] = classify_func(cycle_data)
            print(f"✓ Phase classification completed using classifier module")
            
        except Exception as e:
            print(f"⚠  Classifier import failed ({e}), using fallback...")
            
            # Emergency fallback classifier
            try:
                labels = []
                for current in cycle_data['I/mA']:
                    if current > 0:
                        labels.append('charge')
                    elif current < 0:
                        labels.append('discharge')
                    else:
                        labels.append('rest')
                cycle_data['cycle_phase'] = labels
                print(f"✓ Emergency classification completed successfully")
                
            except Exception as e2:
                print(f"❌ ERROR: Both classification methods failed: {e2}")
                return None, [], []
    else:
        print(f"✓ Cycle already classified")
    
    # Verify classification worked
    if 'cycle_phase' not in cycle_data.columns:
        print(f"❌ ERROR: Classification failed - no cycle_phase column")
        return None, [], []
    
    unique_phases = cycle_data['cycle_phase'].unique()
    print(f"   Detected phases: {list(unique_phases)}")
    
    # Separate by phase
    charge_data = cycle_data[cycle_data['cycle_phase'] == 'charge'].copy()
    discharge_data = cycle_data[cycle_data['cycle_phase'] == 'discharge'].copy()
    rest_data = cycle_data[cycle_data['cycle_phase'] == 'rest'].copy()
    
    print(f"✓ Phase separation:")
    print(f"   • Charge: {len(charge_data)} points")
    print(f"   • Discharge: {len(discharge_data)} points")
    print(f"   • Rest: {len(rest_data)} points")
    
    # Check if we have any charge or discharge data
    if len(charge_data) == 0 and len(discharge_data) == 0:
        print(f"⚠  WARNING: No charge or discharge data found in cycle {cycle_num}")
        print(f"   This cycle appears to contain only rest periods")
        return None, [], []
    
    # Reset global variables
    charge_data_rest = pd.DataFrame()
    discharge_data_rest = pd.DataFrame()
    charge_pulse_nums = []
    discharge_pulse_nums = []
    
    # Process charge pulses with error handling
    if len(charge_data) > 0:
        try:
            print(f"\nProcessing charge pulses...")
            charge_processed = assign_valid_pulses(charge_data, MAX_REST_DURATION)
            if len(charge_processed) > 0:
                charge_data_rest = compute_V0_t0(charge_processed)
                charge_pulse_nums = sorted([p for p in charge_data_rest['pulse_number'].unique() if p > 0])
                print(f"✓ Found {len(charge_pulse_nums)} valid charge pulses")
            else:
                print(f"⚠  No valid charge pulses found (rest periods too long or too short)")
        except Exception as e:
            print(f"❌ ERROR processing charge pulses: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"⚠  No charge data to process")
    
    # Process discharge pulses with error handling
    if len(discharge_data) > 0:
        try:
            print(f"\nProcessing discharge pulses...")
            discharge_processed = assign_valid_pulses(discharge_data, MAX_REST_DURATION)
            if len(discharge_processed) > 0:
                discharge_data_rest = compute_V0_t0(discharge_processed)
                discharge_pulse_nums = sorted([p for p in discharge_data_rest['pulse_number'].unique() if p > 0])
                print(f"✓ Found {len(discharge_pulse_nums)} valid discharge pulses")
            else:
                print(f"⚠  No valid discharge pulses found (rest periods too long or too short)")
        except Exception as e:
            print(f"❌ ERROR processing discharge pulses: {e}")
            import traceback
            traceback.print_exc()
    else:
        print(f"⚠  No discharge data to process")
    
    # Combine processed data for return
    processed_data_list = []
    if len(charge_data_rest) > 0:
        processed_data_list.append(charge_data_rest)
    if len(discharge_data_rest) > 0:
        processed_data_list.append(discharge_data_rest)
    
    if processed_data_list:
        current_cycle_data = pd.concat(processed_data_list, ignore_index=True)
    else:
        current_cycle_data = pd.DataFrame()
        print(f"\n⚠  WARNING: No valid pulses found in cycle {cycle_num}")
        print(f"   This might be because:")
        print(f"   • Rest periods are > {MAX_REST_DURATION}s (too long)")
        print(f"   • Rest periods are = 0s (no rest between pulses)")
        print(f"   • Cycle structure is unusual")
        return None, [], []
    
    # Set current cycle
    current_cycle = cycle_num
    
    # Summary
    print(f"\n{'='*60}")
    print(f"PULSE ANALYSIS COMPLETE FOR CYCLE {cycle_num}")
    print(f"{'='*60}")
    print(f"✓ Charge pulses: {len(charge_pulse_nums)}")
    if charge_pulse_nums:
        print(f"  └─ Pulse numbers: {charge_pulse_nums}")
    print(f"✓ Discharge pulses: {len(discharge_pulse_nums)}")
    if discharge_pulse_nums:
        print(f"  └─ Pulse numbers: {discharge_pulse_nums}")
    print(f"✓ Total valid pulses: {len(charge_pulse_nums) + len(discharge_pulse_nums)}")
    print(f"{'='*60}\n")
    
    return current_cycle_data, charge_pulse_nums, discharge_pulse_nums

# =============================================================================
# PLOTTING FUNCTIONS
# =============================================================================

def plot_pulse(df, pulse_num, ax, color_v, title_prefix=""):
    """Plot a specific pulse with styling matching Jupyter notebook"""
    pulse_df = df[df['pulse_number'] == pulse_num]
    ax.clear()
    
    if pulse_df.empty:
        ax.text(0.5, 0.5, f"No data for pulse {pulse_num}", ha='center', va='center', transform=ax.transAxes)
        ax.set_title(f"{title_prefix}Pulse {pulse_num} - No Data")
        return None

    # Main voltage plot
    ax.plot(pulse_df['t/s'], pulse_df['E/V'], color=color_v, marker='o', markersize=2, label='Voltage (V)')
    ax.set_xlabel('Absolute Time (s)')
    ax.set_ylabel('Voltage (V)')
    ax.grid(True, alpha=0.3)

    # Relative time axis on top
    pulse_start = pulse_df['t/s'].iloc[0]
    relative_time = pulse_df['t/s'] - pulse_start
    ax_top = ax.twiny()
    ax_top.plot(relative_time, pulse_df['E/V'], alpha=0)
    ax_top.set_xlabel('Relative Time (s)', color='darkblue')
    ax_top.tick_params(axis='x', colors='darkblue')

    # Current overlay on right axis
    ax_curr = ax.twinx()
    ax_curr.plot(pulse_df['t/s'], pulse_df['I/mA'], 'orange', marker='o', 
                linestyle='--', markersize=2, label='Current (mA)', alpha=0.7)
    ax_curr.set_ylabel('Current (mA)', color='orange')
    ax_curr.tick_params(axis='y', colors='orange')

    # V0 marker and rest shading
    if 'V0' in pulse_df.columns and 't0' in pulse_df.columns and not pulse_df['V0'].isna().all():
        V0 = pulse_df['V0'].iloc[0]
        t0 = pulse_df['t0'].iloc[0]
        # Rest period shading
        ax.axvspan(t0, pulse_df['t/s'].iloc[-1], color=color_v, alpha=0.2, label='Rest Period')
        # V0 marker
        ax.plot(t0, V0, 'o', color='green', markersize=8, label=f'V0={V0:.3f}V', zorder=10)

    ax.set_title(f"{title_prefix}Pulse {pulse_num}")
    ax.legend(loc='upper left', fontsize=8)
    
    return pulse_df

def plot_rest_period(pulse_df, ax, color_v):
    """Plot rest period analysis"""
    ax.clear()
    
    if pulse_df is None or pulse_df[pulse_df['I/mA'] == 0].empty:
        ax.text(0.5, 0.5, 'No rest period', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Rest Period - No Data')
        return

    rest_df = pulse_df[pulse_df['I/mA'] == 0]
    if rest_df.empty:
        ax.text(0.5, 0.5, 'No rest period', ha='center', va='center', transform=ax.transAxes)
        ax.set_title('Rest Period - No Data')
        return

    # Rest period relative time
    rest_start = rest_df['t/s'].iloc[0]
    relative_time = rest_df['t/s'] - rest_start

    # Plot rest voltage
    ax.plot(rest_df['t/s'], rest_df['E/V'], color=color_v, marker='o', 
           markersize=2, label='Rest Voltage')
    
    # Relative time axis on top
    ax_top = ax.twiny()
    ax_top.plot(relative_time, rest_df['E/V'], alpha=0)
    ax_top.set_xlabel('Rest Time (s)', color='darkgreen')
    ax_top.tick_params(axis='x', colors='darkgreen')

    # V0 marker and shading
    if 'V0' in pulse_df.columns and 't0' in pulse_df.columns and not pulse_df['V0'].isna().all():
        V0 = pulse_df['V0'].iloc[0]
        t0 = pulse_df['t0'].iloc[0]
        ax.plot(t0, V0, 'o', color='green', markersize=8, label='V0', zorder=10)
        ax.axvspan(t0, rest_df['t/s'].iloc[-1], color=color_v, alpha=0.2)

    # Calculate voltage change during rest
    if len(rest_df) > 1:
        v_start = rest_df['E/V'].iloc[0]
        v_end = rest_df['E/V'].iloc[-1]
        delta_v = v_end - v_start
        duration = rest_df['t/s'].iloc[-1] - rest_df['t/s'].iloc[0]
        ax.set_title(f"Rest Period ({duration:.1f}s, ΔV={delta_v:.3f}V)")
    else:
        ax.set_title("Rest Period")

    ax.set_xlabel('Absolute Time (s)')
    ax.set_ylabel('Voltage (V)', color=color_v)
    ax.tick_params(axis='y', colors=color_v)
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

def plot_cycle_pulse_overview(cycle_data, cycle_num):
    """Plot overview of all pulses in a cycle"""
    if cycle_data is None or len(cycle_data) == 0:
        print("No cycle data to plot")
        return
    
    print(f"Creating pulse overview plot for cycle {cycle_num}")
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 10))
    
    # Get unique pulses
    unique_pulses = sorted([p for p in cycle_data['pulse_number'].unique() if p > 0])
    colors = plt.cm.tab10(np.linspace(0, 1, len(unique_pulses)))
    
    # Plot 1: Voltage vs Time
    for i, pulse_num in enumerate(unique_pulses):
        pulse_data = cycle_data[cycle_data['pulse_number'] == pulse_num]
        color = colors[i % len(colors)]
        ax1.plot(pulse_data['t/s'], pulse_data['E/V'], 
                color=color, label=f'Pulse {pulse_num}', linewidth=2, alpha=0.8)
        
        # Mark V0 points
        if 'V0' in pulse_data.columns and 't0' in pulse_data.columns:
            v0_data = pulse_data.dropna(subset=['V0', 't0'])
            if not v0_data.empty:
                ax1.scatter(v0_data['t0'].iloc[0], v0_data['V0'].iloc[0], 
                          color=color, s=50, marker='s', edgecolor='black', zorder=10)
    
    ax1.set_xlabel('Time (s)')
    ax1.set_ylabel('Voltage (V)')
    ax1.set_title(f'Cycle {cycle_num} - Voltage vs Time (All Pulses)')
    ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax1.grid(True, alpha=0.3)
    
    # Plot 2: Current vs Time with pulse type indication
    for i, pulse_num in enumerate(unique_pulses):
        pulse_data = cycle_data[cycle_data['pulse_number'] == pulse_num]
        color = colors[i % len(colors)]
        avg_current = pulse_data['I/mA'].mean()
        
        # Different line styles for charge vs discharge
        linestyle = '-' if avg_current > 0 else '--'
        alpha = 0.8
            
        ax2.plot(pulse_data['t/s'], pulse_data['I/mA'], 
                color=color, label=f'Pulse {pulse_num}', 
                linewidth=2, alpha=alpha, linestyle=linestyle)
    
    ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
    ax2.set_xlabel('Time (s)')
    ax2.set_ylabel('Current (mA)')
    ax2.set_title(f'Cycle {cycle_num} - Current vs Time (— = Charge, -- = Discharge)')
    ax2.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
    ax2.grid(True, alpha=0.3)
    
    plt.tight_layout()
    plt.show()

def plot_individual_pulse_detailed(pulse_num):
    """Plot detailed view of charge and discharge pulses - 2x2 layout matching Jupyter"""
    global charge_data_rest, discharge_data_rest, current_cycle
    
    print(f"DEBUG: current_cycle = {current_cycle}")
    print(f"DEBUG: charge_data_rest is None: {charge_data_rest is None}")
    print(f"DEBUG: discharge_data_rest is None: {discharge_data_rest is None}")
    
    if charge_data_rest is not None:
        print(f"DEBUG: charge pulse numbers: {sorted(charge_data_rest['pulse_number'].unique())}")
    if discharge_data_rest is not None:
        print(f"DEBUG: discharge pulse numbers: {sorted(discharge_data_rest['pulse_number'].unique())}")
    
    # Create 2x2 layout: rest periods on top, full pulses below
    fig, ((ax_charge_rest, ax_discharge_rest), (ax_charge_main, ax_discharge_main)) = plt.subplots(2, 2, figsize=(16, 10))
    
    # Plot charge pulse (left column)
    if charge_data_rest is not None and pulse_num in charge_data_rest['pulse_number'].values:
        charge_pulse = charge_data_rest[charge_data_rest['pulse_number'] == pulse_num]
        
        # Full pulse plot (bottom left)
        plot_pulse(charge_data_rest, pulse_num, ax_charge_main, 'blue', "Charge ")
        
        # Rest period plot (top left)  
        plot_rest_period(charge_pulse, ax_charge_rest, 'blue')
        
        print(f"DEBUG: Plotted charge pulse {pulse_num}")
    else:
        ax_charge_rest.text(0.5, 0.5, f'No charge pulse {pulse_num}', ha='center', va='center')
        ax_charge_rest.set_title(f'Charge Pulse {pulse_num} - Rest Period')
        ax_charge_main.text(0.5, 0.5, f'No charge pulse {pulse_num}', ha='center', va='center')
        ax_charge_main.set_title(f'Charge Pulse {pulse_num} - No Data')
        print(f"DEBUG: No charge pulse {pulse_num} found")
    
    # Plot discharge pulse (right column)  
    if discharge_data_rest is not None and pulse_num in discharge_data_rest['pulse_number'].values:
        discharge_pulse = discharge_data_rest[discharge_data_rest['pulse_number'] == pulse_num]
        
        # Full pulse plot (bottom right)
        plot_pulse(discharge_data_rest, pulse_num, ax_discharge_main, 'red', "Discharge ")
        
        # Rest period plot (top right)
        plot_rest_period(discharge_pulse, ax_discharge_rest, 'red')
        
        print(f"DEBUG: Plotted discharge pulse {pulse_num}")
    else:
        ax_discharge_rest.text(0.5, 0.5, f'No discharge pulse {pulse_num}', ha='center', va='center')
        ax_discharge_rest.set_title(f'Discharge Pulse {pulse_num} - Rest Period')  
        ax_discharge_main.text(0.5, 0.5, f'No discharge pulse {pulse_num}', ha='center', va='center')
        ax_discharge_main.set_title(f'Discharge Pulse {pulse_num} - No Data')
        print(f"DEBUG: No discharge pulse {pulse_num} found")
    
    plt.tight_layout()
    plt.show()

# =============================================================================
# CONSOLE INTERFACE
# =============================================================================

def console_pulse_interface():
    """Interactive console interface for pulse analysis"""
    global current_cycle, charge_pulse_nums, discharge_pulse_nums
    
    if df_raw is None:
        print("No data loaded. Please run data loading first.")
        return False
    
    print(f"\nPulse Analysis & Visualization")
    print(f"=" * 50)
    print(f"Available cycles: {cycle_list}")
    print(f"\nCommands:")
    print(f"  'cycle X' - Analyze cycle X (e.g., 'cycle 3')")
    print(f"  'overview' - Show pulse overview for current cycle")
    print(f"  'pulse X' - Side-by-side view of charge & discharge pulse X")
    print(f"  'list' - List pulses in current cycle")
    print(f"  'charge' - Show charge pulse data")
    print(f"  'discharge' - Show discharge pulse data")
    print(f"  'help' - Show this help")
    print(f"  'q' - Quit")
    print(f"=" * 50)
    
    while True:
        try:
            user_input = input(f"\nEnter command: ").strip().lower()
            
            if user_input in ['q', 'quit']:
                print("Exiting pulse analysis interface")
                break
                
            elif user_input == 'help':
                print(f"\nAvailable commands:")
                print(f"  Cycle selection: 'cycle 3' (analyze cycle 3)")
                print(f"  Overview plot: 'overview' (current cycle pulse overview)")
                print(f"  Pulse comparison: 'pulse 5' (side-by-side view of charge & discharge pulse 5)")
                print(f"  List pulses: 'list' (show all pulses with counts in current cycle)")
                print(f"  Show data: 'charge' or 'discharge' (show pulse data table)")
                print(f"  Available cycles: {cycle_list}")
                if current_cycle:
                    total_available = len(charge_pulse_nums) + len(discharge_pulse_nums)
                    print(f"  Current cycle: {current_cycle} ({total_available} total pulses)")
                    if charge_pulse_nums or discharge_pulse_nums:
                        all_nums = sorted(set(charge_pulse_nums + discharge_pulse_nums))
                        print(f"  Available pulse numbers: {all_nums}")
                        
            elif user_input.startswith('cycle '):
                try:
                    cycle_num = int(user_input.split()[1])
                    if cycle_num in cycle_list:
                        print(f"Analyzing cycle {cycle_num}...")
                        result_data, charge_pulses, discharge_pulses = analyze_cycle_pulses(cycle_num)
                        
                        if result_data is not None:
                            total_pulses = len(charge_pulses) + len(discharge_pulses)
                            max_pulse_num = max(charge_pulses + discharge_pulses) if (charge_pulses or discharge_pulses) else 0
                            
                            print(f"Cycle {cycle_num} loaded successfully")
                            print(f"  Pulse Summary:")
                            print(f"  Charge pulses: {len(charge_pulses)} - {charge_pulses}")
                            print(f"  Discharge pulses: {len(discharge_pulses)} - {discharge_pulses}")
                            print(f"  Total pulses: {total_pulses}")
                            if max_pulse_num > 0:
                                print(f"  Pulse number range: 1-{max_pulse_num}")
                            print(f"  Use 'pulse X' to see charge & discharge pulse X side-by-side")
                        else:
                            print(f"Failed to analyze cycle {cycle_num}")
                    else:
                        print(f"Cycle {cycle_num} not available. Available: {cycle_list}")
                except (ValueError, IndexError):
                    print("Invalid format. Use 'cycle X' where X is cycle number")
                    
            elif user_input == 'overview':
                if current_cycle and current_cycle_data is not None:
                    plot_cycle_pulse_overview(current_cycle_data, current_cycle)
                else:
                    print("No cycle loaded. Use 'cycle X' to load a cycle first.")
                    
            elif user_input == 'list':
                if current_cycle:
                    total_pulses = len(charge_pulse_nums) + len(discharge_pulse_nums)
                    all_pulse_nums = sorted(set(charge_pulse_nums + discharge_pulse_nums))
                    max_pulse = max(all_pulse_nums) if all_pulse_nums else 0
                    
                    print(f"\nPulses in cycle {current_cycle}:")
                    print(f"  Summary:")
                    print(f"  Total pulses: {total_pulses}")
                    if max_pulse > 0:
                        print(f"  Pulse number range: 1-{max_pulse}")
                    print(f"  Available pulse numbers: {all_pulse_nums}")
                    print(f"\n  By type:")
                    print(f"  Charge pulses ({len(charge_pulse_nums)}): {charge_pulse_nums}")
                    print(f"  Discharge pulses ({len(discharge_pulse_nums)}): {discharge_pulse_nums}")
                    print(f"\n  Use 'pulse X' to see both charge & discharge pulse X side-by-side")
                else:
                    print("No cycle loaded. Use 'cycle X' to load a cycle first.")
                    
            elif user_input == 'charge':
                if current_cycle and charge_data_rest is not None and len(charge_data_rest) > 0:
                    print(f"\nCharge pulse data for cycle {current_cycle}:")
                    print(f"  Pulses: {charge_pulse_nums}")
                    print(f"  Data points: {len(charge_data_rest)}")
                    print(charge_data_rest.head())
                else:
                    print("No charge data available. Load a cycle first.")
                    
            elif user_input == 'discharge':
                if current_cycle and discharge_data_rest is not None and len(discharge_data_rest) > 0:
                    print(f"\nDischarge pulse data for cycle {current_cycle}:")
                    print(f"  Pulses: {discharge_pulse_nums}")
                    print(f"  Data points: {len(discharge_data_rest)}")
                    print(discharge_data_rest.head())
                else:
                    print("No discharge data available. Load a cycle first.")
                    
            elif user_input.startswith('pulse '):
                if current_cycle:
                    try:
                        pulse_num = int(user_input.split()[1])
                        all_pulses = charge_pulse_nums + discharge_pulse_nums
                        if pulse_num in all_pulses or pulse_num in charge_pulse_nums or pulse_num in discharge_pulse_nums:
                            plot_individual_pulse_detailed(pulse_num)
                        else:
                            print(f"Pulse {pulse_num} not found in cycle {current_cycle}")
                            if all_pulses:
                                print(f"Available pulses: {sorted(set(all_pulses))}")
                    except (ValueError, IndexError):
                        print("Invalid format. Use 'pulse X' where X is pulse number")
                else:
                    print("No cycle loaded. Use 'cycle X' to load a cycle first.")
                    
            else:
                print("Invalid command. Type 'help' for available commands.")
                
        except KeyboardInterrupt:
            print("\nExiting pulse analysis interface")
            break
        except Exception as e:
            print(f"Error: {e}")

# =============================================================================
# MAIN EXECUTION FUNCTIONS
# =============================================================================

def run_pulse_analysis():
    """
    Main function to execute pulse analysis functionality
    """
    global df_raw, cycle_list
    
    # Import data from data_loader
    try:
        try:
            from .data_loader import df_raw as loader_df_raw, cycle_list as loader_cycle_list
        except ImportError:
            from data_loader import df_raw as loader_df_raw, cycle_list as loader_cycle_list
        
        if loader_df_raw is None:
            print("No data found from data loader. Please run data loading first.")
            return False
        
        df_raw = loader_df_raw
        cycle_list = loader_cycle_list
        
        print("ICI Battery Analysis - Pulse Analysis")
        print("=" * 60)
        print(f"Imported data from data loader:")
        print(f"   {len(df_raw)} data points")
        print(f"   {len(cycle_list)} cycles: {cycle_list}")
        
        # Launch pulse analysis interface
        console_pulse_interface()
        
        return True
        
    except Exception as e:
        print(f"Error in pulse analysis: {e}")
        return False

def run_cell3():
    """Backward compatibility wrapper"""
    return run_pulse_analysis()

# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Running ICI Battery Analysis - Pulse Analysis Module")
    print("Requires data to be loaded first from data_loader module")
    
    success = run_pulse_analysis()
    if success:
        print("Pulse analysis module completed successfully")
    else:
        print("Pulse analysis module failed")
        print("Make sure data_loader has been executed first!")