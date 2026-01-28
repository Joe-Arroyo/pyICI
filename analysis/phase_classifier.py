#!/usr/bin/env python3
"""
ICI Battery Analysis - Phase Classifier Module
Interactive Data Classification & Visualization with Multi-Cycle Support
Fixed to match original cell2 behavior exactly
"""

# =============================================================================
# PHASE CLASSIFICATION & VISUALIZATION MODULE
# =============================================================================

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import ipywidgets as widgets
from IPython.display import display, clear_output
import os

# =============================================================================
# CONFIGURATION
# =============================================================================

# Analysis parameters
MAX_REST_DURATION = 1800  # seconds

# Global variables (will be set from data_loader)
df_raw = None
cycle_list = []

# =============================================================================
# CORE CLASSIFICATION FUNCTIONS
# =============================================================================

def classify_charge_discharge(df, current_col='I/mA'):
    """Classify data points as charge, discharge, or rest based on current direction"""
    current = df[current_col].values
    labels = np.empty(len(current), dtype=object)
    
    print(f"🔍 Classifying {len(current)} data points by current direction...")
    
    i = 0
    charge_count = 0
    discharge_count = 0
    rest_count = 0
    
    while i < len(current):
        if current[i] > 0:
            # Positive current = charge
            start = i
            while i < len(current) and current[i] >= 0:
                i += 1
            labels[start:i] = 'charge'
            charge_count += (i - start)
        elif current[i] < 0:
            # Negative current = discharge
            start = i
            while i < len(current) and current[i] <= 0:
                i += 1
            labels[start:i] = 'discharge'
            discharge_count += (i - start)
        else:
            # Current is zero - assign same as previous or 'rest'
            labels[i] = 'rest' if i == 0 else labels[i-1]
            if labels[i] == 'rest':
                rest_count += 1
            i += 1
    
    # Handle None values (convert to 'rest')
    labels = np.where(labels == None, 'rest', labels)
    
    print(f"✅ Classification completed:")
    print(f"   • Charge points: {charge_count} ({charge_count/len(current)*100:.1f}%)")
    print(f"   • Discharge points: {discharge_count} ({discharge_count/len(current)*100:.1f}%)")
    print(f"   • Rest points: {rest_count} ({rest_count/len(current)*100:.1f}%)")
    
    return labels

def parse_cycles(input_str, available_cycles):
    """Parse cycle input string into list of cycle numbers"""
    try:
        input_str = input_str.strip()
        if not input_str:
            return []
        
        cycles = []
        parts = input_str.split(',')
        
        for part in parts:
            part = part.strip()
            if '-' in part:
                # Range like "1-5"
                start, end = map(int, part.split('-'))
                cycles.extend(range(start, end + 1))
            else:
                # Single number
                cycles.append(int(part))
        
        # Filter to only available cycles
        valid_cycles = [c for c in cycles if c in available_cycles]
        return sorted(list(set(valid_cycles)))
        
    except Exception as e:
        print(f"❌ Error parsing cycles: {e}")
        return []

def validate_cycle_input(input_str, available_cycles):
    """Validate cycle input and return parsed cycles"""
    cycles = parse_cycles(input_str, available_cycles)
    
    if not cycles:
        print(f"❌ No valid cycles found in input: '{input_str}'")
        print(f"Available cycles: {available_cycles}")
        return []
    
    invalid_cycles = [c for c in cycles if c not in available_cycles]
    if invalid_cycles:
        print(f"⚠️ Invalid cycles will be ignored: {invalid_cycles}")
    
    valid_cycles = [c for c in cycles if c in available_cycles]
    
    if valid_cycles:
        print(f"✅ Selected cycles: {valid_cycles}")
    
    return valid_cycles

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

def plot_classification_overview(selected_cycles, df_raw):
    """Plot classification overview matching original behavior"""
    if not selected_cycles or df_raw is None:
        print("❌ No data to plot")
        return
    
    print(f"📈 Creating classification overview for {len(selected_cycles)} cycles...")
    
    if len(selected_cycles) == 1:
        # Single cycle mode - matches original exactly
        plot_single_cycle_classification(selected_cycles[0], df_raw)
    else:
        # Multi-cycle mode - matches original exactly
        plot_multi_cycle_comparison(selected_cycles, df_raw)

