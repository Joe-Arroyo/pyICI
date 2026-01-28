#!/usr/bin/env python3
"""
ICI Battery Analysis - Kinetic Analyzer Module (Cell 5)
R & k Parameter Extraction with Error Propagation
"""

import numpy as np
import pandas as pd
import os
import warnings
warnings.filterwarnings('ignore')

from analysis.regression_analyzer import (
    classify_charge_discharge,
    assign_valid_pulses,
    compute_V0_t0,
    get_V0,
    compute_single_pulse_regression,
    DEFAULT_R1_START,
    DEFAULT_R1_LENGTH,
    MAX_REST_DURATION
)

DEFAULT_R1S = DEFAULT_R1_START
DEFAULT_R1L = DEFAULT_R1_LENGTH

df_raw = None
cycle_list = []

def get_pre_pulse_currents(data, pulse_numbers):
    currents = []
    voltages = []
    
    for pulse_num in pulse_numbers:
        pulse_data = data[data['pulse_number'] == pulse_num]
        rest_data = pulse_data[pulse_data['I/mA'] == 0]
        
        if rest_data.empty:
            currents.append(np.nan)
            voltages.append(np.nan)
            continue
        
        first_rest_idx = rest_data.index[0]
        pulse_data_idx = data.index.get_loc(first_rest_idx)
        prev_idx = pulse_data_idx - 1
        
        if prev_idx < 0:
            currents.append(np.nan)
            voltages.append(np.nan)
            continue
        
        current_mA = data.iloc[prev_idx]['I/mA']
        voltage_V = data.iloc[prev_idx]['E/V']
        
        currents.append(current_mA / 1000.0)
        voltages.append(voltage_V)
    
    return np.array(currents), np.array(voltages)

def compute_regression_with_covariance(data, pulse_num, r1s, r1l):
    pulse_data = data[data['pulse_number'] == pulse_num]
    rest_data = pulse_data[pulse_data['I/mA'] == 0].copy()
    
    if len(rest_data) < r1s + r1l:
        return {'pulse': pulse_num, 'r2': np.nan, 'slope': np.nan, 'intercept': np.nan, 'cov': None, 'V0': np.nan}
    
    V0 = get_V0(data, pulse_num)
    if np.isnan(V0):
        return {'pulse': pulse_num, 'r2': np.nan, 'slope': np.nan, 'intercept': np.nan, 'cov': None, 'V0': V0}
    
    rest_data['ΔV'] = rest_data['E/V'] - V0
    rest_data['sqrt_time'] = np.sqrt(rest_data['t/s'].values - rest_data['t/s'].values[0])
    
    result = compute_single_pulse_regression(rest_data, r1s, r1l)
    result['pulse'] = pulse_num
    result['V0'] = V0
    
    return result

def compute_R_k(data, pulse_numbers, regression_results):
    currents, voltages = get_pre_pulse_currents(data, pulse_numbers)
    
    R_vals = []
    R_errs = []
    k_vals = []
    k_errs = []
    
    for i, result in enumerate(regression_results):
        intercept = result.get('intercept', np.nan)
        slope = result.get('slope', np.nan)
        cov = result.get('cov', None)
        current = currents[i]
        
        if current == 0 or np.isnan(current) or np.isnan(intercept) or np.isnan(slope):
            R_vals.append(np.nan)
            R_errs.append(np.nan)
            k_vals.append(np.nan)
            k_errs.append(np.nan)
            continue
        
        R_val = -intercept / current
        k_val = -slope / current
        
        if cov is not None and cov.shape == (2, 2):
            slope_err = np.sqrt(cov[0, 0])
            intercept_err = np.sqrt(cov[1, 1])
            R_err = abs(R_val) * (intercept_err / abs(intercept)) if intercept != 0 else np.nan
            k_err = abs(k_val) * (slope_err / abs(slope)) if slope != 0 else np.nan
        else:
            R_err = np.nan
            k_err = np.nan
        
        R_vals.append(R_val)
        R_errs.append(R_err)
        k_vals.append(k_val)
        k_errs.append(k_err)
    
    return voltages, (np.array(R_vals), np.array(R_errs)), (np.array(k_vals), np.array(k_errs))

