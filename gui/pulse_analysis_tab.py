#!/usr/bin/env python3
"""
Pulse Analysis Tab - UPGRADED Version with Smart Export Controls
Tab 3: Enhanced Pulse Analysis & Visualization with Plot-Specific Export

UPGRADES ADDED:
✅ Smart export controls with plot selection dropdown
✅ Automatic plot detection (Overview: 2 plots, Detail: 4 plots)  
✅ Individual subplot export capability
✅ Professional export functionality (width, height, DPI, format)
✅ Three-panel layout: Controls | Export | Results
✅ Maintains all existing functionality
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import os

# Export function (following established pattern)
def export_figure(fig, filepath, width_in=8, height_in=6, dpi=300):
    """Export figure with specified dimensions and DPI - NO TITLES"""
    original_size = fig.get_size_inches()
    
    # Store original titles
    original_titles = []
    for ax in fig.axes:
        original_titles.append(ax.get_title())
        ax.set_title("")  # Remove title for export
    
    try:
        fig.set_size_inches(width_in, height_in)
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
        messagebox.showinfo("Export", f"Figure exported:\n{filepath}")
    except Exception as e:
        messagebox.showerror("Export Error", str(e))
    finally:
        # Restore original size and titles
        fig.set_size_inches(original_size)
        for ax, title in zip(fig.axes, original_titles):
            ax.set_title(title)

class PulseTab:
    """Tab 3: Pulse Analysis & Visualization - UPGRADED with Smart Export"""
    
    def __init__(self, parent, shared_data):
        self.parent = parent
        self.shared_data = shared_data
        
        # Internal data storage
        self.current_cycle = None
        self.charge_data_rest = None
        self.discharge_data_rest = None
        self.charge_pulse_nums = []
        self.discharge_pulse_nums = []
        
        # Track current plot type for refresh and export
        self.current_plot_type = 'overview'  # or 'detail'
        
        self.setup_ui()
        self.load_shared_data()
    
    def setup_ui(self):
        """Create the UI layout - UPGRADED with three-panel export controls"""
        
        # ==============================
        # TOP CONTROLS - THREE-PANEL LAYOUT
        # ==============================
        main_control_frame = ttk.Frame(self.parent)
        main_control_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # ==============================
        # PANEL 1: PULSE ANALYSIS CONTROLS (LEFT)
        # ==============================
        left_frame = ttk.LabelFrame(main_control_frame, text="Pulse Analysis Controls", padding=10)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Cycle selection
        ttk.Label(left_frame, text="Select Cycle:").grid(row=0, column=0, padx=5, pady=2, sticky=tk.W)
        self.cycle_var = tk.StringVar()
        self.cycle_combo = ttk.Combobox(left_frame, textvariable=self.cycle_var, width=15, state='readonly')
        self.cycle_combo.grid(row=0, column=1, padx=5, pady=2, sticky=tk.W)
        
        ttk.Button(left_frame, text="Analyze Pulses", command=self.analyze_pulses).grid(row=0, column=2, padx=5, pady=2)
        
        # Pulse selection
        ttk.Label(left_frame, text="Pulse #:").grid(row=1, column=0, padx=5, pady=2, sticky=tk.W)
        self.pulse_var = tk.IntVar(value=1)
        self.pulse_spinbox = ttk.Spinbox(left_frame, from_=1, to=10, textvariable=self.pulse_var, width=10)
        self.pulse_spinbox.grid(row=1, column=1, padx=5, pady=2, sticky=tk.W)
        
        ttk.Button(left_frame, text="Show Pulse Details", command=self.show_pulse_details).grid(row=1, column=2, padx=5, pady=2)
        
        # Title toggle
        self.show_title_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(left_frame, text="Show plot titles", variable=self.show_title_var, 
                       command=self.refresh_current_plot).grid(row=2, column=0, columnspan=3, padx=5, pady=5, sticky=tk.W)
        
        # ==============================
        # PANEL 2: EXPORT CONTROLS (CENTER)
        # ==============================
        export_frame = ttk.LabelFrame(main_control_frame, text="Export Figure", padding=10)
        export_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5)
        
        # Plot selection dropdown (SMART - updates based on current mode)
        ttk.Label(export_frame, text="Plot to Export:").grid(row=0, column=0, columnspan=2, padx=5, pady=2, sticky=tk.W)
        self.plot_to_export_var = tk.StringVar(value="All Plots")
        self.plot_to_export_combo = ttk.Combobox(export_frame, textvariable=self.plot_to_export_var, 
                                                width=18, state='readonly')
        self.plot_to_export_combo.grid(row=1, column=0, columnspan=2, padx=5, pady=2, sticky=tk.EW)
        
        # Initial plot options (will be updated dynamically)
        self.update_plot_export_options()
        
        # Export dimensions
        ttk.Label(export_frame, text="Width (in):").grid(row=2, column=0, padx=5, pady=2, sticky=tk.W)
        self.export_width_var = tk.DoubleVar(value=8.0)
        ttk.Entry(export_frame, textvariable=self.export_width_var, width=8).grid(row=2, column=1, padx=5, pady=2)
        
        ttk.Label(export_frame, text="Height (in):").grid(row=3, column=0, padx=5, pady=2, sticky=tk.W)
        self.export_height_var = tk.DoubleVar(value=6.0)
        ttk.Entry(export_frame, textvariable=self.export_height_var, width=8).grid(row=3, column=1, padx=5, pady=2)
        
        # DPI and Format
        ttk.Label(export_frame, text="DPI:").grid(row=4, column=0, padx=5, pady=2, sticky=tk.W)
        self.export_dpi_var = tk.IntVar(value=300)
        ttk.Entry(export_frame, textvariable=self.export_dpi_var, width=8).grid(row=4, column=1, padx=5, pady=2)
        
        ttk.Label(export_frame, text="Format:").grid(row=5, column=0, padx=5, pady=2, sticky=tk.W)
        self.export_format_var = tk.StringVar(value="png")
        ttk.Combobox(export_frame, textvariable=self.export_format_var, values=["png", "pdf", "svg"], 
                    width=6, state="readonly").grid(row=5, column=1, padx=5, pady=2)
        
        # Export button
        ttk.Button(export_frame, text="Export", command=self.export_selected_plot).grid(row=6, column=0, columnspan=2, pady=10)
        
        # ==============================
        # PANEL 3: ANALYSIS RESULTS (RIGHT)
        # ==============================
        results_frame = ttk.LabelFrame(main_control_frame, text="Pulse Analysis Results", padding=5)
        results_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        self.results_text = tk.Text(results_frame, height=6, width=45, state='disabled')
        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_text.yview)
        self.results_text.configure(yscrollcommand=scrollbar.set)
        self.results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # ==============================
        # PLOT FRAME - MAXIMIZED
        # ==============================
        plot_frame = ttk.LabelFrame(self.parent, text="Pulse Visualization", padding=5)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.fig = Figure(figsize=(14, 10))
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        
        # Add navigation toolbar for zoom/pan functionality
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        self.toolbar.update()
        
        # Pack in correct order: toolbar at bottom, canvas fills remaining space
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Status bar
        self.bottom_status = ttk.Label(self.parent, text="Ready | Load data to begin", relief=tk.SUNKEN)
        self.bottom_status.pack(fill=tk.X, side=tk.BOTTOM)
    
    def update_plot_export_options(self):
        """Update export dropdown options based on current plot mode"""
        if self.current_plot_type == 'overview':
            # Overview mode: 2 subplots (voltage + current)
            options = [
                "All Plots",
                "Voltage Plot Only", 
                "Current Plot Only"
            ]
        elif self.current_plot_type == 'detail':
            # Detail mode: 4 subplots (2x2 grid)
            options = [
                "All Plots",
                "Charge Rest Period",
                "Discharge Rest Period", 
                "Charge Full Detail",
                "Discharge Full Detail"
            ]
        else:
            # No plots yet
            options = ["No plots available"]
        
        self.plot_to_export_combo['values'] = options
        
        # Keep current selection if still valid, otherwise reset to "All Plots"
        current_selection = self.plot_to_export_var.get()
        if current_selection not in options:
            self.plot_to_export_var.set("All Plots")
    
    def export_selected_plot(self):
        """Export the selected plot with smart subplot extraction"""
        if self.fig is None or len(self.fig.axes) == 0:
            messagebox.showwarning("No Plot", "No plot available to export")
            return
        
        # Get export settings
        plot_selection = self.plot_to_export_var.get()
        width = self.export_width_var.get()
        height = self.export_height_var.get()
        dpi = self.export_dpi_var.get()
        fmt = self.export_format_var.get()
        
        # File dialog
        filepath = filedialog.asksaveasfilename(
            title="Export Pulse Analysis Plot",
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")],
            initialdir=self.shared_data.get('last_folder', os.path.expanduser("~"))
        )
        
        if not filepath:
            return
        
        # Remember folder for next time
        self.shared_data['last_folder'] = os.path.dirname(filepath)
        
        try:
            if plot_selection == "All Plots":
                # Export entire current figure
                export_figure(self.fig, filepath, width_in=width, height_in=height, dpi=dpi)
                
            else:
                # Export individual subplot
                target_ax = self.get_target_subplot(plot_selection)
                if target_ax is not None:
                    self.export_individual_subplot(target_ax, filepath, width, height, dpi)
                else:
                    messagebox.showwarning("Plot Not Found", f"Could not find plot: {plot_selection}")
                    return
            
            self.update_status(f"Exported: {os.path.basename(filepath)}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting plot:\n{str(e)}")
            self.update_status("Export failed", error=True)
            import traceback
            traceback.print_exc()
    
    def get_target_subplot(self, plot_selection):
        """Get the target subplot based on selection and current mode"""
        axes = self.fig.axes
        
        if self.current_plot_type == 'overview' and len(axes) >= 2:
            # Overview mode: 2 subplots
            if plot_selection == "Voltage Plot Only":
                return axes[0]  # Top subplot (voltage)
            elif plot_selection == "Current Plot Only":
                return axes[1]  # Bottom subplot (current)
                
        elif self.current_plot_type == 'detail' and len(axes) >= 4:
            # Detail mode: 4 subplots in 2x2 grid
            # Order: [top-left, top-right, bottom-left, bottom-right]
            if plot_selection == "Charge Rest Period":
                return axes[0]  # Top-left
            elif plot_selection == "Discharge Rest Period":
                return axes[1]  # Top-right
            elif plot_selection == "Charge Full Detail":
                return axes[2]  # Bottom-left
            elif plot_selection == "Discharge Full Detail":
                return axes[3]  # Bottom-right
        
        return None
    
    def export_individual_subplot(self, source_ax, filepath, width_in, height_in, dpi):
        """Export a single subplot as a standalone figure"""
        # Create new figure for the individual subplot
        temp_fig, temp_ax = plt.subplots(figsize=(width_in, height_in))
        
        try:
            # Copy all plot elements from source to temp axis
            self.copy_axis_content(source_ax, temp_ax)
            
            # Save the temporary figure
            temp_fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
            
            messagebox.showinfo("Export", f"Plot exported:\n{filepath}")
            
        finally:
            # Clean up temporary figure
            plt.close(temp_fig)
    
    def copy_axis_content(self, source_ax, target_ax):
        """Copy all content from source axis to target axis"""
        # Copy lines
        for line in source_ax.get_lines():
            target_ax.plot(line.get_xdata(), line.get_ydata(),
                          color=line.get_color(), linewidth=line.get_linewidth(),
                          linestyle=line.get_linestyle(), marker=line.get_marker(),
                          markersize=line.get_markersize(), alpha=line.get_alpha(),
                          label=line.get_label())
        
        # Copy scatter plots
        for collection in source_ax.collections:
            if hasattr(collection, 'get_offsets') and len(collection.get_offsets()) > 0:
                offsets = collection.get_offsets()
                colors = collection.get_facecolors()
                sizes = collection.get_sizes()
                target_ax.scatter(offsets[:, 0], offsets[:, 1], 
                                c=colors, s=sizes, alpha=collection.get_alpha())
        
        # Copy spans (axvspan)
        for patch in source_ax.patches:
            if hasattr(patch, 'get_x') and hasattr(patch, 'get_width'):
                x = patch.get_x()
                width = patch.get_width()
                target_ax.axvspan(x, x + width, color=patch.get_facecolor(), 
                                alpha=patch.get_alpha())
        
        # Copy horizontal/vertical lines
        for line in source_ax.get_lines():
            if hasattr(line, '_x') and len(line._x) == 2:
                if line._x[0] == line._x[1]:  # Vertical line
                    target_ax.axvline(line._x[0], color=line.get_color(), 
                                    linestyle=line.get_linestyle(), alpha=line.get_alpha())
                elif line._y[0] == line._y[1]:  # Horizontal line
                    target_ax.axhline(line._y[0], color=line.get_color(),
                                    linestyle=line.get_linestyle(), alpha=line.get_alpha())
        
        # Copy formatting
        target_ax.set_xlabel(source_ax.get_xlabel(), fontsize=source_ax.xaxis.label.get_fontsize())
        target_ax.set_ylabel(source_ax.get_ylabel(), fontsize=source_ax.yaxis.label.get_fontsize())
        #target_ax.set_title(source_ax.get_title(), fontsize=source_ax.title.get_fontsize())
        target_ax.set_xlim(source_ax.get_xlim())
        target_ax.set_ylim(source_ax.get_ylim())
        target_ax.grid(source_ax.get_xgridlines()[0].get_visible() if source_ax.get_xgridlines() else False, 
                      alpha=0.3)
        
        # Copy legend
        if source_ax.get_legend():
            target_ax.legend(loc='best')
    
    # ==============================
    # ORIGINAL FUNCTIONALITY (PRESERVED)
    # ==============================
    
    def load_shared_data(self):
        """Load available cycles from shared data"""
        try:
            # Get df_raw and cycle_list from shared_data (standard workflow)
            if 'df_raw' not in self.shared_data or self.shared_data['df_raw'] is None:
                self.update_status("No data loaded. Please load data in Tab 1 first.", error=True)
                return
            
            df_raw = self.shared_data['df_raw']
            cycle_list = self.shared_data.get('cycle_list', [])
            
            if len(cycle_list) == 0:
                # Try to get cycles from df_raw if cycle_list is empty
                cycle_list = sorted(df_raw['cycle'].unique().tolist())
            
            self.cycle_combo['values'] = [f"Cycle {c}" for c in cycle_list]
            
            if len(cycle_list) > 0:
                self.cycle_combo.current(0)
                self.update_status(f"Loaded {len(cycle_list)} cycles")
            else:
                self.update_status("No cycles found", error=True)
                
        except Exception as e:
            self.update_status(f"Error loading data: {str(e)}", error=True)
            import traceback
            traceback.print_exc()
    
    def refresh_current_plot(self):
        """Refresh the current plot when title toggle changes"""
        if self.current_plot_type == 'overview':
            self.plot_pulse_overview_fixed()
        elif self.current_plot_type == 'detail':
            self.show_pulse_details()
    
    def analyze_pulses(self):
        """Analyze pulses in selected cycle"""
        try:
            cycle_str = self.cycle_var.get()
            if not cycle_str:
                messagebox.showwarning("No Selection", "Please select a cycle first")
                return
            
            cycle_num = int(cycle_str.split()[-1])
            self.current_cycle = cycle_num
            
            self.update_status(f"Analyzing cycle {cycle_num}...")
            
            # Get df_raw from shared_data
            df_raw = self.shared_data['df_raw']
            cycle_data = df_raw[df_raw['cycle'] == cycle_num].copy()
            
            if len(cycle_data) == 0:
                self.update_status(f"No data for cycle {cycle_num}", error=True)
                return
            
            # CRITICAL: Sync data to pulse_analyzer module BEFORE calling analyze_cycle_pulses
            from analysis import pulse_analyzer
            pulse_analyzer.df_raw = df_raw
            pulse_analyzer.cycle_list = self.shared_data.get('cycle_list', sorted(df_raw['cycle'].unique().tolist()))
            
            # Run pulse analysis
            result_data, charge_pulses, discharge_pulses = pulse_analyzer.analyze_cycle_pulses(cycle_num)
            
            # Store results - GET FROM GLOBAL VARIABLES in pulse_analyzer module!
            self.charge_data_rest = pulse_analyzer.charge_data_rest
            self.discharge_data_rest = pulse_analyzer.discharge_data_rest
            self.charge_pulse_nums = charge_pulses
            self.discharge_pulse_nums = discharge_pulses
            
            # Update pulse spinbox range
            all_pulse_nums = sorted(set(charge_pulses + discharge_pulses))
            if all_pulse_nums:
                self.pulse_spinbox.config(from_=min(all_pulse_nums), to=max(all_pulse_nums))
            
            # Display results
            self.display_analysis_summary()
            
            # Plot overview - FIXED: Show full continuous cycle data
            self.current_plot_type = 'overview'
            self.plot_pulse_overview_fixed()
            
            # UPDATE EXPORT OPTIONS for new plot mode
            self.update_plot_export_options()
            
            # CRITICAL FIX: Force canvas update
            self.canvas.draw_idle()
            self.parent.update_idletasks()
            
            self.update_status(f"Analyzed cycle {cycle_num}: {len(charge_pulses)} charge + {len(discharge_pulses)} discharge pulses")
            
        except Exception as e:
            self.update_status(f"Analysis error: {str(e)}", error=True)
            import traceback
            traceback.print_exc()
    
    def display_analysis_summary(self):
        """Display pulse analysis summary in text widget"""
        results = []
        results.append(f"PULSE ANALYSIS - CYCLE {self.current_cycle}")
        results.append("=" * 80)
        
        charge_pulses = self.charge_pulse_nums
        discharge_pulses = self.discharge_pulse_nums
        
        results.append(f"\nCHARGE PULSES: {len(charge_pulses)}")
        if charge_pulses:
            results.append(f"   Pulse numbers: {charge_pulses}")
        
        results.append(f"\nDISCHARGE PULSES: {len(discharge_pulses)}")
        if discharge_pulses:
            results.append(f"   Pulse numbers: {discharge_pulses}")
        
        # Show V0 values if available
        if self.charge_data_rest is not None and len(self.charge_data_rest) > 0 and 'V0' in self.charge_data_rest.columns:
            charge_v0s = []
            for pulse_num in charge_pulses:
                pulse_data = self.charge_data_rest[self.charge_data_rest['pulse_number'] == pulse_num]
                if len(pulse_data) > 0 and not pulse_data['V0'].isna().all():
                    v0 = pulse_data['V0'].iloc[0]
                    charge_v0s.append(f"P{pulse_num}:{v0:.3f}V")
            if charge_v0s:
                results.append(f"\nCharge V0 values: {', '.join(charge_v0s)}")
        
        if self.discharge_data_rest is not None and len(self.discharge_data_rest) > 0 and 'V0' in self.discharge_data_rest.columns:
            discharge_v0s = []
            for pulse_num in discharge_pulses:
                pulse_data = self.discharge_data_rest[self.discharge_data_rest['pulse_number'] == pulse_num]
                if len(pulse_data) > 0 and not pulse_data['V0'].isna().all():
                    v0 = pulse_data['V0'].iloc[0]
                    discharge_v0s.append(f"P{pulse_num}:{v0:.3f}V")
            if discharge_v0s:
                results.append(f"\nDischarge V0 values: {', '.join(discharge_v0s)}")
        
        results.append(f"\nUse the 'Pulse #' selector and 'Show Pulse Details' to view individual pulses")
        
        self.results_text.config(state='normal')
        self.results_text.delete(1.0, tk.END)
        self.results_text.insert(1.0, '\n'.join(results))
        self.results_text.config(state='disabled')
    
    def plot_pulse_overview_fixed(self):
        """FIXED: Plot full continuous cycle data like Tab 1 (not individual pulses)"""
        self.fig.clear()
        
        if self.current_cycle is None:
            return
        
        # Get the FULL cycle data from df_raw (like Tab 1 does)
        df_raw = self.shared_data['df_raw']
        cycle_data = df_raw[df_raw['cycle'] == self.current_cycle].copy()
        
        if len(cycle_data) == 0:
            return
        
        # Create 2 subplots
        ax1 = self.fig.add_subplot(211)
        ax2 = self.fig.add_subplot(212)
        
        # Check if cycle has 'phase' column (from classification tab)
        # If not, use charge_data_rest and discharge_data_rest to identify phases
        if 'phase' in cycle_data.columns or 'cycle_phase' in cycle_data.columns:
            # Use existing phase classification
            phase_col = 'phase' if 'phase' in cycle_data.columns else 'cycle_phase'
            charge_data = cycle_data[cycle_data[phase_col] == 'charge']
            discharge_data = cycle_data[cycle_data[phase_col] == 'discharge']
            rest_data = cycle_data[cycle_data[phase_col] == 'rest']
        else:
            # No phase column - separate by current sign
            charge_data = cycle_data[cycle_data['I/mA'] > 0]
            discharge_data = cycle_data[cycle_data['I/mA'] < 0]
            rest_data = cycle_data[cycle_data['I/mA'] == 0]
        
        # Plot 1: Voltage vs Time (continuous lines)
        if len(charge_data) > 0:
            ax1.plot(charge_data['t/s'], charge_data['E/V'], 
                    color='blue', label='Charge', linewidth=2)
        
        if len(discharge_data) > 0:
            ax1.plot(discharge_data['t/s'], discharge_data['E/V'], 
                    color='red', label='Discharge', linewidth=2)
        
        if len(rest_data) > 0:
            ax1.plot(rest_data['t/s'], rest_data['E/V'], 
                    color='green', label='Rest', linewidth=2, alpha=0.6)
        
        # Mark V0 points if available
        if self.charge_data_rest is not None and 'V0' in self.charge_data_rest.columns:
            v0_data = self.charge_data_rest.dropna(subset=['V0', 't0'])
            if len(v0_data) > 0:
                ax1.scatter(v0_data['t0'], v0_data['V0'], 
                          color='green', s=30, marker='o', edgecolor='black', 
                          label='V0 (charge)', zorder=10)
        
        if self.discharge_data_rest is not None and 'V0' in self.discharge_data_rest.columns:
            v0_data = self.discharge_data_rest.dropna(subset=['V0', 't0'])
            if len(v0_data) > 0:
                ax1.scatter(v0_data['t0'], v0_data['V0'], 
                          color='darkgreen', s=30, marker='s', edgecolor='black', 
                          label='V0 (discharge)', zorder=10)
        
        ax1.set_xlabel('Time (s)', fontsize=11)
        ax1.set_ylabel('Voltage (V)', fontsize=11)
        
        # Conditional title
        if self.show_title_var.get():
            ax1.set_title(f'Cycle {self.current_cycle} - Voltage Profile', fontsize=12, fontweight='bold')
        
        # Draggable legend with visibility
        legend = ax1.legend(loc='best', fontsize=10)
        legend.set_draggable(True)
        legend.set_zorder(100)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_alpha(0.9)
        legend.get_frame().set_edgecolor('black')
        
        ax1.grid(True, alpha=0.3)
        
        # Plot 2: Current vs Time (continuous lines)
        if len(charge_data) > 0:
            ax2.plot(charge_data['t/s'], charge_data['I/mA'], 
                    color='blue', label='Charge', linewidth=2)
        
        if len(discharge_data) > 0:
            ax2.plot(discharge_data['t/s'], discharge_data['I/mA'], 
                    color='red', label='Discharge', linewidth=2)
        
        if len(rest_data) > 0:
            ax2.plot(rest_data['t/s'], rest_data['I/mA'], 
                    color='green', label='Rest', linewidth=2, alpha=0.6)
        
        ax2.axhline(y=0, color='black', linestyle='-', alpha=0.5)
        ax2.set_xlabel('Time (s)', fontsize=11)
        ax2.set_ylabel('Current (mA)', fontsize=11)
        
        # Conditional title
        if self.show_title_var.get():
            ax2.set_title(f'Cycle {self.current_cycle} - Current Profile', fontsize=12, fontweight='bold')
        
        # Draggable legend with visibility
        legend = ax2.legend(loc='best', fontsize=10)
        legend.set_draggable(True)
        legend.set_zorder(100)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_alpha(0.9)
        legend.get_frame().set_edgecolor('black')
        
        ax2.grid(True, alpha=0.3)
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def show_pulse_details(self):
        """Show detailed view of selected pulse (charge and discharge side-by-side)"""
        if self.current_cycle is None:
            messagebox.showwarning("No Cycle", "Please analyze a cycle first")
            return
        
        pulse_num = self.pulse_var.get()
        self.current_plot_type = 'detail'
        
        # Clear and create 2x2 subplot layout
        self.fig.clear()
        
        ax_charge_rest = self.fig.add_subplot(221)
        ax_discharge_rest = self.fig.add_subplot(222)
        ax_charge_main = self.fig.add_subplot(223)
        ax_discharge_main = self.fig.add_subplot(224)
        
        # Plot charge pulse (left column)
        has_charge = False
        if self.charge_data_rest is not None and pulse_num in self.charge_data_rest['pulse_number'].values:
            charge_pulse = self.charge_data_rest[self.charge_data_rest['pulse_number'] == pulse_num]
            has_charge = True
            
            self.plot_pulse_detail(charge_pulse, ax_charge_main, 'blue', f'Charge Pulse {pulse_num}')
            self.plot_rest_period(charge_pulse, ax_charge_rest, 'blue', f'Charge P{pulse_num} - Rest')
        else:
            ax_charge_rest.text(0.5, 0.5, f'No charge pulse {pulse_num}', ha='center', va='center')
            if self.show_title_var.get():
                ax_charge_rest.set_title(f'Charge Pulse {pulse_num} - Rest Period')
            ax_charge_main.text(0.5, 0.5, f'No charge pulse {pulse_num}', ha='center', va='center')
            if self.show_title_var.get():
                ax_charge_main.set_title(f'Charge Pulse {pulse_num}')
        
        # Plot discharge pulse (right column)
        has_discharge = False
        if self.discharge_data_rest is not None and pulse_num in self.discharge_data_rest['pulse_number'].values:
            discharge_pulse = self.discharge_data_rest[self.discharge_data_rest['pulse_number'] == pulse_num]
            has_discharge = True
            
            self.plot_pulse_detail(discharge_pulse, ax_discharge_main, 'red', f'Discharge Pulse {pulse_num}')
            self.plot_rest_period(discharge_pulse, ax_discharge_rest, 'red', f'Discharge P{pulse_num} - Rest')
        else:
            ax_discharge_rest.text(0.5, 0.5, f'No discharge pulse {pulse_num}', ha='center', va='center')
            if self.show_title_var.get():
                ax_discharge_rest.set_title(f'Discharge Pulse {pulse_num} - Rest Period')
            ax_discharge_main.text(0.5, 0.5, f'No discharge pulse {pulse_num}', ha='center', va='center')
            if self.show_title_var.get():
                ax_discharge_main.set_title(f'Discharge Pulse {pulse_num}')
        
        if not has_charge and not has_discharge:
            messagebox.showinfo("No Data", f"Pulse {pulse_num} not found in this cycle")
        
        # UPDATE EXPORT OPTIONS for new plot mode
        self.update_plot_export_options()
        
        self.fig.tight_layout()
        self.canvas.draw()
    
    def plot_pulse_detail(self, pulse_df, ax, color, title):
        """Plot detailed pulse with dual axis (voltage + current)"""
        if pulse_df is None or len(pulse_df) == 0:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            return
        
        # Voltage on left axis
        ax.plot(pulse_df['t/s'], pulse_df['E/V'], color=color, linewidth=2, label='Voltage')
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Voltage (V)', color=color)
        ax.tick_params(axis='y', labelcolor=color)
        
        # Current on right axis
        ax2 = ax.twinx()
        ax2.plot(pulse_df['t/s'], pulse_df['I/mA'], color='orange', linewidth=1.5, 
                linestyle='--', label='Current', alpha=0.7)
        ax2.set_ylabel('Current (mA)', color='orange')
        ax2.tick_params(axis='y', labelcolor='orange')
        
        # V0 marker
        if 'V0' in pulse_df.columns and 't0' in pulse_df.columns:
            v0_data = pulse_df.dropna(subset=['V0', 't0'])
            if not v0_data.empty:
                ax.plot(v0_data['t0'].iloc[0], v0_data['V0'].iloc[0], 
                       'o', color='green', markersize=10, label='V0', zorder=10)
        
        # Conditional title
        if self.show_title_var.get():
            ax.set_title(title, fontweight='bold')
        
        ax.grid(True, alpha=0.3)
        
        # Merged draggable legend
        handles1, labels1 = ax.get_legend_handles_labels()
        handles2, labels2 = ax2.get_legend_handles_labels()
        legend = ax.legend(handles1 + handles2, labels1 + labels2, loc='best', fontsize=8)
        legend.set_draggable(True)
        legend.set_zorder(100)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_alpha(0.9)
        legend.get_frame().set_edgecolor('black')
    
    def plot_rest_period(self, pulse_df, ax, color, title):
        """Plot rest period analysis"""
        if pulse_df is None or len(pulse_df) == 0:
            ax.text(0.5, 0.5, 'No data', ha='center', va='center', transform=ax.transAxes)
            return
        
        rest_df = pulse_df[pulse_df['I/mA'] == 0]
        if rest_df.empty:
            ax.text(0.5, 0.5, 'No rest period', ha='center', va='center', transform=ax.transAxes)
            return
        
        # Plot rest voltage
        ax.plot(rest_df['t/s'], rest_df['E/V'], color=color, marker='o', 
               markersize=3, label='Rest Voltage', linewidth=1.5)
        
        # V0 marker
        if 'V0' in pulse_df.columns and 't0' in pulse_df.columns:
            v0_data = pulse_df.dropna(subset=['V0', 't0'])
            if not v0_data.empty:
                V0 = v0_data['V0'].iloc[0]
                t0 = v0_data['t0'].iloc[0]
                ax.plot(t0, V0, 'o', color='green', markersize=8, label='V0', zorder=10)
                ax.axvspan(t0, rest_df['t/s'].iloc[-1], color=color, alpha=0.15)
        
        # Calculate rest duration
        if len(rest_df) > 1:
            duration = rest_df['t/s'].iloc[-1] - rest_df['t/s'].iloc[0]
            # Conditional title with duration only
            if self.show_title_var.get():
                ax.set_title(f"{title} ({duration:.1f}s)", fontweight='bold')
        else:
            # Conditional title
            if self.show_title_var.get():
                ax.set_title(title, fontweight='bold')
        
        ax.set_xlabel('Time (s)')
        ax.set_ylabel('Voltage (V)', color=color)
        ax.tick_params(axis='y', labelcolor=color)
        
        # Draggable legend with visibility
        legend = ax.legend(fontsize=8)
        legend.set_draggable(True)
        legend.set_zorder(100)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_alpha(0.9)
        legend.get_frame().set_edgecolor('black')
        
        ax.grid(True, alpha=0.3)
    
    def update_status(self, message, error=False):
        """Update the bottom status bar"""
        if error:
            self.bottom_status.config(text=f"ERROR: {message}", foreground='red')
        else:
            self.bottom_status.config(text=message, foreground='black')