def plot_single_cycle_classification(cycle_num, df_raw):
    """Single cycle plot with all data points - no downsampling"""
    cycle_data = df_raw[df_raw['cycle'] == cycle_num].copy()
    
    if len(cycle_data) == 0:
        print(f"❌ No data for cycle {cycle_num}")
        return
    
    print(f"📊 Creating single cycle classification plot for cycle {cycle_num}...")
    print(f"   Using all {len(cycle_data)} data points (no downsampling)")
    
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
        print(f"   Plotted all {len(charge_data)} charge points")
    if len(discharge_data) > 0:
        ax_class.plot(discharge_data['t/s'], discharge_data['E/V'], 'r-o', 
                     label='Discharge Voltage', markersize=2, alpha=0.8)
        print(f"   Plotted all {len(discharge_data)} discharge points")
    if len(rest_data) > 0:
        # Plot rest data points in gray for complete visualization
        ax_class.plot(rest_data['t/s'], rest_data['E/V'], 'gray', 
                     label='Rest Voltage', markersize=1, alpha=0.6)
        print(f"   Plotted all {len(rest_data)} rest points")
    
    # Plot ALL current data on secondary axis
    ax_current.plot(cycle_data['t/s'], cycle_data['I/mA'], '--o', 
                   color='orange', label='Current (mA)', markersize=2, alpha=0.8)
    ax_current.axhline(0, color='darkgrey', linestyle=':', alpha=0.6, linewidth=1)
    ax_current.set_ylabel('Current (mA)', color='orange', fontsize=12)
    ax_current.tick_params(axis='y', labelcolor='orange')
    ax_current.yaxis.tick_right()
    ax_current.yaxis.set_label_position('right')
    
    # Highlight short rests using ALL data
    print(f"   Analyzing rest periods with all data points...")
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
    
    # Complete statistics display
    total_time = cycle_data['t/s'].max() - cycle_data['t/s'].min()
    print(f"\n📊 Complete Cycle {cycle_num} Statistics:")
    print(f"   • Data source: {data_source}")
    print(f"   • Total duration: {total_time:.1f} seconds")
    print(f"   • Total data points: {len(cycle_data)} (all analyzed)")
    print(f"   • Voltage range: {cycle_data['E/V'].min():.3f} - {cycle_data['E/V'].max():.3f} V")
    print(f"   • Current range: {cycle_data['I/mA'].min():.2f} - {cycle_data['I/mA'].max():.2f} mA")
    
    # Count exact zero current points
    exact_zero_points = len(cycle_data[cycle_data['I/mA'] == 0])
    if exact_zero_points > 0:
        print(f"   • Points with I=0: {exact_zero_points} ({exact_zero_points/len(cycle_data)*100:.1f}%)")
    else:
        print(f"   • No points with exactly I=0 found")

