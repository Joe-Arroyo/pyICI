#!/usr/bin/env python3
"""
ICI Battery Analysis - Regression Tab (Tab 4)
R² Regression Analysis with Time-Based Selection
Features:
- Time-based window selection (0.1s to 5s default)
- Dynamic limits based on actual rest duration
- Side-by-side Charge/Discharge display
- Parameter persistence across cycles
- Optional plot titles
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
import os

# Import regression analyzer
import analysis.regression_analyzer as ra

class RegressionTab:
    """Regression Analysis Tab - Tab 4"""

    def __init__(self, parent, shared_data):
        self.parent = parent
        self.shared_data = shared_data

        # Local data
        self.df_raw = None
        self.cycle_list = []
        self.current_cycle = None
        self.charge_pulse_nums = []
        self.discharge_pulse_nums = []
        self.charge_data_pulse = pd.DataFrame()
        self.discharge_data_pulse = pd.DataFrame()

        # R² values
        self.charge_r2_values = []
        self.discharge_r2_values = []

        # Current indices
        self.current_charge_idx = 0
        self.current_discharge_idx = 0
        
        # Spinbox references (for dynamic limit updates)
        self.start_time_charge_spinbox = None
        self.end_time_charge_spinbox = None
        self.start_time_discharge_spinbox = None
        self.end_time_discharge_spinbox = None

        # Create UI
        self.create_interface()

        # Load data
        self.load_shared_data()

    def create_interface(self):
        """Create the main interface with top controls and two tabs"""

        # Top control bar
        control_frame = ttk.Frame(self.parent)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        ttk.Label(control_frame, text="Cycle:").pack(side=tk.LEFT, padx=5)
        self.cycle_combo = ttk.Combobox(control_frame, width=10, state='readonly')
        self.cycle_combo.pack(side=tk.LEFT, padx=5)
        self.cycle_combo.bind('<<ComboboxSelected>>', self.on_cycle_change)

        ttk.Button(control_frame, text="Load Cycle", 
                  command=self.load_current_cycle).pack(side=tk.LEFT, padx=5)
        ttk.Button(control_frame, text="Analyze All Cycles", 
                  command=self.analyze_all_cycles).pack(side=tk.LEFT, padx=20)
        
        # Title toggle checkbox
        self.show_title_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(control_frame, text="Show plot titles", 
                       variable=self.show_title_var,
                       command=self.refresh_plots).pack(side=tk.LEFT, padx=20)

        self.show_time_axis_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(control_frame, text="Show time axis on top", 
               variable=self.show_time_axis_var,
               command=self.refresh_plots).pack(side=tk.LEFT, padx=5)

        # Notebook with two tabs
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Tab 1: Single Cycle Analysis
        self.single_cycle_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.single_cycle_frame, text="Single Cycle Analysis")
        self.create_single_cycle_tab()

        # Tab 2: Multi-Cycle Analysis
        self.multi_cycle_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.multi_cycle_frame, text="Multi-Cycle Analysis")
        self.create_multi_cycle_tab()

    def create_single_cycle_tab(self):
        """Create single cycle analysis tab with charge/discharge side by side"""

        # Left: Charge Analysis
        left_frame = ttk.LabelFrame(self.single_cycle_frame, text="Charge Analysis")
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.create_phase_controls(left_frame, "charge")

        # Right: Discharge Analysis
        right_frame = ttk.LabelFrame(self.single_cycle_frame, text="Discharge Analysis")
        right_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.create_phase_controls(right_frame, "discharge")

    def create_phase_controls(self, parent, phase):
        """Create controls and plots for a phase (charge or discharge)"""

        # Control frame
        ctrl_frame = ttk.Frame(parent)
        ctrl_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)

        # Pulse navigation
        nav_frame = ttk.Frame(ctrl_frame)
        nav_frame.pack(fill=tk.X, pady=2)

        if phase == "charge":
            ttk.Button(nav_frame, text="◀", width=3,
                      command=self.prev_charge_pulse).pack(side=tk.LEFT)
            self.charge_pulse_label = ttk.Label(nav_frame, text="Pulse: -", anchor=tk.CENTER)
            self.charge_pulse_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            ttk.Button(nav_frame, text="▶", width=3,
                      command=self.next_charge_pulse).pack(side=tk.RIGHT)
        else:
            ttk.Button(nav_frame, text="◀", width=3,
                      command=self.prev_discharge_pulse).pack(side=tk.LEFT)
            self.discharge_pulse_label = ttk.Label(nav_frame, text="Pulse: -", anchor=tk.CENTER)
            self.discharge_pulse_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
            ttk.Button(nav_frame, text="▶", width=3,
                      command=self.next_discharge_pulse).pack(side=tk.RIGHT)

        # Time window controls
        start_frame = ttk.Frame(ctrl_frame)
        start_frame.pack(fill=tk.X, pady=2)
        
        ttk.Label(start_frame, text="Start (s):").pack(side=tk.LEFT, padx=2)

        if phase == "charge":
            self.start_time_charge_var = tk.DoubleVar(value=0.1)
            self.start_time_charge_spinbox = ttk.Spinbox(
                start_frame, 
                from_=0.0, 
                to=100.0,  # Initial max, will be updated dynamically
                increment=0.1,
                textvariable=self.start_time_charge_var, 
                width=8, 
                format="%.2f"
            )
            self.start_time_charge_spinbox.pack(side=tk.LEFT, padx=2)
        else:
            self.start_time_discharge_var = tk.DoubleVar(value=0.1)
            self.start_time_discharge_spinbox = ttk.Spinbox(
                start_frame, 
                from_=0.0, 
                to=100.0,
                increment=0.1,
                textvariable=self.start_time_discharge_var, 
                width=8, 
                format="%.2f"
            )
            self.start_time_discharge_spinbox.pack(side=tk.LEFT, padx=2)

        ttk.Label(start_frame, text="End (s):").pack(side=tk.LEFT, padx=(10,2))

        if phase == "charge":
            self.end_time_charge_var = tk.DoubleVar(value=1.0)
            self.end_time_charge_spinbox = ttk.Spinbox(
                start_frame, 
                from_=0.0, 
                to=100.0,  # Initial max, will be updated dynamically
                increment=0.1,
                textvariable=self.end_time_charge_var, 
                width=8, 
                format="%.2f"
            )
            self.end_time_charge_spinbox.pack(side=tk.LEFT, padx=2)
        else:
            self.end_time_discharge_var = tk.DoubleVar(value=1.0)
            self.end_time_discharge_spinbox = ttk.Spinbox(
                start_frame, 
                from_=0.0, 
                to=100.0,
                increment=0.1,
                textvariable=self.end_time_discharge_var, 
                width=8, 
                format="%.2f"
            )
            self.end_time_discharge_spinbox.pack(side=tk.LEFT, padx=2)

        # Create side-by-side layout: Controls (left) | Export (right)
        controls_export_frame = ttk.Frame(ctrl_frame)
        controls_export_frame.pack(fill=tk.X, pady=5)
        
        # Create export variables first (needed for both panels)
        if phase == "charge":
            self.charge_export_plot_var = tk.StringVar(value="Both Plots")
            self.export_width_charge_var = tk.DoubleVar(value=6.0)
            self.export_height_charge_var = tk.DoubleVar(value=8.0)
            self.export_dpi_charge_var = tk.IntVar(value=300)
            self.export_format_charge_var = tk.StringVar(value="png")
            plot_var = self.charge_export_plot_var
            width_var = self.export_width_charge_var
            height_var = self.export_height_charge_var
            dpi_var = self.export_dpi_charge_var
            format_var = self.export_format_charge_var
        else:
            self.discharge_export_plot_var = tk.StringVar(value="Both Plots")
            self.export_width_discharge_var = tk.DoubleVar(value=6.0)
            self.export_height_discharge_var = tk.DoubleVar(value=8.0)
            self.export_dpi_discharge_var = tk.IntVar(value=300)
            self.export_format_discharge_var = tk.StringVar(value="png")
            plot_var = self.discharge_export_plot_var
            width_var = self.export_width_discharge_var
            height_var = self.export_height_discharge_var
            dpi_var = self.export_dpi_discharge_var
            format_var = self.export_format_discharge_var
        
        # LEFT: Controls panel
        controls_panel = ttk.LabelFrame(controls_export_frame, text="Controls", padding=5)
        controls_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Controls row 1
        ctrl_row1 = ttk.Frame(controls_panel)
        ctrl_row1.pack(fill=tk.X, pady=2)
        ttk.Button(ctrl_row1, text="Update", width=8,
                  command=lambda: self.update_pulse_plot(phase)).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl_row1, text="Save", width=8,
                  command=lambda: self.save_phase_params(phase, apply_all=False)).pack(side=tk.LEFT, padx=2)
        
        # Controls row 2
        ctrl_row2 = ttk.Frame(controls_panel)
        ctrl_row2.pack(fill=tk.X, pady=2)
        ttk.Button(ctrl_row2, text="Apply to all pulses", width=16,
                  command=lambda: self.save_phase_params(phase, apply_all=True)).pack(side=tk.LEFT, padx=2)
        ttk.Button(ctrl_row2, text="Save all", width=12,
                  command=lambda: self.save_all_pulses(phase)).pack(side=tk.LEFT, padx=2)
        
        # Controls row 3
        ctrl_row3 = ttk.Frame(controls_panel)
        ctrl_row3.pack(fill=tk.X, pady=2)
        ttk.Button(ctrl_row3, text="Apply to all cycles", width=16,
                  command=lambda: self.apply_to_all_cycles(phase)).pack(side=tk.LEFT, padx=2)
        
        # RIGHT: Export panel
        export_panel = ttk.LabelFrame(controls_export_frame, text="Export", padding=5)
        export_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        # Export row 1: Plot selection
        export_row1 = ttk.Frame(export_panel)
        export_row1.pack(fill=tk.X, pady=2)
        ttk.Label(export_row1, text="Plot:").pack(side=tk.LEFT, padx=2)
        ttk.Combobox(export_row1, textvariable=plot_var, 
                    values=["Both Plots", "Regression Plot", "R² Plot"], 
                    width=12, state="readonly").pack(side=tk.LEFT, padx=5)
        
        # Export row 2: Size controls
        export_row2 = ttk.Frame(export_panel)
        export_row2.pack(fill=tk.X, pady=2)
        ttk.Label(export_row2, text="Width (in):").pack(side=tk.LEFT, padx=2)
        ttk.Entry(export_row2, textvariable=width_var, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(export_row2, text="Height (in):").pack(side=tk.LEFT)
        ttk.Entry(export_row2, textvariable=height_var, width=4).pack(side=tk.LEFT, padx=2)
        ttk.Label(export_row2, text="DPI:").pack(side=tk.LEFT, padx=(10,2))
        ttk.Entry(export_row2, textvariable=dpi_var, width=4).pack(side=tk.LEFT, padx=2)
        
        # Export row 3: Format and Export button
        export_row3 = ttk.Frame(export_panel)
        export_row3.pack(fill=tk.X, pady=2)
        ttk.Label(export_row3, text="Format:").pack(side=tk.LEFT, padx=2)
        ttk.Combobox(export_row3, textvariable=format_var, 
                    values=["png", "pdf", "svg"], width=6, state="readonly").pack(side=tk.LEFT, padx=2)
        ttk.Button(export_row3, text="Export", width=8,
                  command=lambda: self.export_phase_plot(phase)).pack(side=tk.LEFT, padx=10)

        # Plot frame
        plot_frame = ttk.Frame(parent)
        plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        fig = Figure(figsize=(6, 8))
        fig.subplots_adjust(hspace=0.4)

        if phase == "charge":
            self.charge_fig = fig
            self.charge_ax1 = fig.add_subplot(211)
            self.charge_ax2 = fig.add_subplot(212)
        else:
            self.discharge_fig = fig
            self.discharge_ax1 = fig.add_subplot(211)
            self.discharge_ax2 = fig.add_subplot(212)

        canvas = FigureCanvasTkAgg(fig, plot_frame)
        toolbar = NavigationToolbar2Tk(canvas, plot_frame)
        toolbar.update()

        toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        canvas.draw()

        if phase == "charge":
            self.charge_canvas = canvas
            self.charge_toolbar = toolbar
        else:
            self.discharge_canvas = canvas
            self.discharge_toolbar = toolbar

    def create_multi_cycle_tab(self):
        """Create multi-cycle analysis tab with three-panel layout"""

        # Main controls frame - horizontal layout for three panels
        main_frame = ttk.Frame(self.multi_cycle_frame)
        main_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=5)
        
        # LEFT PANEL: Multi-Cycle R² Analysis
        left_panel = ttk.LabelFrame(main_frame, text="Multi-Cycle R² Analysis", padding=10)
        left_panel.pack(side=tk.LEFT, padx=(0, 5), ipadx=5, ipady=20)
        
        # Available cycles display
        ttk.Label(left_panel, text="Available Cycles:").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.multi_available_label = ttk.Label(left_panel, text="", font=('Arial', 9, 'bold'))
        self.multi_available_label.grid(row=0, column=1, padx=5, sticky=tk.W)
        
        # Cycle selection
        ttk.Label(left_panel, text="Select Cycles:").grid(row=1, column=0, padx=5, pady=5, sticky=tk.W)
        self.multi_cycle_entry = ttk.Entry(left_panel, width=25)
        self.multi_cycle_entry.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)
        self.multi_cycle_entry.insert(0, "all")
        
        ttk.Button(left_panel, text="Generate Plot", 
                command=self.plot_multi_cycle).grid(row=2, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Button(left_panel, text="Back to Single Cycle", 
                command=self.back_to_cycles).grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)
        
        # Feedback label
        self.multi_feedback_label = ttk.Label(left_panel, text="", foreground="blue")
        self.multi_feedback_label.grid(row=3, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
        
        # Help text
        help_text = "Examples: 'all' | '0-5' | '1,3,5'"
        ttk.Label(left_panel, text=help_text, font=('Arial', 8), foreground='gray').grid(
            row=4, column=0, columnspan=2, padx=5, pady=(0, 5), sticky=tk.W)
        
        # MIDDLE PANEL: Axis Limits
        middle_panel = ttk.LabelFrame(main_frame, text="Axis Limits", padding=10)
        middle_panel.pack(side=tk.LEFT, padx=5, ipadx=5, ipady=20)
        
        # Auto limits checkbox
        self.auto_limits_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(middle_panel, text="Auto limits", 
                    variable=self.auto_limits_var,
                    command=self.update_limits_state).grid(row=0, column=0, columnspan=4, padx=2, pady=2, sticky=tk.W)
        
        # X and Y limits side by side
        limits_frame = ttk.Frame(middle_panel)
        limits_frame.grid(row=1, column=0, columnspan=4, padx=2, pady=2, sticky=tk.EW)
        
        # X-axis limits (left side)
        x_frame = ttk.LabelFrame(limits_frame, text="X-axis (Cycle)", padding=5)
        x_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        ttk.Label(x_frame, text="Min:").grid(row=0, column=0, padx=2, sticky=tk.W)
        self.x_min_var = tk.DoubleVar(value=0)
        self.x_min_entry = ttk.Entry(x_frame, textvariable=self.x_min_var, width=8)
        self.x_min_entry.grid(row=0, column=1, padx=2)
        
        ttk.Label(x_frame, text="Max:").grid(row=1, column=0, padx=2, sticky=tk.W)
        self.x_max_var = tk.DoubleVar(value=10)
        self.x_max_entry = ttk.Entry(x_frame, textvariable=self.x_max_var, width=8)
        self.x_max_entry.grid(row=1, column=1, padx=2)
        
        # Y-axis limits (right side)
        y_frame = ttk.LabelFrame(limits_frame, text="Y-axis (R²)", padding=5)
        y_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=(5, 0))
        
        ttk.Label(y_frame, text="Min:").grid(row=0, column=0, padx=2, sticky=tk.W)
        self.y_min_var = tk.DoubleVar(value=0)
        self.y_min_entry = ttk.Entry(y_frame, textvariable=self.y_min_var, width=8)
        self.y_min_entry.grid(row=0, column=1, padx=2)
        
        ttk.Label(y_frame, text="Max:").grid(row=1, column=0, padx=2, sticky=tk.W)
        self.y_max_var = tk.DoubleVar(value=1)
        self.y_max_entry = ttk.Entry(y_frame, textvariable=self.y_max_var, width=8)
        self.y_max_entry.grid(row=1, column=1, padx=2)
        
        # Apply button
        ttk.Button(middle_panel, text="Apply Limits", 
                command=self.apply_axis_limits).grid(row=2, column=0, columnspan=4, padx=2, pady=5)
        
        # RIGHT PANEL: Export Figure
        right_panel = ttk.LabelFrame(main_frame, text="Export Figure", padding=10)
        right_panel.pack(side=tk.LEFT, padx=(5, 0), ipadx=5, ipady=23)
        
        ttk.Label(right_panel, text="Width (in):").grid(row=0, column=0, padx=5, sticky=tk.W)
        self.multi_export_width_var = tk.DoubleVar(value=12.0)
        ttk.Entry(right_panel, textvariable=self.multi_export_width_var, width=8).grid(row=0, column=1, padx=5)
        
        ttk.Label(right_panel, text="Height (in):").grid(row=1, column=0, padx=5, sticky=tk.W)
        self.multi_export_height_var = tk.DoubleVar(value=6.0)
        ttk.Entry(right_panel, textvariable=self.multi_export_height_var, width=8).grid(row=1, column=1, padx=5)
        
        ttk.Label(right_panel, text="DPI:").grid(row=2, column=0, padx=5, sticky=tk.W)
        self.multi_export_dpi_var = tk.IntVar(value=300)
        ttk.Entry(right_panel, textvariable=self.multi_export_dpi_var, width=8).grid(row=2, column=1, padx=5)
        
        ttk.Label(right_panel, text="Format:").grid(row=3, column=0, padx=5, sticky=tk.W)
        self.multi_export_format_var = tk.StringVar(value="png")
        ttk.Combobox(right_panel, textvariable=self.multi_export_format_var,
                    values=["png", "pdf", "svg"], width=8, state="readonly").grid(row=3, column=1, padx=5)
        
        ttk.Button(right_panel, text="Export Plot", 
                command=self.export_multi_cycle_plot).grid(row=4, column=0, columnspan=2, padx=5, pady=10)
        
        # Initialize limits state
        self.update_limits_state()

        # Plot frame
        plot_frame = ttk.Frame(self.multi_cycle_frame)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        self.multi_fig = Figure(figsize=(12, 6))
        self.multi_ax = self.multi_fig.add_subplot(111)

        self.multi_canvas = FigureCanvasTkAgg(self.multi_fig, plot_frame)
        
        # Add navigation toolbar for zoom/pan
        self.multi_toolbar = NavigationToolbar2Tk(self.multi_canvas, plot_frame)
        self.multi_toolbar.update()

        # Pack toolbar at bottom, canvas fills remaining space
        self.multi_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.multi_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        self.multi_canvas.draw()

    def load_shared_data(self):
        """Load data from shared_data"""

        self.df_raw = self.shared_data.get('df_raw')
        self.cycle_list = self.shared_data.get('cycle_list', [])

        if self.df_raw is not None and len(self.cycle_list) > 0:
            self.cycle_combo['values'] = self.cycle_list
            if self.cycle_list:
                self.cycle_combo.current(0)

        # Update multi-cycle available label
        self.update_multi_cycle_available_label()

    def update_multi_cycle_available_label(self):
        """Update the available cycles label in multi-cycle tab"""
        if self.cycle_list:
            available_text = f"{min(self.cycle_list)}-{max(self.cycle_list)}"
            self.multi_available_label.config(text=available_text)


    def on_cycle_change(self, event):
        """Handle cycle dropdown change"""
        pass

    def get_rest_duration(self, pulse_data, pulse_num):
        """Get the actual duration of rest period for a pulse"""
        pulse = pulse_data[pulse_data['pulse_number'] == pulse_num]
        rest = pulse[pulse['I/mA'] == 0]
        
        if len(rest) == 0:
            return 0.0
        
        t_start = rest['t/s'].iloc[0]
        t_end = rest['t/s'].iloc[-1]
        duration = t_end - t_start
        
        return duration

    def update_time_limits(self, phase):
        """Update spinbox limits based on current pulse's rest duration"""
        
        if phase == "charge":
            if len(self.charge_pulse_nums) == 0:
                return
            pulse_num = self.charge_pulse_nums[self.current_charge_idx]
            pulse_data = self.charge_data_pulse
            spinbox_start = self.start_time_charge_spinbox
            spinbox_end = self.end_time_charge_spinbox
        else:
            if len(self.discharge_pulse_nums) == 0:
                return
            pulse_num = self.discharge_pulse_nums[self.current_discharge_idx]
            pulse_data = self.discharge_data_pulse
            spinbox_start = self.start_time_discharge_spinbox
            spinbox_end = self.end_time_discharge_spinbox
        
        # Get actual rest duration
        max_time = self.get_rest_duration(pulse_data, pulse_num)
        
        if max_time > 0:
            # Update spinbox limits dynamically
            spinbox_start.config(to=max_time)
            spinbox_end.config(to=max_time)
            
            # Clamp current values if they exceed new limit
            if phase == "charge":
                if self.start_time_charge_var.get() > max_time:
                    self.start_time_charge_var.set(min(0.1, max_time * 0.1))
                if self.end_time_charge_var.get() > max_time:
                    self.end_time_charge_var.set(max_time * 0.9)
            else:
                if self.start_time_discharge_var.get() > max_time:
                    self.start_time_discharge_var.set(min(0.1, max_time * 0.1))
                if self.end_time_discharge_var.get() > max_time:
                    self.end_time_discharge_var.set(max_time * 0.9)

    def time_to_indices(self, rest_data, start_time, end_time):
        """Convert time window to point indices with validation"""
        if len(rest_data) == 0:
            return 0, 0
        
        t_rel = rest_data['t/s'].values - rest_data['t/s'].values[0]
        max_time = t_rel[-1]
        
        # Clamp values to valid range
        start_time = max(0.0, min(start_time, max_time))
        end_time = max(start_time, min(end_time, max_time))
        
        # Ensure minimum window size
        if end_time - start_time < 0.1:
            end_time = min(start_time + 0.1, max_time)
        
        start_idx = np.argmin(np.abs(t_rel - start_time))
        end_idx = np.argmin(np.abs(t_rel - end_time))
        
        r1s = start_idx
        r1l = max(2, end_idx - start_idx)  # Minimum 2 points for regression
        
        return r1s, r1l

    def load_current_cycle(self):
        """Load the currently selected cycle"""

        if not self.cycle_combo.get():
            messagebox.showwarning("No Cycle", "Please select a cycle")
            return

        self.current_cycle = int(self.cycle_combo.get())

        # Load cycle data
        ra.df_raw = self.df_raw
        ra.cycle_list = self.cycle_list

        success = ra.load_cycle_for_regression(self.current_cycle)

        if success:
            self.charge_pulse_nums = ra.charge_pulse_nums.copy()
            self.discharge_pulse_nums = ra.discharge_pulse_nums.copy()
            self.charge_data_pulse = ra.charge_data_pulse.copy()
            self.discharge_data_pulse = ra.discharge_data_pulse.copy()

            # Reset to first pulse
            self.current_charge_idx = 0
            self.current_discharge_idx = 0

            # Load saved params for first pulses OR use defaults
            if len(self.charge_pulse_nums) > 0:
                pulse_num = self.charge_pulse_nums[0]
                key = f"{self.current_cycle}_charge_{pulse_num}"
                if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                    params = self.shared_data['regression_params'][key]
                    if 'start_time' in params:
                        self.start_time_charge_var.set(params['start_time'])
                        self.end_time_charge_var.set(params['end_time'])
                    else:
                        self.start_time_charge_var.set(0.1)
                        self.end_time_charge_var.set(1.0)
                else:
                    self.start_time_charge_var.set(0.1)
                    self.end_time_charge_var.set(1.0)
                
                # Update time limits based on actual rest duration
                self.update_time_limits("charge")

            if len(self.discharge_pulse_nums) > 0:
                pulse_num = self.discharge_pulse_nums[0]
                key = f"{self.current_cycle}_discharge_{pulse_num}"
                if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                    params = self.shared_data['regression_params'][key]
                    if 'start_time' in params:
                        self.start_time_discharge_var.set(params['start_time'])
                        self.end_time_discharge_var.set(params['end_time'])
                    else:
                        self.start_time_discharge_var.set(0.1)
                        self.end_time_charge_var.set(1.0)
                else:
                    self.start_time_discharge_var.set(0.1)
                    self.end_time_charge_var.set(1.0)
                
                # Update time limits based on actual rest duration
                self.update_time_limits("discharge")

            # Compute all R² values
            self.compute_all_r2_values()

            # Update plots
            self.update_pulse_labels()
            self.update_pulse_plot("charge")
            self.update_pulse_plot("discharge")

            print(f"✅ Loaded cycle {self.current_cycle}")

    def compute_all_r2_values(self):
        """Compute R² for all pulses using saved params or defaults"""

        # Charge
        if len(self.charge_pulse_nums) > 0:
            self.charge_r2_values = []
            for i, pulse_num in enumerate(self.charge_pulse_nums):
                key = f"{self.current_cycle}_charge_{pulse_num}"
                
                # Get rest data for time-to-indices conversion
                rest_data = self.charge_data_pulse[self.charge_data_pulse['pulse_number'] == pulse_num]
                rest_data = rest_data[rest_data['I/mA'] == 0].copy()
                
                if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                    params = self.shared_data['regression_params'][key]
                    if 'start_time' in params:
                        # Use time-based params
                        r1s, r1l = self.time_to_indices(rest_data, params['start_time'], params['end_time'])
                    else:
                        # Old format - use r1s/r1l directly
                        r1s = params['r1s']
                        r1l = params['r1l']
                else:
                    # Use defaults
                    r1s, r1l = self.time_to_indices(rest_data, 0.1, 1.0)

                result = ra.compute_r2_for_pulse(self.charge_data_pulse, pulse_num, r1s, r1l)
                self.charge_r2_values.append(result['r2'])
        else:
            self.charge_r2_values = []

        # Discharge
        if len(self.discharge_pulse_nums) > 0:
            self.discharge_r2_values = []
            for i, pulse_num in enumerate(self.discharge_pulse_nums):
                key = f"{self.current_cycle}_discharge_{pulse_num}"
                
                # Get rest data for time-to-indices conversion
                rest_data = self.discharge_data_pulse[self.discharge_data_pulse['pulse_number'] == pulse_num]
                rest_data = rest_data[rest_data['I/mA'] == 0].copy()
                
                if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                    params = self.shared_data['regression_params'][key]
                    if 'start_time' in params:
                        # Use time-based params
                        r1s, r1l = self.time_to_indices(rest_data, params['start_time'], params['end_time'])
                    else:
                        # Old format - use r1s/r1l directly
                        r1s = params['r1s']
                        r1l = params['r1l']
                else:
                    # Use defaults
                    r1s, r1l = self.time_to_indices(rest_data, 0.1, 1.0)

                result = ra.compute_r2_for_pulse(self.discharge_data_pulse, pulse_num, r1s, r1l)
                self.discharge_r2_values.append(result['r2'])
        else:
            self.discharge_r2_values = []

    def update_current_pulse_r2(self, phase):
        """Update R² for ONLY the current pulse (temporary, in memory)"""

        if phase == "charge":
            if len(self.charge_pulse_nums) == 0:
                return
            pulse_num = self.charge_pulse_nums[self.current_charge_idx]
            
            # Get rest data
            rest_data = self.charge_data_pulse[self.charge_data_pulse['pulse_number'] == pulse_num]
            rest_data = rest_data[rest_data['I/mA'] == 0].copy()
            
            # Convert time to indices
            start_time = self.start_time_charge_var.get()
            end_time = self.end_time_charge_var.get()
            r1s, r1l = self.time_to_indices(rest_data, start_time, end_time)

            result = ra.compute_r2_for_pulse(self.charge_data_pulse, pulse_num, r1s, r1l)
            
            if self.current_charge_idx < len(self.charge_r2_values):
                self.charge_r2_values[self.current_charge_idx] = result['r2']
            else:
                while len(self.charge_r2_values) < self.current_charge_idx:
                    self.charge_r2_values.append(np.nan)
                self.charge_r2_values.append(result['r2'])
        else:
            if len(self.discharge_pulse_nums) == 0:
                return
            pulse_num = self.discharge_pulse_nums[self.current_discharge_idx]
            
            # Get rest data
            rest_data = self.discharge_data_pulse[self.discharge_data_pulse['pulse_number'] == pulse_num]
            rest_data = rest_data[rest_data['I/mA'] == 0].copy()
            
            # Convert time to indices
            start_time = self.start_time_discharge_var.get()
            end_time = self.end_time_discharge_var.get()
            r1s, r1l = self.time_to_indices(rest_data, start_time, end_time)

            result = ra.compute_r2_for_pulse(self.discharge_data_pulse, pulse_num, r1s, r1l)
            
            if self.current_discharge_idx < len(self.discharge_r2_values):
                self.discharge_r2_values[self.current_discharge_idx] = result['r2']
            else:
                while len(self.discharge_r2_values) < self.current_discharge_idx:
                    self.discharge_r2_values.append(np.nan)
                self.discharge_r2_values.append(result['r2'])

    def update_pulse_labels(self):
        """Update pulse navigation labels with rest duration info"""

        if len(self.charge_pulse_nums) > 0:
            pulse_num = self.charge_pulse_nums[self.current_charge_idx]
            max_time = self.get_rest_duration(self.charge_data_pulse, pulse_num)
            self.charge_pulse_label.config(
                text=f"Pulse: {pulse_num} ({self.current_charge_idx+1}/{len(self.charge_pulse_nums)}) | "
                     f"Rest: {max_time:.2f}s"
            )
        else:
            self.charge_pulse_label.config(text="Pulse: None")

        if len(self.discharge_pulse_nums) > 0:
            pulse_num = self.discharge_pulse_nums[self.current_discharge_idx]
            max_time = self.get_rest_duration(self.discharge_data_pulse, pulse_num)
            self.discharge_pulse_label.config(
                text=f"Pulse: {pulse_num} ({self.current_discharge_idx+1}/{len(self.discharge_pulse_nums)}) | "
                     f"Rest: {max_time:.2f}s"
            )
        else:
            self.discharge_pulse_label.config(text="Pulse: None")

    def prev_charge_pulse(self):
        """Previous charge pulse - loads saved params if available"""
        if len(self.charge_pulse_nums) > 0:
            self.current_charge_idx = (self.current_charge_idx - 1) % len(self.charge_pulse_nums)
            pulse_num = self.charge_pulse_nums[self.current_charge_idx]
            key = f"{self.current_cycle}_charge_{pulse_num}"

            # Load saved params OR reset to defaults
            if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                params = self.shared_data['regression_params'][key]
                if 'start_time' in params:
                    self.start_time_charge_var.set(params['start_time'])
                    self.end_time_charge_var.set(params['end_time'])
                else:
                    self.start_time_charge_var.set(0.1)
                    self.end_time_charge_var.set(1.0)
            else:
                self.start_time_charge_var.set(0.1)
                self.end_time_charge_var.set(1.0)

            # Update time limits based on actual rest duration
            self.update_time_limits("charge")
            
            self.update_pulse_labels()
            self.update_pulse_plot("charge")

    def next_charge_pulse(self):
        """Next charge pulse - loads saved params if available"""
        if len(self.charge_pulse_nums) > 0:
            self.current_charge_idx = (self.current_charge_idx + 1) % len(self.charge_pulse_nums)
            pulse_num = self.charge_pulse_nums[self.current_charge_idx]
            key = f"{self.current_cycle}_charge_{pulse_num}"

            # Load saved params OR reset to defaults
            if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                params = self.shared_data['regression_params'][key]
                if 'start_time' in params:
                    self.start_time_charge_var.set(params['start_time'])
                    self.end_time_charge_var.set(params['end_time'])
                else:
                    self.start_time_charge_var.set(0.1)
                    self.end_time_charge_var.set(1.0)
            else:
                self.start_time_charge_var.set(0.1)
                self.end_time_charge_var.set(1.0)

            # Update time limits based on actual rest duration
            self.update_time_limits("charge")
            
            self.update_pulse_labels()
            self.update_pulse_plot("charge")

    def prev_discharge_pulse(self):
        """Previous discharge pulse - loads saved params if available"""
        if len(self.discharge_pulse_nums) > 0:
            self.current_discharge_idx = (self.current_discharge_idx - 1) % len(self.discharge_pulse_nums)
            pulse_num = self.discharge_pulse_nums[self.current_discharge_idx]
            key = f"{self.current_cycle}_discharge_{pulse_num}"

            # Load saved params OR reset to defaults
            if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                params = self.shared_data['regression_params'][key]
                if 'start_time' in params:
                    self.start_time_discharge_var.set(params['start_time'])
                    self.end_time_discharge_var.set(params['end_time'])
                else:
                    self.start_time_discharge_var.set(0.1)
                    self.end_time_charge_var.set(1.0)
            else:
                self.start_time_discharge_var.set(0.1)
                self.end_time_charge_var.set(1.0)

            # Update time limits based on actual rest duration
            self.update_time_limits("discharge")
            
            self.update_pulse_labels()
            self.update_pulse_plot("discharge")

    def next_discharge_pulse(self):
        """Next discharge pulse - loads saved params if available"""
        if len(self.discharge_pulse_nums) > 0:
            self.current_discharge_idx = (self.current_discharge_idx + 1) % len(self.discharge_pulse_nums)
            pulse_num = self.discharge_pulse_nums[self.current_discharge_idx]
            key = f"{self.current_cycle}_discharge_{pulse_num}"

            # Load saved params OR reset to defaults
            if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                params = self.shared_data['regression_params'][key]
                if 'start_time' in params:
                    self.start_time_discharge_var.set(params['start_time'])
                    self.end_time_discharge_var.set(params['end_time'])
                else:
                    self.start_time_discharge_var.set(0.1)
                    self.end_time_charge_var.set(1.0)
            else:
                self.start_time_discharge_var.set(0.1)
                self.end_time_charge_var.set(1.0)

            # Update time limits based on actual rest duration
            self.update_time_limits("discharge")
            
            self.update_pulse_labels()
            self.update_pulse_plot("discharge")

    def refresh_plots(self):
        """Refresh both charge and discharge plots (for title toggle)"""
        # Refresh single-cycle plots
        if self.current_cycle is not None:
            if len(self.charge_pulse_nums) > 0:
                self.update_pulse_plot("charge")
            if len(self.discharge_pulse_nums) > 0:
                self.update_pulse_plot("discharge")
    
        # Refresh multi-cycle plot TITLE ONLY (fast)
        current_tab = self.notebook.select()
        if current_tab == self.notebook.tabs()[1]:  # Index 1 = Multi-Cycle Analysis tab
            # Check if multi-cycle plot exists
            if len(self.multi_ax.lines) > 0 or len(self.multi_ax.collections) > 0:
                # Just update the title, don't recalculate everything
                if self.show_title_var.get():
                    self.multi_ax.set_title('R² Analysis Across All Cycles', 
                                             fontsize=14, fontweight='bold')
                else:
                    self.multi_ax.set_title('')
            
                self.multi_canvas.draw()  # Redraw canvas (fast!)

    def update_pulse_plot(self, phase):
        """Update regression and R² plots with time-based parameters"""

        if phase == "charge":
            if len(self.charge_pulse_nums) == 0:
                return
            pulse_num = self.charge_pulse_nums[self.current_charge_idx]
            pulse_data = self.charge_data_pulse
            start_time = self.start_time_charge_var.get()
            end_time = self.end_time_charge_var.get()
            ax1 = self.charge_ax1
            ax2 = self.charge_ax2
            canvas = self.charge_canvas
            r2_values = self.charge_r2_values
            current_idx = self.current_charge_idx
            pulse_nums = self.charge_pulse_nums
            color = 'b'
        else:
            if len(self.discharge_pulse_nums) == 0:
                return
            pulse_num = self.discharge_pulse_nums[self.current_discharge_idx]
            pulse_data = self.discharge_data_pulse
            start_time = self.start_time_discharge_var.get()
            end_time = self.end_time_discharge_var.get()
            ax1 = self.discharge_ax1
            ax2 = self.discharge_ax2
            canvas = self.discharge_canvas
            r2_values = self.discharge_r2_values
            current_idx = self.current_discharge_idx
            pulse_nums = self.discharge_pulse_nums
            color = 'r'

        # Update ONLY current pulse's R² (temporary, in memory)
        self.update_current_pulse_r2(phase)

        # Get updated R² values
        if phase == "charge":
            r2_values = self.charge_r2_values
        else:
            r2_values = self.discharge_r2_values

        # Get rest data
        rest_data = pulse_data[pulse_data['pulse_number'] == pulse_num]
        rest_data = rest_data[rest_data['I/mA'] == 0].copy()

        if len(rest_data) == 0:
            return

        # Get V0 and compute ΔV
        V0 = ra.get_V0(pulse_data, pulse_num)
        if np.isnan(V0):
            return

        rest_data['ΔV'] = rest_data['E/V'] - V0
        times_sqrt = np.sqrt(rest_data['t/s'].values - rest_data['t/s'].values[0])

        # Convert time to indices
        r1s, r1l = self.time_to_indices(rest_data, start_time, end_time)

        # Compute regression
        regression_result = ra.compute_single_pulse_regression(rest_data, r1s, r1l)
        
        # Get rest duration
        max_time = self.get_rest_duration(pulse_data, pulse_num)

        # Plot 1: Regression
        fig = ax1.get_figure()
        for ax in fig.get_axes():
            if ax not in [ax1, ax2]:
                fig.delaxes(ax)
        ax1.clear()

        ax1.plot(times_sqrt, rest_data['ΔV'].values, f'{color}o-', 
                markersize=3, label='ΔV', linewidth=1)

        if not np.isnan(regression_result['r2']) and len(rest_data) >= r1s + r1l:
            X_fit = times_sqrt[r1s:r1s + r1l]
            y_fit = regression_result['slope'] * X_fit + regression_result['intercept']
            
            # --- MODIFIED LEGEND START ---
            slope = regression_result['slope']
            intercept = regression_result['intercept']
            r2 = regression_result['r2']
            fit_label = (f"Slope: {slope:.6f}\n"
                         f"Intercept: {intercept:.6f}\n"
                         f"R2: {r2:.6f}")
            
            ax1.plot(X_fit, y_fit, 'green', linewidth=3, label=fit_label)
            # --- MODIFIED LEGEND END ---
            
            ax1.plot(times_sqrt[r1s:r1s+r1l], rest_data['ΔV'].values[r1s:r1s+r1l],
                    'o', color='orange', markersize=6, alpha=0.6, label='Reg points')

        ax1.set_xlabel('√Time (√s)', fontsize=12)
        ax1.set_ylabel('ΔV (V)', fontsize=12)
        
        if self.show_title_var.get():
            ax1.set_title(
                f'{phase.capitalize()} Pulse {pulse_num} (Cycle {self.current_cycle})\n' +
                f'V₀ = {V0:.4f} V | Window: {start_time:.2f}-{end_time:.2f}s ' +
                f'({r1l} pts) | Rest: {max_time:.2f}s total',
                fontsize=11
            )
        else:
            ax1.set_title('')
        
        # Legend with small font to ensure the 3-line text fits nicely
        ax1.legend(loc='best', fontsize='x-small', frameon=True)
        ax1.grid(True, alpha=0.3)

        # Secondary time axis logic (Untouched)
        if self.show_time_axis_var.get():
            ax1_top = ax1.twiny()
            xlim_sqrt = ax1.get_xlim()
            ax1_top.set_xlim(xlim_sqrt)
            max_time_sqrt = xlim_sqrt[1]
            max_time_val = max_time_sqrt ** 2
    
            if max_time_val <= 10:
                time_values = [0, 1, 4, 9, 16, 25, 36, 49, 64, 81, 100]
            elif max_time_val <= 25:
                time_values = [0, 1, 4, 9, 16, 25]
            elif max_time_val <= 100:
                time_values = [0, 4, 16, 36, 64, 100]
            else:
                time_values = [0, 25, 100, 225, 400]
    
            time_values = [t for t in time_values if t <= max_time_val]
            tick_positions = [np.sqrt(t) for t in time_values]
            ax1_top.set_xticks(tick_positions)
            ax1_top.set_xticklabels([f'{int(t)}' for t in time_values])
            ax1_top.set_xlabel('Time (s)', color='darkblue', fontsize=10)
            ax1_top.tick_params(axis='x', colors='darkblue', labelsize=9)

        # Plot 2: R² Across Pulses (Untouched)
        ax2.clear()
        pulse_indices = range(1, len(pulse_nums) + 1)
        ax2.plot(pulse_indices, r2_values, 'ko-', linewidth=1, markersize=4, label='R²')
        sel_r2 = r2_values[current_idx] if current_idx < len(r2_values) else np.nan
        ax2.plot(current_idx + 1, sel_r2, 'co', markersize=8, label='Selected')

        ax2.set_xlabel('Pulse #', fontsize=12)
        ax2.set_ylabel('R²', fontsize=12)
        
        if self.show_title_var.get():
            ax2.set_title(f'{phase.capitalize()} R² Across Pulses', fontsize=11)
        else:
            ax2.set_title('')
        
        ax2.legend(fontsize=9)
        ax2.grid(True, alpha=0.3)

        fig.subplots_adjust(hspace=0.45)
        fig.tight_layout(pad=2.0)
        canvas.draw()

    def save_phase_params(self, phase, apply_all=False):
        """Save regression parameters with time-based format"""

        if self.current_cycle is None:
            messagebox.showwarning("No Data", "Please load a cycle first")
            return

        if phase == "charge":
            if len(self.charge_pulse_nums) == 0:
                return
            pulse_num = self.charge_pulse_nums[self.current_charge_idx]
            start_time = self.start_time_charge_var.get()
            end_time = self.end_time_charge_var.get()
            pulse_data = self.charge_data_pulse
            pulse_list = self.charge_pulse_nums
        else:
            if len(self.discharge_pulse_nums) == 0:
                return
            pulse_num = self.discharge_pulse_nums[self.current_discharge_idx]
            start_time = self.start_time_discharge_var.get()
            end_time = self.end_time_discharge_var.get()
            pulse_data = self.discharge_data_pulse
            pulse_list = self.discharge_pulse_nums

        # Ensure regression_params exists
        if 'regression_params' not in self.shared_data:
            self.shared_data['regression_params'] = {}

        # Get rest data and convert time to indices
        rest_data = pulse_data[pulse_data['pulse_number'] == pulse_num]
        rest_data = rest_data[rest_data['I/mA'] == 0].copy()
        r1s, r1l = self.time_to_indices(rest_data, start_time, end_time)

        # Compute R² and save single-pulse params
        result = ra.compute_r2_for_pulse(pulse_data, pulse_num, r1s, r1l)
        key = f"{self.current_cycle}_{phase}_{pulse_num}"
        self.shared_data['regression_params'][key] = {
            'start_time': start_time,
            'end_time': end_time,
            'r1s': r1s,  # Keep for backward compatibility
            'r1l': r1l,  # Keep for backward compatibility
            'r2': result['r2'],
            'cycle': self.current_cycle,
            'phase': phase,
            'pulse': pulse_num
        }

        # If apply_all is requested, apply to every pulse in that phase
        if apply_all:
            applied_count = 0
            for p in pulse_list:
                key_all = f"{self.current_cycle}_{phase}_{p}"
                
                # Get rest data for this pulse
                rest_data_p = pulse_data[pulse_data['pulse_number'] == p]
                rest_data_p = rest_data_p[rest_data_p['I/mA'] == 0].copy()
                r1s_p, r1l_p = self.time_to_indices(rest_data_p, start_time, end_time)
                
                # Compute r2 for each pulse using the same time window
                res_all = ra.compute_r2_for_pulse(pulse_data, p, r1s_p, r1l_p)
                self.shared_data['regression_params'][key_all] = {
                    'start_time': start_time,
                    'end_time': end_time,
                    'r1s': r1s_p,
                    'r1l': r1l_p,
                    'r2': res_all['r2'],
                    'cycle': self.current_cycle,
                    'phase': phase,
                    'pulse': p
                }
                applied_count += 1

            # Recompute all r2 values and refresh plots
            self.compute_all_r2_values()
            try:
                self.update_pulse_plot(phase)
            except Exception:
                pass

            messagebox.showinfo("Applied to All",
                                f"✅ Applied {start_time:.2f}s-{end_time:.2f}s to all {applied_count} {phase} pulses in cycle {self.current_cycle}")
            print(f"✅ Applied to ALL pulses ({phase}) in cycle {self.current_cycle}: {start_time:.2f}s-{end_time:.2f}s")
            return

        # Otherwise, just saved the single pulse
        messagebox.showinfo("Saved", 
                           f"✅ {phase.capitalize()} parameters saved!\n\n"
                           f"Cycle {self.current_cycle}, pulse {pulse_num}\n"
                           f"Window: {start_time:.2f}s-{end_time:.2f}s, R²={result['r2']:.4f}")

        print(f"✅ Saved {phase} params for {key}: {start_time:.2f}s-{end_time:.2f}s")

    def save_all_pulses(self, phase):
        """Save the parameters for ALL pulses of the selected phase"""

        if self.current_cycle is None:
            messagebox.showwarning("No Data", "Please load a cycle first")
            return

        # Select correct data
        if phase == "charge":
            pulse_list = self.charge_pulse_nums
            pulse_data = self.charge_data_pulse
        else:
            pulse_list = self.discharge_pulse_nums
            pulse_data = self.discharge_data_pulse

        if len(pulse_list) == 0:
            return

        # Ensure storage dict exists
        if 'regression_params' not in self.shared_data:
            self.shared_data['regression_params'] = {}

        saved_count = 0

        for p in pulse_list:
            key = f"{self.current_cycle}_{phase}_{p}"

            # If the user already saved parameters for this pulse earlier
            if key in self.shared_data['regression_params']:
                params = self.shared_data['regression_params'][key]
                if 'start_time' in params:
                    start_time = params['start_time']
                    end_time = params['end_time']
                else:
                    # Old format
                    r1s = params['r1s']
                    r1l = params['r1l']
                    # Convert to time (approximate)
                    rest_data_p = pulse_data[pulse_data['pulse_number'] == p]
                    rest_data_p = rest_data_p[rest_data_p['I/mA'] == 0].copy()
                    if len(rest_data_p) > 0:
                        t_rel = rest_data_p['t/s'].values - rest_data_p['t/s'].values[0]
                        start_time = t_rel[min(r1s, len(t_rel)-1)]
                        end_time = t_rel[min(r1s + r1l - 1, len(t_rel)-1)]
                    else:
                        start_time = 0.1
                        end_time = 1.0
            else:
                # Otherwise, use GUI current values
                if phase == "charge":
                    start_time = self.start_time_charge_var.get()
                    end_time = self.end_time_charge_var.get()
                else:
                    start_time = self.start_time_discharge_var.get()
                    end_time = self.end_time_discharge_var.get()

            # Get rest data and convert
            rest_data_p = pulse_data[pulse_data['pulse_number'] == p]
            rest_data_p = rest_data_p[rest_data_p['I/mA'] == 0].copy()
            r1s, r1l = self.time_to_indices(rest_data_p, start_time, end_time)

            # Compute R²
            try:
                res = ra.compute_r2_for_pulse(pulse_data, p, r1s, r1l)
            except Exception:
                res = {'r2': np.nan}

            # Save params
            self.shared_data['regression_params'][key] = {
                'start_time': start_time,
                'end_time': end_time,
                'r1s': r1s,
                'r1l': r1l,
                'r2': res.get('r2', np.nan),
                'cycle': self.current_cycle,
                'phase': phase,
                'pulse': p
            }

            saved_count += 1

        messagebox.showinfo(
            "Saved All Pulses",
            f"✅ Saved parameters for {saved_count} {phase} pulses (cycle {self.current_cycle})"
        )

        print(f"✅ Saved all {phase} pulses for cycle {self.current_cycle}")

    def apply_to_all_cycles(self, phase):
        """Apply current time window to ALL pulses in ALL cycles for the selected phase"""
        
        if self.df_raw is None or len(self.cycle_list) == 0:
            messagebox.showwarning("No Data", "Please load data first")
            return
        
        # Get current time window
        if phase == "charge":
            start_time = self.start_time_charge_var.get()
            end_time = self.end_time_charge_var.get()
        else:
            start_time = self.start_time_discharge_var.get()
            end_time = self.end_time_discharge_var.get()
        
        # Confirm action
        response = messagebox.askyesno(
            "Apply to All Cycles",
            f"Apply window {start_time:.2f}s-{end_time:.2f}s to ALL {phase} pulses in ALL {len(self.cycle_list)} cycles?\n\n"
            f"This will overwrite any existing saved parameters.\n\n"
            f"Continue?"
        )
        
        if not response:
            return
        
        # Ensure regression_params exists
        if 'regression_params' not in self.shared_data:
            self.shared_data['regression_params'] = {}
        
        # Progress tracking
        total_saved = 0
        cycles_processed = 0
        
        print(f"\n{'='*60}")
        print(f"APPLYING TO ALL CYCLES: {start_time:.2f}s-{end_time:.2f}s ({phase})")
        print(f"{'='*60}")
        
        # Loop through all cycles
        for cycle_num in self.cycle_list:
            try:
                # Load cycle data
                cycle_df = self.df_raw[self.df_raw['cycle'] == cycle_num].copy()
                
                if 'cycle_phase' not in cycle_df.columns:
                    cycle_df['cycle_phase'] = ra.classify_charge_discharge(cycle_df)
                
                # Get phase data
                phase_df = cycle_df[cycle_df['cycle_phase'] == phase].copy()
                
                if len(phase_df) == 0:
                    continue
                
                # Process pulses
                phase_processed = ra.assign_valid_pulses(phase_df, ra.MAX_REST_DURATION)
                
                if len(phase_processed) == 0:
                    continue
                
                phase_processed = ra.compute_V0_t0(phase_processed)
                pulse_nums = [p for p in phase_processed['pulse_number'].unique() if p > 0]
                
                if not pulse_nums:
                    continue
                
                # Apply to all pulses in this cycle
                for pulse_num in pulse_nums:
                    # Get rest data for this pulse
                    rest_data = phase_processed[phase_processed['pulse_number'] == pulse_num]
                    rest_data = rest_data[rest_data['I/mA'] == 0].copy()
                    
                    if len(rest_data) == 0:
                        continue
                    
                    # Convert time to indices for this specific pulse
                    r1s, r1l = self.time_to_indices(rest_data, start_time, end_time)
                    
                    # Compute R²
                    try:
                        result = ra.compute_r2_for_pulse(phase_processed, pulse_num, r1s, r1l)
                        r2_value = result['r2']
                    except Exception as e:
                        print(f"  Warning: Cycle {cycle_num}, Pulse {pulse_num} - {e}")
                        r2_value = np.nan
                    
                    # Save parameters
                    key = f"{cycle_num}_{phase}_{pulse_num}"
                    self.shared_data['regression_params'][key] = {
                        'start_time': start_time,
                        'end_time': end_time,
                        'r1s': r1s,
                        'r1l': r1l,
                        'r2': r2_value,
                        'cycle': cycle_num,
                        'phase': phase,
                        'pulse': pulse_num
                    }
                    total_saved += 1
                
                cycles_processed += 1
                print(f"  ✅ Cycle {cycle_num}: {len(pulse_nums)} {phase} pulses")
                
            except Exception as e:
                print(f"  ❌ Error processing cycle {cycle_num}: {e}")
                continue
        
        print(f"{'='*60}")
        print(f"SUMMARY:")
        print(f"  • Cycles processed: {cycles_processed}/{len(self.cycle_list)}")
        print(f"  • Total pulses saved: {total_saved}")
        print(f"  • Time window: {start_time:.2f}s-{end_time:.2f}s")
        print(f"{'='*60}\n")
        
        # Refresh current cycle display if we're viewing one of the affected cycles
        if self.current_cycle in self.cycle_list:
            self.compute_all_r2_values()
            try:
                self.update_pulse_plot(phase)
            except Exception:
                pass
        
        # Show success message
        messagebox.showinfo(
            "Applied to All Cycles",
            f"✅ Successfully applied {start_time:.2f}s-{end_time:.2f}s window!\n\n"
            f"Cycles processed: {cycles_processed}\n"
            f"Total {phase} pulses saved: {total_saved}\n\n"
            f"Parameters are now saved and will be used in Tab 5."
        )
        
        print(f"✅ Applied window to ALL cycles for {phase} phase")

    def plot_multi_cycle(self):
        """Plot R² across all cycles (global plot)"""

        if self.df_raw is None or len(self.cycle_list) == 0:
            messagebox.showwarning("No Data", "Please load data first")
            return
        
        # Parse cycle selection
        cycle_input = self.multi_cycle_entry.get().strip().lower()
        
        if cycle_input == "all" or cycle_input == "":
            selected_cycles = self.cycle_list
        
        else:
            # Parse cycle range (e.g., "1-5", "1,3,5", "0-2,5,7-9")
            selected_cycles = self.parse_cycle_range(cycle_input)
            if not selected_cycles:
                messagebox.showwarning("Invalid Input", 
                    "Please enter valid cycle numbers\n\nExamples:\n  'all'\n  '0-5'\n  '1,3,5'\n  '0-2,5,7-10'")
                return
        print(f"📊 Plotting R² for {len(selected_cycles)} cycles: {selected_cycles}")

        # Show feedback
        if len(selected_cycles) > 5:
            feedback = f"Will plot {len(selected_cycles)} cycles: {selected_cycles[:5]} ... (+{len(selected_cycles)-5} more)"
        else:
            feedback = f"Will plot {len(selected_cycles)} cycles: {selected_cycles}"
        self.multi_feedback_label.config(text=feedback, foreground="blue")

        self.multi_ax.clear()

        # --- Store reference figure size for R² plot (only once) ---
        fig = self.multi_ax.figure
        if not hasattr(self, "_r2_ref_figsize"):
            self._r2_ref_figsize = fig.get_size_inches()

        charge_data = []
        discharge_data = []

        # Collect R² data for all cycles
        for cycle_num in selected_cycles:
            cycle_df = self.df_raw[self.df_raw['cycle'] == cycle_num].copy()

            if 'cycle_phase' not in cycle_df.columns:
                cycle_df['cycle_phase'] = ra.classify_charge_discharge(cycle_df)

            # Charge
            charge_df = cycle_df[cycle_df['cycle_phase'] == 'charge'].copy()
            if len(charge_df) > 0:
                charge_processed = ra.assign_valid_pulses(charge_df, ra.MAX_REST_DURATION)
                if len(charge_processed) > 0:
                    charge_processed = ra.compute_V0_t0(charge_processed)
                    charge_nums = [p for p in charge_processed['pulse_number'].unique() if p > 0]
                    if charge_nums:
                        for i, pulse_num in enumerate(charge_nums):
                            key = f"{cycle_num}_charge_{pulse_num}"
                            
                            # Get rest data for conversion
                            rest_data = charge_processed[charge_processed['pulse_number'] == pulse_num]
                            rest_data = rest_data[rest_data['I/mA'] == 0].copy()
                            
                            # Check if saved params exist
                            if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                                params = self.shared_data['regression_params'][key]
                                if 'start_time' in params:
                                    r1s, r1l = self.time_to_indices(rest_data, params['start_time'], params['end_time'])
                                else:
                                    r1s = params['r1s']
                                    r1l = params['r1l']
                            else:
                                r1s, r1l = self.time_to_indices(rest_data, 0.1, 1.0)

                            result = ra.compute_r2_for_pulse(charge_processed, pulse_num, r1s, r1l)
                            r2_value = result['r2']
                            charge_data.append({'cycle': cycle_num, 'pulse_idx': i, 'r2': r2_value})

            # Discharge
            discharge_df = cycle_df[cycle_df['cycle_phase'] == 'discharge'].copy()
            if len(discharge_df) > 0:
                discharge_processed = ra.assign_valid_pulses(discharge_df, ra.MAX_REST_DURATION)
                if len(discharge_processed) > 0:
                    discharge_processed = ra.compute_V0_t0(discharge_processed)
                    discharge_nums = [p for p in discharge_processed['pulse_number'].unique() if p > 0]
                    if discharge_nums:
                        for i, pulse_num in enumerate(discharge_nums):
                            key = f"{cycle_num}_discharge_{pulse_num}"
                            
                            # Get rest data for conversion
                            rest_data = discharge_processed[discharge_processed['pulse_number'] == pulse_num]
                            rest_data = rest_data[rest_data['I/mA'] == 0].copy()
                            
                            # Check if saved params exist
                            if 'regression_params' in self.shared_data and key in self.shared_data['regression_params']:
                                params = self.shared_data['regression_params'][key]
                                if 'start_time' in params:
                                    r1s, r1l = self.time_to_indices(rest_data, params['start_time'], params['end_time'])
                                else:
                                    r1s = params['r1s']
                                    r1l = params['r1l']
                            else:
                                r1s, r1l = self.time_to_indices(rest_data, 0.1, 1.0)

                            result = ra.compute_r2_for_pulse(discharge_processed, pulse_num, r1s, r1l)
                            r2_value = result['r2']
                            discharge_data.append({'cycle': cycle_num, 'pulse_idx': i, 'r2': r2_value})

        if not charge_data and not discharge_data:
            self.multi_ax.text(0.5, 0.5, 'No data to plot', 
                             ha='center', va='center', transform=self.multi_ax.transAxes)
            # Don't try to scale when there's no data
            self.multi_canvas.draw()
            return

        # Get all unique cycles
        all_cycles = sorted(set([d['cycle'] for d in charge_data + discharge_data]))

        # Create shading for complete cycle ranges
        min_cycle = min(all_cycles)
        max_cycle = max(all_cycles)

        # Create shading aligned with tick positions (offset by -0.35)
        for i, cycle in enumerate(all_cycles):
            if i % 2 == 0:  # Shade every other cycle
                # Use the same offset as tick positions
                if i < len(all_cycles) - 1:
                    next_cycle = all_cycles[i + 1]
                    self.multi_ax.axvspan(cycle - 0.35, next_cycle - 0.35, 
                                        color='lightgray', alpha=0.35, zorder=0)
                else:
                    # For the last cycle, shade from cycle to cycle+1
                    self.multi_ax.axvspan(cycle - 0.35, cycle + 0.65, 
                                        color='lightgray', alpha=0.35, zorder=0)

        # Plot charge data
        if charge_data:
            charge_cmap = plt.colormaps['Blues']
            charge_df = pd.DataFrame(charge_data)
            min_cycle = min(selected_cycles)
            max_cycle = max(selected_cycles)
            
            for cycle in charge_df['cycle'].unique():
                cycle_data = charge_df[charge_df['cycle'] == cycle]
                num_points = len(cycle_data)
                
                # Calculate color intensity based on cycle number
                if max_cycle == min_cycle:
                    cycle_normalized = 0
                else:
                    cycle_normalized = (cycle - min_cycle) / (max_cycle - min_cycle)
                color_intensity = 0.4 + 0.6 * cycle_normalized
                color = charge_cmap(color_intensity)
                
                if num_points == 1:
                    x_vals = [cycle]
                else:
                    x_vals = np.linspace(cycle - 0.3, cycle + 0.3, num_points)
                self.multi_ax.plot(x_vals, cycle_data['r2'].values, 
                                    'o-', color=color, markersize=5, alpha=0.8)

        # Plot discharge data
        if discharge_data:
            discharge_cmap = plt.colormaps['Reds']
            discharge_df = pd.DataFrame(discharge_data)
            min_cycle = min(selected_cycles)
            max_cycle = max(selected_cycles)
            
            for cycle in discharge_df['cycle'].unique():
                cycle_data = discharge_df[discharge_df['cycle'] == cycle]
                num_points = len(cycle_data)
                
                # Calculate color intensity based on cycle number
                if max_cycle == min_cycle:
                    cycle_normalized = 0
                else:
                    cycle_normalized = (cycle - min_cycle) / (max_cycle - min_cycle)
                color_intensity = 0.4 + 0.6 * cycle_normalized
                color = discharge_cmap(color_intensity)
                
                if num_points == 1:
                    x_vals = [cycle]
                else:
                    x_vals = np.linspace(cycle - 0.3, cycle + 0.3, num_points)
                self.multi_ax.plot(x_vals, cycle_data['r2'].values, 
                                    's-', color=color, markersize=5, alpha=0.8)

        # Formatting
        self.multi_ax.set_xlabel('Cycle Number', fontsize=16)
        self.multi_ax.set_ylabel('Coefficient of determination, R²', fontsize=16)
        
        # Conditional title
        if self.show_title_var.get():
            self.multi_ax.set_title('R² Analysis Across All Cycles', fontsize=14, fontweight='bold')
        else:
            self.multi_ax.set_title('')

        # Set x-axis ticks at LEFT edge of each cycle group (not centered)
        tick_positions = [c - 0.35 for c in all_cycles]
        self.multi_ax.set_xticks(tick_positions)

        # Set x-axis limits with proper margins
        self.multi_ax.set_xlim(min(all_cycles) - 0.35, max(all_cycles) + 0.9)
        #self.multi_ax.set_xlim(-0.35, max(all_cycles) + 0.9)

        # Adaptive labeling
        num_cycles = len(all_cycles)
        if num_cycles > 50:
            labels = [str(c) if c % 10 == 0 else '' for c in all_cycles]
            self.multi_ax.set_xticklabels(labels, fontsize=14)
        elif num_cycles > 20:
            labels = [str(c) if c % 5 == 0 else '' for c in all_cycles]
            self.multi_ax.set_xticklabels(labels, fontsize=14)
        else:
            labels = [str(c) for c in all_cycles]
            self.multi_ax.set_xticklabels(labels, fontsize=14)

        # Legend
        legend_elements = [
            Line2D([0], [0], color=plt.colormaps['Blues'](0.7), marker='o', label='Charge', markersize=6),
            Line2D([0], [0], color=plt.colormaps['Reds'](0.7), marker='s', label='Discharge', markersize=6)
        ]
        self.multi_ax.legend(handles=legend_elements, fontsize=11)

        # ===============================
        # Fixed-baseline scaling (12×6 in)
        # ===============================
        fig = self.multi_ax.figure
        dpi = fig.get_dpi()
        
        print(f"DEBUG: Figure DPI = {dpi}")
        print(f"DEBUG: Figure size (inches) = {fig.get_size_inches()}")

        # Baseline is 12×6 inches
        base_width_px = 12.0 * dpi
        base_height_px = 6.0 * dpi
        
        print(f"DEBUG: Baseline pixels = {base_width_px:.0f} × {base_height_px:.0f}")

        # Get current canvas size
        canvas = self.multi_canvas.get_tk_widget()
        canvas.update_idletasks()
        current_width_px = canvas.winfo_width()
        current_height_px = canvas.winfo_height()
        
        print(f"DEBUG: Canvas pixels = {current_width_px} × {current_height_px}")

        # Calculate scale factor
        scale = min(current_width_px / base_width_px, 
                    current_height_px / base_height_px)
        
        print(f"DEBUG: Scale factor = {scale:.3f}")

        # Apply scaling
        self.scale_plot_elements(self.multi_ax, scale)

        self.multi_canvas.draw()

    def scale_plot_elements(self, ax, scale):
        """Scale ALL visual elements proportionally with figure size"""
        
        # Store original sizes if not already stored
        if not hasattr(ax, '_original_sizes'):
            ax._original_sizes = {
                'xlabel_size': ax.xaxis.label.get_size() if ax.xaxis.label.get_text() else 12,
                'ylabel_size': ax.yaxis.label.get_size() if ax.yaxis.label.get_text() else 12,
                'title_size': ax.title.get_size() if ax.get_title() else 14,
                'tick_size': ax.xaxis.get_ticklabels()[0].get_size() if ax.xaxis.get_ticklabels() else 10,
                'linewidths': {},
                'markersizes': {},
                'legend_size': None,
                'legend_handles': {}  # NEW: Store legend handle properties
            }
            
            # Store original line properties
            for i, line in enumerate(ax.get_lines()):
                ax._original_sizes['linewidths'][i] = line.get_linewidth()
                ax._original_sizes['markersizes'][i] = line.get_markersize()
            
            # Store legend info
            legend = ax.get_legend()
            if legend:
                # Store legend text size
                if legend.get_texts():
                    ax._original_sizes['legend_size'] = legend.get_texts()[0].get_size()
                
                # Store legend handle properties
                for i, handle in enumerate(legend.legend_handles):
                    ax._original_sizes['legend_handles'][i] = {
                        'linewidth': handle.get_linewidth() if hasattr(handle, 'get_linewidth') else None,
                        'markersize': handle.get_markersize() if hasattr(handle, 'get_markersize') else None
                    }
        
        # Apply scaling from ORIGINAL sizes
        if ax.xaxis.label.get_text():
            ax.xaxis.label.set_size(ax._original_sizes['xlabel_size'] * scale)
        if ax.yaxis.label.get_text():
            ax.yaxis.label.set_size(ax._original_sizes['ylabel_size'] * scale)
        
        if ax.get_title():
            ax.title.set_size(ax._original_sizes['title_size'] * scale)
        
        # Tick labels
        for tick in ax.get_xticklabels() + ax.get_yticklabels():
            tick.set_fontsize(ax._original_sizes['tick_size'] * scale)
        
        # Lines and markers on plot
        for i, line in enumerate(ax.get_lines()):
            if i in ax._original_sizes['linewidths']:
                line.set_linewidth(ax._original_sizes['linewidths'][i] * scale)
            if i in ax._original_sizes['markersizes']:
                line.set_markersize(ax._original_sizes['markersizes'][i] * scale)
        
        # Legend
        legend = ax.get_legend()
        if legend:
            # Scale legend text
            if ax._original_sizes['legend_size']:
                for text in legend.get_texts():
                    text.set_fontsize(ax._original_sizes['legend_size'] * scale)
            
            # Scale legend symbols (handles)
            for i, handle in enumerate(legend.legend_handles):
                if i in ax._original_sizes['legend_handles']:
                    handle_props = ax._original_sizes['legend_handles'][i]
                    
                    # Scale line width in legend
                    if handle_props['linewidth'] is not None and hasattr(handle, 'set_linewidth'):
                        handle.set_linewidth(handle_props['linewidth'] * scale)
                    
                    # Scale marker size in legend
                    if handle_props['markersize'] is not None and hasattr(handle, 'set_markersize'):
                        handle.set_markersize(handle_props['markersize'] * scale)
            
            # Also try markerscale (sometimes works)
            legend.markerscale = scale

    def parse_cycle_range(self, input_str):
        """Parse cycle range string like '1-5' or '1,3,5,7-10'"""
        try:
            cycles = []
            parts = input_str.split(',')
            
            for part in parts:
                part = part.strip()
                if '-' in part:
                    start, end = map(int, part.split('-'))
                    cycles.extend(range(start, end + 1))
                else:
                    cycles.append(int(part))
            
            # Filter to available cycles only
            valid_cycles = [c for c in cycles if c in self.cycle_list]
            return sorted(list(set(valid_cycles)))
            
        except Exception as e:
            print(f"Error parsing cycle range: {e}")
            return []

    def analyze_all_cycles(self):
        """Switch to multi-cycle tab and generate plot"""
        self.notebook.select(self.multi_cycle_frame)
        self.plot_multi_cycle()

    def back_to_cycles(self):
        """Switch back to single cycle tab"""
        self.notebook.select(self.single_cycle_frame)

    # ==============================
    # EXPORT FUNCTIONS (STEP 1)
    # ==============================
    
    def export_figure_no_titles(self, fig, filepath, width_in, height_in, dpi, restore_callback=None):
        """
        Export figure without titles but WITH proper scaling
        Args:
            restore_callback: Optional function to call after export to restore display scaling
        """
        # Save ALL original properties
        original_state = {
            'size': fig.get_size_inches(),
            'titles': [],
            'element_scales': {},  # Store current scale state per axis
            'current_scale': {}    # Track current scale per axis
        }
        
        # Store titles
        for ax in fig.axes:
            original_state['titles'].append(ax.get_title())
        
        # Store current scale state for each axis
        for i, ax in enumerate(fig.get_axes()):
            if hasattr(ax, '_current_scale'):
                original_state['current_scale'][i] = ax._current_scale
            
            # Store the current visual state for restoration
            original_state['element_scales'][i] = {
                'xlabel_size': ax.xaxis.label.get_size() if ax.xaxis.label.get_text() else 12,
                'ylabel_size': ax.yaxis.label.get_size() if ax.yaxis.label.get_text() else 12,
                'title_size': ax.title.get_size() if ax.get_title() else 14,
                'tick_size': ax.xaxis.get_ticklabels()[0].get_size() if ax.xaxis.get_ticklabels() else 10,
            }
        
        try:
            # Calculate scale factors for BOTH dimensions independently
            width_scale = width_in / 12.0   # Scale factor for width (12" baseline)
            height_scale = height_in / 6.0  # Scale factor for height (6" baseline)
            
            # Apply export scaling to all axes
            for ax in fig.get_axes():
                # Store original element sizes if not already stored
                if not hasattr(ax, '_original_sizes'):
                    self.scale_plot_elements(ax, 1.0)  # This will store original sizes
                
                # Scale elements based on AVERAGE of width and height scaling
                # OR use the dominant scaling factor
                avg_scale = (width_scale + height_scale) / 2.0
                
                # Alternatively, use geometric mean for better balance
                geo_mean_scale = np.sqrt(width_scale * height_scale)
                
                # Apply the scaling
                self.scale_plot_elements(ax, geo_mean_scale)  # Using geometric mean
                ax._current_scale = geo_mean_scale  # Track current scale
            
            # Remove titles (regardless of show_title_var setting for export)
            for ax in fig.axes:
                ax.set_title("")
            
            # Set export size - this will stretch the plot area, but elements are scaled proportionally
            fig.set_size_inches(width_in, height_in)
            
            # Adjust layout to fit new aspect ratio
            fig.tight_layout(pad=1.5)
            
            # Export
            fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
            messagebox.showinfo("Export", f"Figure exported:\n{filepath}")
            
        finally:
            # ==============================================
            # RESTORE ORIGINAL STATE
            # ==============================================
            
            # 1. Restore figure size
            fig.set_size_inches(original_state['size'])
            
            # 2. Restore titles (respecting show_title_var setting)
            for ax, title in zip(fig.axes, original_state['titles']):
                ax.set_title(title)
            
            # 3. Restore tight layout
            fig.tight_layout(pad=2.0)
            
            # 4. If caller provided a restore callback, use it
            if restore_callback:
                restore_callback()
            else:
                # Otherwise, try to restore to the scale that was active before export
                for i, ax in enumerate(fig.get_axes()):
                    if i in original_state['current_scale']:
                        # Restore to the scale that was active before export
                        self.scale_plot_elements(ax, original_state['current_scale'][i])
                        ax._current_scale = original_state['current_scale'][i]
            
            # Redraw the canvas
            if hasattr(self, 'multi_canvas') and fig == self.multi_fig:
                self.multi_canvas.draw()
            elif hasattr(self, 'charge_canvas') and fig == self.charge_fig:
                self.charge_canvas.draw()
            elif hasattr(self, 'discharge_canvas') and fig == self.discharge_fig:
                self.discharge_canvas.draw()

    def export_single_axis(self, source_ax, filepath, width_in, height_in, dpi):
        """Export single subplot as standalone figure"""
        import matplotlib.pyplot as plt
        
        temp_fig, temp_ax = plt.subplots(figsize=(width_in, height_in))
        
        try:
            # Copy plot elements
            for line in source_ax.get_lines():
                temp_ax.plot(line.get_xdata(), line.get_ydata(),
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
                    temp_ax.scatter(offsets[:, 0], offsets[:, 1], 
                                  c=colors, s=sizes, alpha=collection.get_alpha())
            
            # Copy formatting (NO TITLE)
            temp_ax.set_xlabel(source_ax.get_xlabel())
            temp_ax.set_ylabel(source_ax.get_ylabel())
            temp_ax.set_xlim(source_ax.get_xlim())
            temp_ax.set_ylim(source_ax.get_ylim())
            temp_ax.grid(True, alpha=0.3)
            
            if source_ax.get_legend():
                temp_ax.legend(loc='best')
            
            temp_fig.tight_layout()
            temp_fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
            messagebox.showinfo("Export", f"Plot exported:\n{filepath}")
            
        finally:
            plt.close(temp_fig)

    def export_phase_plot(self, phase):
        """Export selected plot from charge or discharge analysis"""
        try:
            # Get export settings based on phase
            if phase == "charge":
                plot_selection = self.charge_export_plot_var.get()
                width = self.export_width_charge_var.get()
                height = self.export_height_charge_var.get()
                dpi = self.export_dpi_charge_var.get()
                fig = self.charge_fig
                ax1 = self.charge_ax1
                ax2 = self.charge_ax2
            else:
                plot_selection = self.discharge_export_plot_var.get()
                width = self.export_width_discharge_var.get()
                height = self.export_height_discharge_var.get()
                dpi = self.export_dpi_discharge_var.get()
                fig = self.discharge_fig
                ax1 = self.discharge_ax1
                ax2 = self.discharge_ax2
            
            # File dialog
            filepath = filedialog.asksaveasfilename(
                title=f"Export {phase.title()} Analysis Plot",
                defaultextension=".png",
                filetypes=[("PNG", "*.png"), ("PDF", "*.pdf"), ("SVG", "*.svg")],
                initialdir=self.shared_data.get('last_folder', os.path.expanduser("~"))
            )
            
            if not filepath:
                return
            
            # Remember folder
            self.shared_data['last_folder'] = os.path.dirname(filepath)
            
            if plot_selection == "Both Plots":
                self.export_figure_no_titles(fig, filepath, width, height, dpi)
            elif plot_selection == "Regression Plot":
                self.export_single_axis(ax1, filepath, width, height/2, dpi)
            elif plot_selection == "R² Plot":
                self.export_single_axis(ax2, filepath, width, height/2, dpi)
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting {phase} plot:\n{str(e)}")

    # ==============================
    # MULTI-CYCLE FUNCTIONS (STEP 4)
    # ==============================
    
    def update_limits_state(self):
        """Enable/disable limit entry fields based on auto limits checkbox"""
        state = 'disabled' if self.auto_limits_var.get() else 'normal'
        
        self.x_min_entry.config(state=state)
        self.x_max_entry.config(state=state)
        self.y_min_entry.config(state=state)
        self.y_max_entry.config(state=state)
    
    def apply_axis_limits(self):
        """Apply manual axis limits to the multi-cycle plot"""
        if self.multi_ax is None or len(self.multi_ax.lines) == 0:
            messagebox.showwarning("No Plot", "Generate a plot first before applying limits")
            return
        
        try:
            if not self.auto_limits_var.get():
                # Apply manual limits
                x_min = self.x_min_var.get()
                x_max = self.x_max_var.get()
                y_min = self.y_min_var.get()
                y_max = self.y_max_var.get()
                
                self.multi_ax.set_xlim(x_min, x_max)
                self.multi_ax.set_ylim(y_min, y_max)
            else:
                # Auto limits
                self.multi_ax.relim()
                self.multi_ax.autoscale()
            
            self.multi_canvas.draw()
            
            limit_type = "Auto" if self.auto_limits_var.get() else "Manual"
            messagebox.showinfo("Limits Applied", f"{limit_type} axis limits applied successfully")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error applying limits:\n{str(e)}")
    
    def export_multi_cycle_plot(self):
        """Export the multi-cycle plot with proper scaling"""
        try:
            # Get export settings
            width = self.multi_export_width_var.get()
            height = self.multi_export_height_var.get()
            dpi = self.multi_export_dpi_var.get()
            format_ext = self.multi_export_format_var.get()
            
            # File dialog
            filepath = filedialog.asksaveasfilename(
                title="Export Multi-Cycle Plot",
                defaultextension=f".{format_ext}",
                filetypes=[(f"{format_ext.upper()}", f"*.{format_ext}")],
                initialdir=self.shared_data.get('last_folder', os.path.expanduser("~"))
            )
            
            if not filepath:
                return
            
            # Remember folder
            self.shared_data['last_folder'] = os.path.dirname(filepath)
            
            # Use the existing export method with proper scaling
            self.export_figure_no_titles(self.multi_fig, filepath, width, height, dpi, 
                                        restore_callback=self.restore_multi_cycle_scaling)
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting multi-cycle plot:\n{str(e)}")
            import traceback
            traceback.print_exc()

    def restore_multi_cycle_scaling(self):
        """Restore the scaling for the multi-cycle plot after export"""
        # Recalculate and apply proper scaling for display
        fig = self.multi_ax.figure
        dpi = fig.get_dpi()
        
        # Baseline is 12×6 inches
        base_width_px = 12.0 * dpi
        base_height_px = 6.0 * dpi
        
        # Get current canvas size
        canvas = self.multi_canvas.get_tk_widget()
        canvas.update_idletasks()
        current_width_px = canvas.winfo_width()
        current_height_px = canvas.winfo_height()
        
        # Calculate scale factor
        scale = min(current_width_px / base_width_px, 
                    current_height_px / base_height_px)
        
        # Apply scaling
        self.scale_plot_elements(self.multi_ax, scale)
        self.multi_canvas.draw()