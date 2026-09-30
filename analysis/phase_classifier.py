#!/usr/bin/env python3
"""
ICI Battery Analysis - Phase Classifier Module
Charge/discharge/rest classification and capacity calculation, plus the
single-cycle classification plot used by the Classification tab.
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# =============================================================================
# CONFIGURATION
# =============================================================================

MAX_REST_DURATION = 1800  # seconds

# =============================================================================
# CORE CLASSIFICATION FUNCTIONS
# =============================================================================

def classify_charge_discharge(df, current_col='I/mA'):
    """Classify data points as charge, discharge, or rest based on current direction"""
    current = df[current_col].values
    labels = np.empty(len(current), dtype=object)

    i = 0
    while i < len(current):
        if current[i] > 0:
            # Positive current = charge
            start = i
            while i < len(current) and current[i] >= 0:
                i += 1
            labels[start:i] = 'charge'
        elif current[i] < 0:
            # Negative current = discharge
            start = i
            while i < len(current) and current[i] <= 0:
                i += 1
            labels[start:i] = 'discharge'
        else:
            # Current is zero - assign same as previous or 'rest'
            labels[i] = 'rest' if i == 0 else labels[i-1]
            i += 1

    # Handle None values (convert to 'rest')
    labels = np.where(labels == None, 'rest', labels)

    return labels

# =============================================================================
# CAPACITY CALCULATION
# =============================================================================

def calculate_capacity(data, mass_mg):
    """Calculate capacity from current integration with reset at each phase change.

    Shared by the Classification tab (Capacity vs Voltage) and the Kinetics tab
    (R/k vs Capacity) so both compute capacity the same way from the same function.
    """
    data = data.copy()

    # Ensure we have phase classification
    if 'cycle_phase' not in data.columns:
        data['cycle_phase'] = classify_charge_discharge(data)

    # Create segment_id: increments each time phase changes
    data['segment_id'] = (data['cycle_phase'] != data['cycle_phase'].shift()).cumsum()

    # Calculate time differences
    data['dt'] = data['t/s'].diff().fillna(0)

    # Reset dt to 0 at the start of every new segment to prevent large jumps between cycles/phases
    data.loc[data['segment_id'] != data['segment_id'].shift(), 'dt'] = 0

    # Calculate dQ (mAh)
    data['dQ'] = data['I/mA'].abs() * data['dt'] / 3600

    # Calculate capacity resetting at each phase (charge/discharge/rest starts at 0)
    data['capacity_mAh'] = data.groupby('segment_id')['dQ'].cumsum()

    # Calculate specific capacity if mass provided (NaN when no mass, so it's
    # correctly excluded by NaN-based filtering downstream rather than
    # silently plotting a degenerate x=0 point)
    if mass_mg > 0:
        data['specific_capacity'] = data['capacity_mAh'] / (mass_mg / 1000)
    else:
        data['specific_capacity'] = np.nan

    return data

# =============================================================================
# VISUALIZATION FUNCTIONS
# =============================================================================

def highlight_short_rests(df_phase, ax, color, max_duration=MAX_REST_DURATION):
    """Highlight short rest periods in the plot - matches original implementation"""
    if len(df_phase) == 0:
        return

    # Create I_zero column like original (exactly I/mA == 0)
    df_phase = df_phase.copy()
    df_phase['I_zero'] = df_phase['I/mA'] == 0

    rests = df_phase['I_zero'].values
    times = df_phase['t/s'].values  # Use our standard column name

    i = 0
    while i < len(rests):
        if rests[i]:  # If current is zero
            start_time = times[i]
            while i < len(rests) and rests[i]:
                i += 1
            end_time = times[i-1]
            # Highlight if rest duration <= max_duration
            if (end_time - start_time) <= max_duration:
                ax.axvspan(start_time, end_time, color=color, alpha=0.3)
        else:
            i += 1

def plot_single_cycle_classification(cycle_num, df_raw):
    """Single cycle plot with all data points - no downsampling"""
    cycle_data = df_raw[df_raw['cycle'] == cycle_num].copy()

    if len(cycle_data) == 0:
        return

    # Add classification and I_zero column
    cycle_data['cycle_phase'] = classify_charge_discharge(cycle_data)
    cycle_data['I_zero'] = cycle_data['I/mA'] == 0

    # Create figure with dual y-axis
    fig, ax_class = plt.subplots(figsize=(14, 8))
    ax_current = ax_class.twinx()

    # Split data by phase - NO DOWNSAMPLING
    charge_data = cycle_data[cycle_data['cycle_phase'] == 'charge'].copy()
    discharge_data = cycle_data[cycle_data['cycle_phase'] == 'discharge'].copy()
    rest_data = cycle_data[cycle_data['cycle_phase'] == 'rest'].copy()

    # Plot ALL voltage data points: Charge=Blue, Discharge=Red
    if len(charge_data) > 0:
        ax_class.plot(charge_data['t/s'], charge_data['E/V'], 'b-o',
                     label='Charge Voltage', markersize=2, alpha=0.8)
    if len(discharge_data) > 0:
        ax_class.plot(discharge_data['t/s'], discharge_data['E/V'], 'r-o',
                     label='Discharge Voltage', markersize=2, alpha=0.8)
    if len(rest_data) > 0:
        # Plot rest data points in gray for complete visualization
        ax_class.plot(rest_data['t/s'], rest_data['E/V'], 'gray',
                     label='Rest Voltage', markersize=1, alpha=0.6)

    # Plot ALL current data on secondary axis
    ax_current.plot(cycle_data['t/s'], cycle_data['I/mA'], '--o',
                   color='orange', label='Current (mA)', markersize=2, alpha=0.8)
    ax_current.axhline(0, color='darkgrey', linestyle=':', alpha=0.6, linewidth=1)
    ax_current.set_ylabel('Current (mA)', color='orange', fontsize=12)
    ax_current.tick_params(axis='y', labelcolor='orange')
    ax_current.yaxis.tick_right()
    ax_current.yaxis.set_label_position('right')

    # Highlight short rests using ALL data
    if len(charge_data) > 0:
        highlight_short_rests(charge_data, ax_class, 'blue')
    if len(discharge_data) > 0:
        highlight_short_rests(discharge_data, ax_class, 'red')
    if len(rest_data) > 0:
        highlight_short_rests(rest_data, ax_class, 'gray')

    # Title with complete statistics
    charge_points = len(cycle_data[cycle_data['cycle_phase'] == 'charge'])
    discharge_points = len(cycle_data[cycle_data['cycle_phase'] == 'discharge'])
    rest_points = len(cycle_data[cycle_data['cycle_phase'] == 'rest'])

    # Enhanced title with data completeness indication
    data_source = "Single-Cycle File" if len(df_raw['cycle'].unique()) == 1 else "Multi-Cycle File"
    ax_class.set_title(f'Cycle {cycle_num} - Complete Data Analysis ({data_source})\n'
                      f'Charge: {charge_points} pts | Discharge: {discharge_points} pts | Rest: {rest_points} pts',
                      fontsize=12, fontweight='bold')

    # Formatting
    ax_class.set_xlabel('Time (s)', fontsize=12)
    ax_class.set_ylabel('Voltage (V)', fontsize=12)
    ax_class.grid(True, alpha=0.3)
    ax_class.legend(loc='lower left', fontsize=11)
    ax_current.legend(loc='upper right', fontsize=11)

    plt.tight_layout()
    plt.show()