def plot_multi_cycle_comparison(selected_cycles, df_raw):
    """Multi-cycle plot with all data points - no downsampling"""
    fig, ax_class = plt.subplots(figsize=(14, 8))
    
    print(f"📊 Creating multi-cycle plot with all data points...")
    
    # Use viridis colormap
    cmap = plt.colormaps['viridis']
    total_points = 0
    
    for i, cycle_num in enumerate(selected_cycles):
        cycle_data = df_raw[df_raw['cycle'] == cycle_num].copy()
        
        if len(cycle_data) == 0:
            continue
        
        # Find cycle start (first non-zero current)
        first_nonzero_idx = cycle_data[cycle_data['I/mA'] != 0].index
        if len(first_nonzero_idx) > 0:
            cycle_start_time = cycle_data.loc[first_nonzero_idx[0], 't/s']
        else:
            cycle_start_time = cycle_data['t/s'].min()
        
        # Normalize time to start from cycle start
        cycle_data['time_norm'] = cycle_data['t/s'] - cycle_start_time
        
        # NO DOWNSAMPLING - use all data points
        total_points += len(cycle_data)
        print(f"   Cycle {cycle_num}: {len(cycle_data)} points")
        
        # Color per cycle
        color_intensity = 0.3 + 0.7 * (i / max(1, len(selected_cycles) - 1))
        cycle_color = cmap(color_intensity)
        
        # Plot entire cycle with all data points
        ax_class.plot(cycle_data['time_norm'], cycle_data['E/V'], '-o', 
                     color=cycle_color, label=f'Cycle {cycle_num}', 
                     linewidth=1, alpha=0.8, markersize=1)
    
    print(f"   Total plotted points: {total_points}")
    
    # Multi-cycle title
    cycles_display = ', '.join(map(str, selected_cycles[:8]))
    if len(selected_cycles) > 8:
        cycles_display += f' ... (+{len(selected_cycles)-8} more)'
    ax_class.set_title(f'Multi-Cycle Comparison - Complete Data ({len(selected_cycles)} Cycles)\n'
                      f'Cycles: {cycles_display} | Total Points: {total_points}', 
                      fontsize=12, fontweight='bold')
    
    # Formatting
    ax_class.set_xlabel('Time (s)', fontsize=12)
    ax_class.set_ylabel('Voltage (V)', fontsize=12)
    ax_class.grid(True, alpha=0.3)
    
    # Legend below plot
    ax_class.legend(loc='upper center', bbox_to_anchor=(0.5, -0.1), 
                   ncol=min(len(selected_cycles), 6), fontsize=10)
    
    plt.tight_layout()
    plt.show()

def plot_detailed_cycle(cycle_num, df_raw):
    """Plot detailed view of a single cycle - enhanced version"""
    if df_raw is None:
        print("❌ No data loaded")
        return
    
    # Use the single cycle plot function for consistency
    plot_single_cycle_classification(cycle_num, df_raw)

# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

def export_cycle_data(selected_cycles, df_raw, output_folder="exports"):
    """Export classified cycle data to CSV"""
    if not selected_cycles or df_raw is None:
        print("❌ No data to export")
        return False
    
    try:
        # Create output folder if it doesn't exist
        os.makedirs(output_folder, exist_ok=True)
        
        exported_files = []
        
        print(f"📁 Exporting classified data for {len(selected_cycles)} cycles...")
        
        for cycle_num in selected_cycles:
            cycle_data = df_raw[df_raw['cycle'] == cycle_num].copy()
            
            if len(cycle_data) == 0:
                print(f"⚠️ No data for cycle {cycle_num}")
                continue
            
            # Add classification like original
            cycle_data['cycle_phase'] = classify_charge_discharge(cycle_data)
            
            # Export filename
            filename = f"cycle_{cycle_num}_classified.csv"
            output_path = os.path.join(output_folder, filename)
            
            # Export to CSV
            cycle_data.to_csv(output_path, index=False)
            exported_files.append(filename)
            print(f"✅ Exported: {output_path}")
        
        if exported_files:
            print(f"\n📄 Exported {len(exported_files)} files to '{output_folder}/' folder:")
            for filename in exported_files:
                print(f"   • {filename}")
            return True
        else:
            print("❌ No files were exported")
            return False
            
    except Exception as e:
        print(f"❌ Export error: {e}")
        return False

# =============================================================================
# INTERACTIVE CONSOLE INTERFACE
# =============================================================================