def compute_R_k_for_cycle(cycle_num, phase, r1s=DEFAULT_R1S, r1l=DEFAULT_R1L, saved_params=None):
    if df_raw is None:
        return None
    
    cycle_df = df_raw[df_raw['cycle'] == cycle_num].copy()
    
    if 'cycle_phase' not in cycle_df.columns:
        cycle_df['cycle_phase'] = classify_charge_discharge(cycle_df)
    
    phase_df = cycle_df[cycle_df['cycle_phase'] == phase].copy()
    
    if len(phase_df) == 0:
        return None
    
    phase_data = assign_valid_pulses(phase_df, MAX_REST_DURATION)
    
    if len(phase_data) == 0:
        return None
    
    phase_data = compute_V0_t0(phase_data)
    pulse_nums = [p for p in phase_data['pulse_number'].unique() if p > 0]
    
    if not pulse_nums:
        return None
    
    regression_results = []
    
    for pulse_num in pulse_nums:
        if saved_params:
            key = f"{cycle_num}_{phase}_{pulse_num}"
            if key in saved_params:
                use_r1s = saved_params[key]['r1s']
                use_r1l = saved_params[key]['r1l']
            else:
                use_r1s = r1s
                use_r1l = r1l
        else:
            use_r1s = r1s
            use_r1l = r1l
        
        result = compute_regression_with_covariance(phase_data, pulse_num, use_r1s, use_r1l)
        regression_results.append(result)
    
    voltages, (R_vals, R_errs), (k_vals, k_errs) = compute_R_k(phase_data, pulse_nums, regression_results)
    
    return {
        'voltages': voltages,
        'R': R_vals,
        'R_err': R_errs,
        'k': k_vals,
        'k_err': k_errs,
        'pulse_nums': pulse_nums,
        'r2': [result['r2'] for result in regression_results]
    }

def compute_R_k_for_cycles(cycle_nums, phase, r1s=DEFAULT_R1S, r1l=DEFAULT_R1L, saved_params=None):
    results = []
    
    for cycle_num in cycle_nums:
        result = compute_R_k_for_cycle(cycle_num, phase, r1s, r1l, saved_params)
        if result:
            result['cycle'] = cycle_num
            results.append(result)
    
    return results

def export_R_k_results(cycle_nums, r1s=DEFAULT_R1S, r1l=DEFAULT_R1L, saved_params=None, output_folder="exports", filename_prefix=""):
    if df_raw is None:
        print("❌ No data loaded")
        return False
    
    try:
        os.makedirs(output_folder, exist_ok=True)
        exported_files = []

        # Create prefix for filename (add underscore if prefix exists)
        prefix = f"{filename_prefix}_" if filename_prefix else ""

        
        for phase in ['charge', 'discharge']:
            all_data = []
            
            for cycle_num in cycle_nums:
                result = compute_R_k_for_cycle(cycle_num, phase, r1s, r1l, saved_params)
                
                if result:
                    for i in range(len(result['voltages'])):
                        all_data.append({
                            'Cycle': cycle_num,
                            'Pulse_Number': result['pulse_nums'][i],
                            'Voltage (V)': result['voltages'][i],
                            'R (Ohm)': result['R'][i],
                            'R_err (Ohm)': result['R_err'][i],
                            'k (Ohm·s^0.5)': result['k'][i],
                            'k_err (Ohm·s^0.5)': result['k_err'][i],
                            'R2': result['r2'][i]
                        })
            
            if all_data:
                df_export = pd.DataFrame(all_data)
                filename = f'{prefix}R_k_results_{phase}.csv'
                output_path = os.path.join(output_folder, filename)
                df_export.to_csv(output_path, index=False)
                exported_files.append(filename)
                print(f"✅ Exported {len(all_data)} {phase} results to: {output_path}")
        
        return len(exported_files) > 0
        
    except Exception as e:
        print(f"❌ Export error: {e}")
        return False

def parse_cycle_input(input_str, available_cycles):
    if not input_str.strip():
        return []
    
    cycles = []
    
    try:
        parts = input_str.replace(" ", "").split(",")
        
        for part in parts:
            if not part:
                continue
            
            if "-" in part:
                range_parts = part.split("-")
                if len(range_parts) == 2:
                    start, end = int(range_parts[0]), int(range_parts[1])
                    if start <= end:
                        cycles.extend(range(start, end + 1))
            else:
                cycles.append(int(part))
        
        valid_cycles = [c for c in cycles if c in available_cycles]
        return sorted(list(set(valid_cycles)))
        
    except Exception as e:
        print(f"❌ Error parsing cycles: {e}")
        return []

def run_kinetic_analysis(df_input=None, interactive=True):
    global df_raw, cycle_list
    
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
    print("⚗️ R & k KINETIC ANALYSIS MODULE")
    print("="*70)
    print(f"✅ Data loaded: {len(df_raw)} points across {len(cycle_list)} cycles")
    print(f"Available cycles: {cycle_list}")
    print(f"Default parameters: R1S={DEFAULT_R1S}, R1L={DEFAULT_R1L}")
    
    if not interactive:
        return True
    
    print("\nConsole interface not implemented. Use GUI for R & k analysis.")
    return True

if __name__ == "__main__":
    run_kinetic_analysis()