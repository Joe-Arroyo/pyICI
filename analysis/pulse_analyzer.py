#!/usr/bin/env python3
"""
ICI Battery Analysis - Pulse Analyzer Module
Pulse assignment, V0/t0 computation, and per-cycle pulse analysis.
Pure analysis layer: functions take data as arguments and return results.
"""

# =============================================================================
# IMPORTS
# =============================================================================

import numpy as np
import pandas as pd
from collections import namedtuple

# =============================================================================
# CONFIGURATION
# =============================================================================

MAX_REST_DURATION = 1800  # seconds

# =============================================================================
# RESULT TYPE
# =============================================================================

PulseAnalysis = namedtuple(
    "PulseAnalysis",
    ["cycle", "charge_data", "charge_pulses", "discharge_data", "discharge_pulses"],
)


def _empty_analysis(cycle_num):
    """A PulseAnalysis with no pulses (used for the no-usable-data paths)."""
    return PulseAnalysis(cycle_num, pd.DataFrame(), [], pd.DataFrame(), [])


# =============================================================================
# PULSE ASSIGNMENT FUNCTIONS
# =============================================================================

def assign_valid_pulses(df, max_rest=MAX_REST_DURATION):
    """
    Assign pulse numbers to valid pulses based on rest duration
    Returns dataframe with only valid pulses (pulse_number > 0)
    """
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

    return valid_df

def compute_V0_t0(df):
    """
    Compute V0 and t0 for each pulse
    V0 = voltage at end of active period
    t0 = time at end of active period
    """
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

    return df

# =============================================================================
# PHASE CLASSIFICATION FUNCTIONS
# =============================================================================

def get_phase_classifier():
    """Get phase classification function with fallback"""
    try:
        from .phase_classifier import classify_charge_discharge
        return classify_charge_discharge
    except ImportError:
        try:
            from phase_classifier import classify_charge_discharge
            return classify_charge_discharge
        except ImportError:
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
# MAIN ANALYSIS FUNCTION
# =============================================================================

def analyze_cycle_pulses(df_raw, cycle_num):
    """
    Analyze all pulses in one cycle.

    Returns a PulseAnalysis: per-phase DataFrames (each carrying pulse_number,
    V0, t0, rest) and the valid pulse-number lists. On any path with no usable
    charge/discharge data the DataFrames are empty and the lists are empty.
    """
    if df_raw is None:
        return _empty_analysis(cycle_num)

    cycle_data = df_raw[df_raw['cycle'] == cycle_num].copy()
    if len(cycle_data) == 0:
        return _empty_analysis(cycle_num)

    # Phase classification (with a fallback classifier)
    if 'cycle_phase' not in cycle_data.columns:
        try:
            classify_func = get_phase_classifier()
            cycle_data['cycle_phase'] = classify_func(cycle_data)
        except Exception:
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
            except Exception:
                return _empty_analysis(cycle_num)

    if 'cycle_phase' not in cycle_data.columns:
        return _empty_analysis(cycle_num)

    # Separate by phase
    charge_data = cycle_data[cycle_data['cycle_phase'] == 'charge'].copy()
    discharge_data = cycle_data[cycle_data['cycle_phase'] == 'discharge'].copy()

    if len(charge_data) == 0 and len(discharge_data) == 0:
        return _empty_analysis(cycle_num)

    charge_data_rest = pd.DataFrame()
    discharge_data_rest = pd.DataFrame()
    charge_pulse_nums = []
    discharge_pulse_nums = []

    # Process charge pulses (isolated so a failure in one phase doesn't stop the other)
    if len(charge_data) > 0:
        try:
            charge_processed = assign_valid_pulses(charge_data, MAX_REST_DURATION)
            if len(charge_processed) > 0:
                charge_data_rest = compute_V0_t0(charge_processed)
                charge_pulse_nums = sorted([int(p) for p in charge_data_rest['pulse_number'].unique() if p > 0])
        except Exception:
            pass

    # Process discharge pulses
    if len(discharge_data) > 0:
        try:
            discharge_processed = assign_valid_pulses(discharge_data, MAX_REST_DURATION)
            if len(discharge_processed) > 0:
                discharge_data_rest = compute_V0_t0(discharge_processed)
                discharge_pulse_nums = sorted([int(p) for p in discharge_data_rest['pulse_number'].unique() if p > 0])
        except Exception:
            pass

    return PulseAnalysis(cycle_num, charge_data_rest, charge_pulse_nums,
                         discharge_data_rest, discharge_pulse_nums)