def console_classification_interface():
    """Console interface for data classification"""
    global df_raw, cycle_list
    
    if df_raw is None:
        print("❌ No data loaded. Please run data loading first.")
        return False
    
    print(f"\n🔍 Phase Classification & Visualization")
    print(f"=" * 50)
    print(f"Available cycles: {cycle_list}")
    print(f"\nCommands:")
    print(f"  • Enter cycle range (e.g., '1-3', '1,3,5', '2')")
    print(f"  • 'all' - Select all cycles")
    print(f"  • 'detail X' - Detailed view of cycle X")
    print(f"  • 'export' - Export classified data")
    print(f"  • 'help' - Show this help")
    print(f"  • 'q' - Quit")
    print(f"=" * 50)
    
    selected_cycles = []
    
    while True:
        try:
            user_input = input(f"\n🎯 Enter command: ").strip().lower()
            
            if user_input == 'q' or user_input == 'quit':
                print("👋 Exiting classification interface")
                break
            elif user_input == 'help':
                print(f"\n📋 Available commands:")
                print(f"  • Cycle selection: '1', '1-5', '1,3,7', 'all'")
                print(f"  • Detailed view: 'detail 3' (shows cycle 3 in detail)")
                print(f"  • Export data: 'export' (exports currently selected cycles)")
                print(f"  • Available cycles: {cycle_list}")
            elif user_input == 'all':
                selected_cycles = cycle_list.copy()
                print(f"✅ Selected all cycles: {selected_cycles}")
                plot_classification_overview(selected_cycles, df_raw)
            elif user_input.startswith('detail '):
                try:
                    cycle_num = int(user_input.split()[1])
                    if cycle_num in cycle_list:
                        print(f"📊 Showing detailed view for cycle {cycle_num}")
                        plot_detailed_cycle(cycle_num, df_raw)
                    else:
                        print(f"❌ Cycle {cycle_num} not available. Available: {cycle_list}")
                except (ValueError, IndexError):
                    print("❌ Invalid format. Use 'detail X' where X is cycle number")
            elif user_input == 'export':
                if selected_cycles:
                    success = export_cycle_data(selected_cycles, df_raw)
                    if success:
                        print(f"✅ Export completed for cycles: {selected_cycles}")
                    else:
                        print(f"❌ Export failed")
                else:
                    print("❌ No cycles selected. Please select cycles first.")
            else:
                # Try to parse as cycle selection
                parsed_cycles = validate_cycle_input(user_input, cycle_list)
                if parsed_cycles:
                    selected_cycles = parsed_cycles
                    print(f"✅ Selected cycles: {selected_cycles}")
                    plot_classification_overview(selected_cycles, df_raw)
                else:
                    print("❌ Invalid input. Type 'help' for available commands.")
                    
        except KeyboardInterrupt:
            print("\n👋 Exiting classification interface")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

# =============================================================================
# MAIN EXECUTION FUNCTION
# =============================================================================

def run_phase_classification():
    """
    Main function to execute phase classification functionality
    """
    global df_raw, cycle_list
    
    # Import data from data_loader (updated import)
    try:
        from .data_loader import df_raw as loader_df_raw, cycle_list as loader_cycle_list
        
        if loader_df_raw is None:
            print("❌ No data found from data loader. Please run data loading first.")
            return False
        
        df_raw = loader_df_raw
        cycle_list = loader_cycle_list
        
        print("🔍 ICI Battery Analysis - Phase Classification")
        print("=" * 60)
        print(f"✅ Imported data from data loader:")
        print(f"   • {len(df_raw)} data points")
        print(f"   • {len(cycle_list)} cycles: {cycle_list}")
        print(f"   • Columns: {list(df_raw.columns)}")
        
        # Verify we have the expected E/V column
        if 'E/V' not in df_raw.columns:
            print("❌ Expected 'E/V' column not found in data")
            print(f"Available columns: {list(df_raw.columns)}")
            return False
        
        # Launch classification interface
        console_classification_interface()
        
        return True
        
    except ImportError as e:
        print("❌ Could not import data from data_loader")
        print("💡 Make sure to run data loading first!")
        print(f"Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Error in phase classification: {e}")
        import traceback
        traceback.print_exc()
        return False

# =============================================================================
# BACKWARD COMPATIBILITY FUNCTIONS
# =============================================================================

def run_cell2():
    """
    Backward compatibility wrapper - calls run_phase_classification
    """
    return run_phase_classification()

# =============================================================================
# STANDALONE EXECUTION
# =============================================================================

if __name__ == "__main__":
    print("Running ICI Battery Analysis - Phase Classification Module")
    print("Requires data to be loaded first from data_loader module")
    
    success = run_phase_classification()
    if success:
        print("✅ Phase classification module completed successfully")
    else:
        print("❌ Phase classification module failed")
        print("💡 Make sure data_loader has been executed first!")