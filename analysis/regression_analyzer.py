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

