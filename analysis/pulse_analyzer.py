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

# Single source of truth for pulse segmentation (F1): assign_valid_pulses and
# compute_V0_t0 live in analysis.regression_analyzer (the same implementations
# the R/k pipeline uses). Imported here so the Pulse tab segments pulses exactly
# as the exported R/k results do.
from analysis.regression_analyzer import assign_valid_pulses, compute_V0_t0
from analysis.phase_classifier import MAX_REST_DURATION  # single source of truth


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
# PULSE ASSIGNMENT  (single source of truth — see import at top of module)
# =============================================================================
# assign_valid_pulses and compute_V0_t0 are imported from
# analysis.regression_analyzer (F1: one implementation, imported everywhere).
# analyze_cycle_pulses below adapts their output to the shape the Pulse tab
# expects (valid rows only, plus a boolean `rest` column).

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
            # canonical assign_valid_pulses returns the full frame; keep valid pulses only
            charge_processed = charge_processed[charge_processed['pulse_number'] > 0].copy()
            if len(charge_processed) > 0:
                charge_data_rest = compute_V0_t0(charge_processed)
                charge_data_rest['rest'] = (charge_data_rest['I/mA'] == 0)
                charge_pulse_nums = sorted([int(p) for p in charge_data_rest['pulse_number'].unique() if p > 0])
        except Exception:
            pass

    # Process discharge pulses
    if len(discharge_data) > 0:
        try:
            discharge_processed = assign_valid_pulses(discharge_data, MAX_REST_DURATION)
            # canonical assign_valid_pulses returns the full frame; keep valid pulses only
            discharge_processed = discharge_processed[discharge_processed['pulse_number'] > 0].copy()
            if len(discharge_processed) > 0:
                discharge_data_rest = compute_V0_t0(discharge_processed)
                discharge_data_rest['rest'] = (discharge_data_rest['I/mA'] == 0)
                discharge_pulse_nums = sorted([int(p) for p in discharge_data_rest['pulse_number'].unique() if p > 0])
        except Exception:
            pass

    return PulseAnalysis(cycle_num, charge_data_rest, charge_pulse_nums,
                         discharge_data_rest, discharge_pulse_nums)