#!/usr/bin/env python3
"""
Kinetics Tab - R & k Analysis (Enhanced)
Tab 5: Kinetic parameter analysis with error bars from covariance matrix
Enhanced with separate axis controls and export functionality for charge/discharge
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
import os
from matplotlib.lines import Line2D

# Import the kinetic analyzer module
import analysis.kinetic_analyzer as ka

class KineticsTab:
    """Tab 5: Kinetic Analysis (R & k) - Enhanced Version"""
    
    def __init__(self, parent, shared_data):
        self.parent = parent
        self.shared_data = shared_data
        
        # Data storage
        self.df_raw = None
        self.cycle_list = []
        
        # Per-file entries for kinetics overlay
        self.kin_file_vars = {}    # {fname: {'cycles_var': StringVar}}
        self.kin_file_check_vars = {}  # {fname: BooleanVar}

        # Colorbar tracking (CRITICAL for preventing stacking and progressive shrinking)
        # Tracking separate colorbars for R and k axes to allow individual positioning
        self.charge_colorbar_R = None
        self.charge_colorbar_k = None
        self.discharge_colorbar_R = None
        self.discharge_colorbar_k = None
        
        self.setup_ui()
        self.load_shared_data()
    
    def export_figure(self, fig, filepath, width_in=8, height_in=6, dpi=300):
        """Export figure to file with specified dimensions and DPI (no titles for clean export)"""
        original_size = fig.get_size_inches()
        
        # Store original titles
        original_titles = []
        for ax in fig.get_axes():
            original_titles.append(ax.get_title())
            ax.set_title('')  # Remove title for clean export
        
        # Set new size
        fig.set_size_inches(width_in, height_in)
        
        try:
            fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
        finally:
            # Restore original titles and size AFTER saving
            for ax, title in zip(fig.get_axes(), original_titles):
                ax.set_title(title)
            fig.set_size_inches(original_size)
    
    def setup_ui(self):
        """Create the UI layout"""
        # Control panel — outer frame
        control_frame = ttk.LabelFrame(self.parent, text="Kinetic Analysis Controls", padding=10)
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Inner panels row
        inner_row = ttk.Frame(control_frame)
        inner_row.pack(side=tk.TOP, anchor=tk.W, pady=(0, 8))

        # ---- Single File panel ----
        single_panel = ttk.LabelFrame(inner_row, text="Single File", padding=8)
        single_panel.pack(side=tk.LEFT, padx=(0, 10), anchor=tk.N)

        ttk.Label(single_panel, text="Available Cycles:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.available_label = ttk.Label(single_panel, text="", font=('Arial', 9, 'bold'))
        self.available_label.grid(row=0, column=1, sticky=tk.W, padx=5)

        ttk.Label(single_panel, text="Select Cycles:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.cycle_entry = ttk.Entry(single_panel, width=20)
        self.cycle_entry.grid(row=1, column=1, sticky=tk.W, padx=5, pady=5)
        self.cycle_entry.insert(0, "1-10")

        # ---- Multi-File panel ----
        multi_panel = ttk.LabelFrame(inner_row, text="Multi-File", padding=8)
        multi_panel.pack(side=tk.LEFT, anchor=tk.N)

        # Column headers
        hdr_frame = ttk.Frame(multi_panel)
        hdr_frame.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(hdr_frame, text="File", foreground='gray',
                  width=28).pack(side=tk.LEFT, padx=(20, 0))
        ttk.Label(hdr_frame, text="Cycles", foreground='gray',
                  width=8).pack(side=tk.LEFT)

        # Scrollable rows canvas
        self.kin_files_canvas = tk.Canvas(multi_panel, height=80, width=500, highlightthickness=0)
        kin_files_scroll = ttk.Scrollbar(multi_panel, orient=tk.VERTICAL,
                                          command=self.kin_files_canvas.yview)
        self.kin_files_canvas.configure(yscrollcommand=kin_files_scroll.set)
        self.kin_files_canvas.pack(side=tk.LEFT, fill=tk.BOTH)
        kin_files_scroll.pack(side=tk.LEFT, fill=tk.Y)

        self.kin_files_inner = ttk.Frame(self.kin_files_canvas)
        self.kin_files_canvas.create_window((0, 0), window=self.kin_files_inner, anchor='nw')
        self.kin_files_inner.bind('<Configure>', lambda e: self.kin_files_canvas.configure(
            scrollregion=self.kin_files_canvas.bbox('all')))

        # Overlay checkbox
        self.kin_overlay_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(multi_panel, text="Overlay selected files",
                        variable=self.kin_overlay_var,
                        command=self._on_kin_overlay_toggled).pack(anchor=tk.W, pady=(6, 0))

        # ---- Bottom bar: buttons + checkbox + feedback ----
        bottom_bar = ttk.Frame(control_frame)
        bottom_bar.pack(side=tk.TOP, fill=tk.X, pady=(4, 0))

        ttk.Button(bottom_bar, text="Plot R & k",
                   command=self.plot_data).pack(side=tk.LEFT, padx=(0, 5))
        ttk.Button(bottom_bar, text="Export Data",
                   command=self.export_data).pack(side=tk.LEFT, padx=5)

        self.show_title_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(bottom_bar, text="Show plot titles",
                        variable=self.show_title_var,
                        command=self.refresh_plots).pack(side=tk.LEFT, padx=15)

        # X-axis selector: Voltage / Capacity / Specific Capacity.
        # Capacity values come from Classification tab's capacity-vs-voltage
        # curve (via analysis.kinetic_analyzer.match_capacity_to_voltage) —
        # no separate mass field here, mass is read from shared_data['file_mass_mg'].
        ttk.Label(bottom_bar, text="X-axis:").pack(side=tk.LEFT, padx=(15, 2))
        self.xaxis_var = tk.StringVar(value="Voltage (V)")
        xaxis_combo = ttk.Combobox(bottom_bar, textvariable=self.xaxis_var,
                     values=["Voltage (V)", "Capacity (mAh)", "Specific Capacity (mAh/g)"],
                     width=22, state='readonly')
        xaxis_combo.pack(side=tk.LEFT, padx=5)
        xaxis_combo.bind('<<ComboboxSelected>>', self._on_xaxis_changed)

        self.feedback_label = ttk.Label(bottom_bar, text="", foreground="blue")
        self.feedback_label.pack(side=tk.LEFT, padx=5)

        # Plot frame
        plot_frame = ttk.Frame(self.parent)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        plot_frame.columnconfigure(0, weight=1, uniform="kinetic")
        plot_frame.columnconfigure(1, weight=1, uniform="kinetic")
        plot_frame.rowconfigure(0, weight=1)

        # ==============================
        # CHARGE SECTION (LEFT SIDE)
        # ==============================
        charge_main_frame = ttk.LabelFrame(plot_frame, text="Charge Analysis", padding=5)
        charge_main_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=0)
        
        # Charge controls frame (axis limits + export side by side)
        charge_controls_frame = ttk.Frame(charge_main_frame)
        charge_controls_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        # Charge axis limits (left side)
        charge_limits_frame = ttk.LabelFrame(charge_controls_frame, text="Axis Limits (Charge)", padding=5)
        charge_limits_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Voltage axis (X-axis) for charge
        ttk.Label(charge_limits_frame, text="Voltage (V):").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Label(charge_limits_frame, text="Min:").grid(row=0, column=1, sticky=tk.W, padx=(10,2))
        self.charge_v_min_var = tk.StringVar()
        ttk.Entry(charge_limits_frame, textvariable=self.charge_v_min_var, width=8).grid(row=0, column=2, padx=2)
        ttk.Label(charge_limits_frame, text="Max:").grid(row=0, column=3, sticky=tk.W, padx=(10,2))
        self.charge_v_max_var = tk.StringVar()
        ttk.Entry(charge_limits_frame, textvariable=self.charge_v_max_var, width=8).grid(row=0, column=4, padx=2)
        
        # R axis (Y-axis top) for charge
        ttk.Label(charge_limits_frame, text="R (Ω):").grid(row=1, column=0, sticky=tk.W, padx=5)
        ttk.Label(charge_limits_frame, text="Min:").grid(row=1, column=1, sticky=tk.W, padx=(10,2))
        self.charge_R_min_var = tk.StringVar()
        ttk.Entry(charge_limits_frame, textvariable=self.charge_R_min_var, width=8).grid(row=1, column=2, padx=2)
        ttk.Label(charge_limits_frame, text="Max:").grid(row=1, column=3, sticky=tk.W, padx=(10,2))
        self.charge_R_max_var = tk.StringVar()
        ttk.Entry(charge_limits_frame, textvariable=self.charge_R_max_var, width=8).grid(row=1, column=4, padx=2)
        
        # k axis (Y-axis bottom) for charge
        ttk.Label(charge_limits_frame, text="k (Ω·s⁻⁰·⁵):").grid(row=2, column=0, sticky=tk.W, padx=5)
        ttk.Label(charge_limits_frame, text="Min:").grid(row=2, column=1, sticky=tk.W, padx=(10,2))
        self.charge_k_min_var = tk.StringVar()
        ttk.Entry(charge_limits_frame, textvariable=self.charge_k_min_var, width=8).grid(row=2, column=2, padx=2)
        ttk.Label(charge_limits_frame, text="Max:").grid(row=2, column=3, sticky=tk.W, padx=(10,2))
        self.charge_k_max_var = tk.StringVar()
        ttk.Entry(charge_limits_frame, textvariable=self.charge_k_max_var, width=8).grid(row=2, column=4, padx=2)
        
        # Charge axis control buttons
        charge_buttons_frame = ttk.Frame(charge_limits_frame)
        charge_buttons_frame.grid(row=3, column=0, columnspan=5, pady=(10,0))
        ttk.Button(charge_buttons_frame, text="Apply Limits", 
                  command=lambda: self.apply_axis_limits("charge")).pack(side=tk.LEFT, padx=5)
        ttk.Button(charge_buttons_frame, text="Auto Scale", 
                  command=lambda: self.auto_scale("charge")).pack(side=tk.LEFT, padx=5)
        
        # Charge export panel (right side)
        charge_export_frame = ttk.LabelFrame(charge_controls_frame, text="Export Charge Plot", padding=5)
        charge_export_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(charge_export_frame, text="Width (in):").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.charge_export_width_var = tk.DoubleVar(value=6.0)
        ttk.Entry(charge_export_frame, textvariable=self.charge_export_width_var, width=6).grid(row=0, column=1, padx=2)

        ttk.Label(charge_export_frame, text="Height (in):").grid(row=1, column=0, sticky=tk.W, padx=2)
        self.charge_export_height_var = tk.DoubleVar(value=8.0)
        ttk.Entry(charge_export_frame, textvariable=self.charge_export_height_var, width=6).grid(row=1, column=1, padx=2)

        ttk.Label(charge_export_frame, text="DPI:").grid(row=0, column=2, sticky=tk.W, padx=(10,2))
        self.charge_export_dpi_var = tk.IntVar(value=300)
        ttk.Entry(charge_export_frame, textvariable=self.charge_export_dpi_var, width=6).grid(row=0, column=3, padx=2)

        ttk.Label(charge_export_frame, text="Format:").grid(row=1, column=2, sticky=tk.W, padx=(10,2))
        self.charge_export_format_var = tk.StringVar(value="png")
        ttk.Combobox(
            charge_export_frame,
            textvariable=self.charge_export_format_var,
            values=["png", "pdf", "svg"],
            width=5,
            state="readonly"
        ).grid(row=1, column=3, padx=2)

        # Export buttons - R&k combined, R only, k only
        export_buttons_frame = ttk.Frame(charge_export_frame)
        export_buttons_frame.grid(row=0, column=4, padx=10, rowspan=2)
        
        ttk.Button(
            export_buttons_frame,
            text="R & k",
            command=self.export_charge_figure,
            width=8
        ).pack(pady=1)
        
        ttk.Button(
            export_buttons_frame,
            text="R only",
            command=lambda: self.export_charge_single("R"),
            width=8
        ).pack(pady=1)
        
        ttk.Button(
            export_buttons_frame,
            text="k only",
            command=lambda: self.export_charge_single("k"),
            width=8
        ).pack(pady=1)
        
        # Charge plot area
        charge_plot_frame = ttk.Frame(charge_main_frame)
        charge_plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # FIXED: Reserve 15% space on right for legend/colorbar with subplots_adjust
        self.charge_fig = Figure(figsize=(6, 8))
        # FIX: Increased bottom margin to ensure x-axis labels fit
        self.charge_fig.subplots_adjust(left=0.15, right=0.85, top=0.95, bottom=0.10, hspace=0.3)
        self.charge_ax_R = self.charge_fig.add_subplot(211)
        self.charge_ax_k = self.charge_fig.add_subplot(212)
        
        self.charge_canvas = FigureCanvasTkAgg(self.charge_fig, charge_plot_frame)

        # Add navigation toolbar for zoom/pan
        self.charge_toolbar = NavigationToolbar2Tk(self.charge_canvas, charge_plot_frame)
        self.charge_toolbar.update()

        # Pack toolbar at bottom, canvas fills remaining space
        self.charge_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.charge_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # ==============================
        # DISCHARGE SECTION (RIGHT SIDE)
        # ==============================
        discharge_main_frame = ttk.LabelFrame(plot_frame, text="Discharge Analysis", padding=5)
        discharge_main_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=0)
        
        # Discharge controls frame (axis limits + export side by side)
        discharge_controls_frame = ttk.Frame(discharge_main_frame)
        discharge_controls_frame.pack(side=tk.TOP, fill=tk.X, pady=5)
        
        # Discharge axis limits (left side)
        discharge_limits_frame = ttk.LabelFrame(discharge_controls_frame, text="Axis Limits (Discharge)", padding=5)
        discharge_limits_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Voltage axis (X-axis) for discharge
        ttk.Label(discharge_limits_frame, text="Voltage (V):").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Label(discharge_limits_frame, text="Min:").grid(row=0, column=1, sticky=tk.W, padx=(10,2))
        self.discharge_v_min_var = tk.StringVar()
        ttk.Entry(discharge_limits_frame, textvariable=self.discharge_v_min_var, width=8).grid(row=0, column=2, padx=2)
        ttk.Label(discharge_limits_frame, text="Max:").grid(row=0, column=3, sticky=tk.W, padx=(10,2))
        self.discharge_v_max_var = tk.StringVar()
        ttk.Entry(discharge_limits_frame, textvariable=self.discharge_v_max_var, width=8).grid(row=0, column=4, padx=2)
        
        # R axis (Y-axis top) for discharge
        ttk.Label(discharge_limits_frame, text="R (Ω):").grid(row=1, column=0, sticky=tk.W, padx=5)
        ttk.Label(discharge_limits_frame, text="Min:").grid(row=1, column=1, sticky=tk.W, padx=(10,2))
        self.discharge_R_min_var = tk.StringVar()
        ttk.Entry(discharge_limits_frame, textvariable=self.discharge_R_min_var, width=8).grid(row=1, column=2, padx=2)
        ttk.Label(discharge_limits_frame, text="Max:").grid(row=1, column=3, sticky=tk.W, padx=(10,2))
        self.discharge_R_max_var = tk.StringVar()
        ttk.Entry(discharge_limits_frame, textvariable=self.discharge_R_max_var, width=8).grid(row=1, column=4, padx=2)
        
        # k axis (Y-axis bottom) for discharge
        ttk.Label(discharge_limits_frame, text="k (Ω·s⁻⁰·⁵):").grid(row=2, column=0, sticky=tk.W, padx=5)
        ttk.Label(discharge_limits_frame, text="Min:").grid(row=2, column=1, sticky=tk.W, padx=(10,2))
        self.discharge_k_min_var = tk.StringVar()
        ttk.Entry(discharge_limits_frame, textvariable=self.discharge_k_min_var, width=8).grid(row=2, column=2, padx=2)
        ttk.Label(discharge_limits_frame, text="Max:").grid(row=2, column=3, sticky=tk.W, padx=(10,2))
        self.discharge_k_max_var = tk.StringVar()
        ttk.Entry(discharge_limits_frame, textvariable=self.discharge_k_max_var, width=8).grid(row=2, column=4, padx=2)
        
        # Discharge axis control buttons
        discharge_buttons_frame = ttk.Frame(discharge_limits_frame)
        discharge_buttons_frame.grid(row=3, column=0, columnspan=5, pady=(10,0))
        ttk.Button(discharge_buttons_frame, text="Apply Limits", 
                  command=lambda: self.apply_axis_limits("discharge")).pack(side=tk.LEFT, padx=5)
        ttk.Button(discharge_buttons_frame, text="Auto Scale", 
                  command=lambda: self.auto_scale("discharge")).pack(side=tk.LEFT, padx=5)
        
        # Discharge export panel (right side)
        discharge_export_frame = ttk.LabelFrame(discharge_controls_frame, text="Export Discharge Plot", padding=5)
        discharge_export_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(discharge_export_frame, text="Width (in):").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.discharge_export_width_var = tk.DoubleVar(value=6.0)
        ttk.Entry(discharge_export_frame, textvariable=self.discharge_export_width_var, width=6).grid(row=0, column=1, padx=2)

        ttk.Label(discharge_export_frame, text="Height (in):").grid(row=1, column=0, sticky=tk.W, padx=2)
        self.discharge_export_height_var = tk.DoubleVar(value=8.0)
        ttk.Entry(discharge_export_frame, textvariable=self.discharge_export_height_var, width=6).grid(row=1, column=1, padx=2)

        ttk.Label(discharge_export_frame, text="DPI:").grid(row=0, column=2, sticky=tk.W, padx=(10,2))
        self.discharge_export_dpi_var = tk.IntVar(value=300)
        ttk.Entry(discharge_export_frame, textvariable=self.discharge_export_dpi_var, width=6).grid(row=0, column=3, padx=2)

        ttk.Label(discharge_export_frame, text="Format:").grid(row=1, column=2, sticky=tk.W, padx=(10,2))
        self.discharge_export_format_var = tk.StringVar(value="png")
        ttk.Combobox(
            discharge_export_frame,
            textvariable=self.discharge_export_format_var,
            values=["png", "pdf", "svg"],
            width=5,
            state="readonly"
        ).grid(row=1, column=3, padx=2)

        # Export buttons - R&k combined, R only, k only
        export_buttons_frame = ttk.Frame(discharge_export_frame)
        export_buttons_frame.grid(row=0, column=4, padx=10, rowspan=2)
        
        ttk.Button(
            export_buttons_frame,
            text="R & k",
            command=self.export_discharge_figure,
            width=8
        ).pack(pady=1)
        
        ttk.Button(
            export_buttons_frame,
            text="R only",
            command=lambda: self.export_discharge_single("R"),
            width=8
        ).pack(pady=1)
        
        ttk.Button(
            export_buttons_frame,
            text="k only",
            command=lambda: self.export_discharge_single("k"),
            width=8
        ).pack(pady=1)
        
        # Discharge plot area
        discharge_plot_frame = ttk.Frame(discharge_main_frame)
        discharge_plot_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # FIXED: Reserve 15% space on right for legend/colorbar with subplots_adjust
        self.discharge_fig = Figure(figsize=(6, 8))
        # FIX: Increased bottom margin to ensure x-axis labels fit
        self.discharge_fig.subplots_adjust(left=0.15, right=0.85, top=0.95, bottom=0.10, hspace=0.3)
        self.discharge_ax_R = self.discharge_fig.add_subplot(211)
        self.discharge_ax_k = self.discharge_fig.add_subplot(212)
        
        self.discharge_canvas = FigureCanvasTkAgg(self.discharge_fig, discharge_plot_frame)

        # Add navigation toolbar for zoom/pan
        self.discharge_toolbar = NavigationToolbar2Tk(self.discharge_canvas, discharge_plot_frame)
        self.discharge_toolbar.update()

        # Pack toolbar at bottom, canvas fills remaining space
        self.discharge_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.discharge_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        
        # Status bar
        self.bottom_status = ttk.Label(self.parent, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.bottom_status.pack(fill=tk.X, side=tk.BOTTOM)
    
    def apply_axis_limits(self, phase):
        """Apply axis limits for the specified phase (charge or discharge)"""
        try:
            if phase == "charge":
                ax_R = self.charge_ax_R
                ax_k = self.charge_ax_k
                v_min_var = self.charge_v_min_var
                v_max_var = self.charge_v_max_var
                R_min_var = self.charge_R_min_var
                R_max_var = self.charge_R_max_var
                k_min_var = self.charge_k_min_var
                k_max_var = self.charge_k_max_var
                canvas = self.charge_canvas
            else:  # discharge
                ax_R = self.discharge_ax_R
                ax_k = self.discharge_ax_k
                v_min_var = self.discharge_v_min_var
                v_max_var = self.discharge_v_max_var
                R_min_var = self.discharge_R_min_var
                R_max_var = self.discharge_R_max_var
                k_min_var = self.discharge_k_min_var
                k_max_var = self.discharge_k_max_var
                canvas = self.discharge_canvas
            
            # Check if plots exist
            if len(ax_R.lines) == 0 and len(ax_k.lines) == 0:
                messagebox.showwarning("No Plot", f"Please plot {phase} data first")
                return
            
            # Apply voltage limits (X-axis for both R and k plots)
            v_min_str = v_min_var.get().strip()
            v_max_str = v_max_var.get().strip()
            
            if v_min_str or v_max_str:
                # Get current limits
                current_xlim_R = ax_R.get_xlim()
                current_xlim_k = ax_k.get_xlim()
                
                # Parse new limits
                new_xlim_R = list(current_xlim_R)
                new_xlim_k = list(current_xlim_k)
                
                if v_min_str:
                    v_min = float(v_min_str)
                    new_xlim_R[0] = v_min
                    new_xlim_k[0] = v_min
                    
                if v_max_str:
                    v_max = float(v_max_str)
                    new_xlim_R[1] = v_max
                    new_xlim_k[1] = v_max
                
                # Apply voltage limits
                ax_R.set_xlim(new_xlim_R)
                ax_k.set_xlim(new_xlim_k)
            
            # Apply R limits (Y-axis for R plot)
            R_min_str = R_min_var.get().strip()
            R_max_str = R_max_var.get().strip()
            
            if R_min_str or R_max_str:
                current_ylim = ax_R.get_ylim()
                new_ylim = list(current_ylim)
                
                if R_min_str:
                    new_ylim[0] = float(R_min_str)
                if R_max_str:
                    new_ylim[1] = float(R_max_str)
                
                ax_R.set_ylim(new_ylim)
            
            # Apply k limits (Y-axis for k plot)
            k_min_str = k_min_var.get().strip()
            k_max_str = k_max_var.get().strip()
            
            if k_min_str or k_max_str:
                current_ylim = ax_k.get_ylim()
                new_ylim = list(current_ylim)
                
                if k_min_str:
                    new_ylim[0] = float(k_min_str)
                if k_max_str:
                    new_ylim[1] = float(k_max_str)
                
                ax_k.set_ylim(new_ylim)
            
            # Refresh canvas
            canvas.draw()
            
            # Status update
            self.update_status(f"Applied axis limits for {phase}")
            
        except ValueError:
            messagebox.showerror("Invalid Input", "Please enter valid numeric values for axis limits")
        except Exception as e:
            messagebox.showerror("Error", f"Error applying axis limits: {str(e)}")
    
    def auto_scale(self, phase):
        """Auto-scale axes for the specified phase and clear limit fields"""
        try:
            if phase == "charge":
                ax_R = self.charge_ax_R
                ax_k = self.charge_ax_k
                canvas = self.charge_canvas
                
                # Clear all limit fields
                self.charge_v_min_var.set("")
                self.charge_v_max_var.set("")
                self.charge_R_min_var.set("")
                self.charge_R_max_var.set("")
                self.charge_k_min_var.set("")
                self.charge_k_max_var.set("")
            else:  # discharge
                ax_R = self.discharge_ax_R
                ax_k = self.discharge_ax_k
                canvas = self.discharge_canvas
                
                # Clear all limit fields
                self.discharge_v_min_var.set("")
                self.discharge_v_max_var.set("")
                self.discharge_R_min_var.set("")
                self.discharge_R_max_var.set("")
                self.discharge_k_min_var.set("")
                self.discharge_k_max_var.set("")
            
            # Check if plots exist
            if len(ax_R.lines) == 0 and len(ax_k.lines) == 0:
                messagebox.showwarning("No Plot", f"Please plot {phase} data first")
                return
            
            # Auto-scale both axes
            ax_R.relim()
            ax_R.autoscale()
            ax_k.relim() 
            ax_k.autoscale()
            
            # Refresh canvas
            canvas.draw()
            
            # Status update
            self.update_status(f"Auto-scaled {phase} plots")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error auto-scaling: {str(e)}")
    
    def export_charge_figure(self):
        """Export charge R & k figure (both plots)"""
        self._export_figure_helper(
            fig=self.charge_fig,
            phase_name="charge",
            plot_type="R_and_k",
            width_var=self.charge_export_width_var,
            height_var=self.charge_export_height_var,
            dpi_var=self.charge_export_dpi_var,
            format_var=self.charge_export_format_var
        )
    
    def export_charge_single(self, plot_type):
        """Export single charge plot (R or k only)"""
        self._export_single_plot_helper(
            phase="charge",
            plot_type=plot_type,
            width_var=self.charge_export_width_var,
            height_var=self.charge_export_height_var,
            dpi_var=self.charge_export_dpi_var,
            format_var=self.charge_export_format_var
        )
    
    def export_discharge_figure(self):
        """Export discharge R & k figure (both plots)"""
        self._export_figure_helper(
            fig=self.discharge_fig,
            phase_name="discharge",
            plot_type="R_and_k",
            width_var=self.discharge_export_width_var,
            height_var=self.discharge_export_height_var,
            dpi_var=self.discharge_export_dpi_var,
            format_var=self.discharge_export_format_var
        )
    
    def export_discharge_single(self, plot_type):
        """Export single discharge plot (R or k only)"""
        self._export_single_plot_helper(
            phase="discharge",
            plot_type=plot_type,
            width_var=self.discharge_export_width_var,
            height_var=self.discharge_export_height_var,
            dpi_var=self.discharge_export_dpi_var,
            format_var=self.discharge_export_format_var
        )
    
    def scale_plot_elements(self, ax, scale):
        """Scale all visual elements of a matplotlib Axes, including legend and colorbar"""

        # ---------- Axis labels ----------
        ax.xaxis.label.set_size(12 * scale)
        ax.yaxis.label.set_size(12 * scale)

        # ---------- Tick labels ----------
        ax.tick_params(axis='both', labelsize=10 * scale)

        # ---------- Title ----------
        if ax.get_title():
            ax.title.set_fontsize(13 * scale)

        # ---------- Axis spines ----------
        for spine in ax.spines.values():
            spine.set_linewidth(1.0 * scale)

        # ---------- Tick length & width ----------
        ax.tick_params(
            axis='both',
            width=1.0 * scale,
            length=5.0 * scale
        )

        # ---------- Lines & markers ----------
        for line in ax.get_lines():
            line.set_linewidth(1.5 * scale)
            if line.get_marker() not in (None, '', 'None'):
                line.set_markersize(6.0 * scale)

        # ---------- Scatter plots ----------
        for coll in ax.collections:
            if hasattr(coll, "set_sizes"):
                coll.set_sizes(coll.get_sizes() * scale**2)

        # ---------- Grid ----------
        for gl in ax.get_xgridlines() + ax.get_ygridlines():
            gl.set_linewidth(0.8 * scale)

        # =========================================================
        # LEGEND (full scaling)
        # =========================================================
        legend = ax.get_legend()
        if legend:
            for txt in legend.get_texts():
                txt.set_fontsize(9 * scale)

            legend.get_frame().set_linewidth(0.8 * scale)

            handles = getattr(legend, "legend_handles", None)
            if handles is None:
                handles = legend.legendHandles  # fallback for older matplotlib

            handles = getattr(legend, "legend_handles", None)
            if handles is None:
                handles = legend.legendHandles

            legend = ax.get_legend()
            if legend:
                # Legend text
                for txt in legend.get_texts():
                    txt.set_fontsize(9 * scale)

                # Legend frame
                legend.get_frame().set_linewidth(0.8 * scale)

                # THIS is the only reliable way to scale legend symbols
                legend.markerscale = scale

        # =========================================================
        # COLORBAR (this is what you asked for)
        # =========================================================
        # ---------- Colorbar ----------
        if hasattr(ax, "_colorbar"):
            cb = ax._colorbar
            cb_ax = cb.ax   # THIS is where text actually lives

            # Label
            if cb_ax.yaxis.label.get_text():
                cb_ax.yaxis.label.set_size(12 * scale)
            if cb_ax.xaxis.label.get_text():
                cb_ax.xaxis.label.set_size(12 * scale)

            # Tick labels
            cb_ax.tick_params(
                labelsize=10 * scale,
                width=1.0 * scale,
                length=4.0 * scale
            )

            # Outline
            for spine in cb_ax.spines.values():
                spine.set_linewidth(1.0 * scale)

    def _export_single_plot_helper(self, phase, plot_type, width_var, height_var, dpi_var, format_var):
        """Helper method for exporting individual R or k plots"""
        try:
            # Get the appropriate axis
            if phase == "charge":
                if plot_type == "R":
                    ax = self.charge_ax_R
                    plot_name = "R"
                else:  # plot_type == "k"
                    ax = self.charge_ax_k
                    plot_name = "k"
            else:  # discharge
                if plot_type == "R":
                    ax = self.discharge_ax_R
                    plot_name = "R"
                else:  # plot_type == "k"
                    ax = self.discharge_ax_k
                    plot_name = "k"
            
            # Check if plot has data
            if len(ax.lines) == 0 and len(ax.collections) == 0:
                messagebox.showwarning("No Plot", f"Please plot {phase} data first")
                return
            
            # Get export parameters
            fmt = format_var.get()
            width = width_var.get()
            height = height_var.get()
            dpi = dpi_var.get()
            
            # Get filename from shared data if available
            filename = self.shared_data.get('filename', 'kinetics_analysis')
            if filename:
                filename_prefix = os.path.splitext(filename)[0]
            else:
                filename_prefix = "kinetics_analysis"
            
            # Open save dialog with fixed options
            default_filename = f"{filename_prefix}_{phase}_{plot_name}.{fmt}"
            
            filetypes = []
            if fmt == "png":
                filetypes = [("PNG files", "*.png"), ("All files", "*.*")]
            elif fmt == "pdf":
                filetypes = [("PDF files", "*.pdf"), ("All files", "*.*")]
            elif fmt == "svg":
                filetypes = [("SVG files", "*.svg"), ("All files", "*.*")]
            
            filepath = filedialog.asksaveasfilename(
                title=f"Export {phase.title()} {plot_name} Plot",
                defaultextension=f".{fmt}",
                filetypes=filetypes,
                initialdir=self.shared_data.get('last_folder', os.path.expanduser("~"))
            )
            
            if not filepath:
                return
            
            # Remember the folder for next time
            self.shared_data['last_folder'] = os.path.dirname(filepath)
            
            # Get current cycles to determine if we need colorbar
            selected_cycles = self.parse_and_validate_cycles()
            use_colorbar = len(selected_cycles) > 10
            
            # Adjust width for colorbar OR legend - both need extra space
            export_width = width 
            
            # Create temporary figure with just the selected plot
            temp_fig = Figure(figsize=(export_width, height))
            
            # Adjust subplot area to reserve space for colorbar/legend
            temp_fig.subplots_adjust(left=0.12, right=0.80, top=0.95, bottom=0.15)
                
            temp_ax = temp_fig.add_subplot(111)
            
            scale = min(export_width / 6.0, height / 6.0)

            # Copy the plot data and formatting - FIXED FOR ERROR BARS
            for line in ax.get_lines():
                temp_ax.plot(line.get_xdata(), line.get_ydata(), 
                           color=line.get_color(), label=line.get_label(),
                           linewidth=line.get_linewidth(), alpha=line.get_alpha(),
                           marker=line.get_marker(), markersize=line.get_markersize(),
                           linestyle=line.get_linestyle())
            
            # Handle collections (error bars, scatter plots, etc.)
            for collection in ax.collections:
                try:
                    if hasattr(collection, 'get_paths') and hasattr(collection, 'get_edgecolors'):
                        # This is likely an error bar collection (LineCollection)
                        # Copy the collection directly
                        import matplotlib.collections as mcoll
                        new_collection = mcoll.LineCollection(
                            collection.get_segments(),
                            colors=collection.get_colors(),
                            linewidths=collection.get_linewidths(),
                            linestyles=collection.get_linestyles(),
                            alpha=collection.get_alpha()
                        )
                        temp_ax.add_collection(new_collection)
                    elif hasattr(collection, 'get_offsets') and len(collection.get_offsets()) > 0:
                        # This is a scatter plot collection
                        offsets = collection.get_offsets()
                        colors = collection.get_facecolors()
                        sizes = collection.get_sizes()
                        temp_ax.scatter(offsets[:, 0], offsets[:, 1], 
                                      c=colors, s=sizes, alpha=collection.get_alpha())
                except Exception as e:
                    print(f"Warning: Could not copy collection: {e}")
                    continue
            
            # Copy formatting (NO TITLE for clean export)
            temp_ax.set_xlabel(ax.get_xlabel(), fontsize=12)
            temp_ax.set_ylabel(ax.get_ylabel(), fontsize=12)
            # NOTE: Intentionally not setting title for clean export
            temp_ax.grid(True, alpha=0.3)
            temp_ax.set_xlim(ax.get_xlim())
            temp_ax.set_ylim(ax.get_ylim())
            
            # Add colorbar for many cycles (>10)
            if use_colorbar:
                from matplotlib.cm import ScalarMappable
                from matplotlib.colors import Normalize
                
                # Determine colormap based on phase
                if phase == "charge":
                    cmap = plt.colormaps['Blues']
                else:
                    cmap = plt.colormaps['Reds']
                
                # Create colorbar
                norm = Normalize(vmin=min(selected_cycles), vmax=max(selected_cycles))
                sm = ScalarMappable(cmap=cmap, norm=norm)
                sm.set_array([])
                
                # Add colorbar
                cbar = temp_fig.colorbar(sm, ax=temp_ax, pad=0.02, fraction=0.046)
                cbar.set_label('Cycle Number', rotation=270, labelpad=20, fontsize=11)
                
                # Set ticks (same logic as main plots)
                min_cycle = min(selected_cycles)
                max_cycle = max(selected_cycles)
                num_cycles = len(selected_cycles)
                
                if num_cycles <= 20:
                    tick_positions = selected_cycles
                elif num_cycles <= 50:
                    tick_positions = [c for c in selected_cycles if c % 5 == 0 or c == min_cycle or c == max_cycle]
                else:
                    tick_positions = [c for c in selected_cycles if c % 10 == 0 or c == min_cycle or c == max_cycle]
                
                if min_cycle not in tick_positions:
                    tick_positions = [min_cycle] + tick_positions
                if max_cycle not in tick_positions:
                    tick_positions.append(max_cycle)
                
                final_ticks = sorted(set(tick_positions))
                cbar.set_ticks(final_ticks)
                cbar.set_ticklabels([str(int(t)) for t in final_ticks])
            
            else:
                # Add legend for few cycles (≤10) - POSITIONED OUTSIDE LIKE COLORBAR
                legend = ax.get_legend()
                if legend and legend.get_texts():
                    # Only add legend if it has actual content
                    handles, labels = ax.get_legend_handles_labels()
                    if handles and labels:
                        # Position legend OUTSIDE plot, aligned with top (like colorbar)
                        legend_obj = temp_ax.legend(
                            handles, labels,
                            bbox_to_anchor=(1.02, 1.0),
                            loc='upper left',
                            fontsize=9 * scale,        # scale text HERE
                            markerscale=scale          #  THIS is the only place it works
                        )
                        legend_obj.get_frame().set_facecolor('white')
                        legend_obj.get_frame().set_alpha(0.9)
                        legend_obj.get_frame().set_edgecolor('black')
            
            # Scale all elements according to figure size
            scale = min(export_width / 6.0, height / 6.0)
            for ax_ in temp_fig.get_axes():
                self.scale_plot_elements(ax_, scale)

            # Export the temporary figure
            temp_fig.tight_layout()
            self.export_figure(temp_fig, filepath, export_width, height, dpi)
                  
            # Clean up
            plt.close(temp_fig)
            
            # Show success message
            colorbar_note = " (with colorbar)" if use_colorbar else ""
            messagebox.showinfo("Export Complete", 
                f"Exported {phase} {plot_name} plot{colorbar_note}:\n{os.path.basename(filepath)}")
            
            self.update_status(f"Exported {phase} {plot_name} plot{colorbar_note} to {os.path.basename(filepath)}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting {phase} {plot_type} plot:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def _export_figure_helper(self, fig, phase_name, plot_type, width_var, height_var, dpi_var, format_var):
        """Helper method for exporting full figures (fixed dialog options)"""
        try:
            # Check if figure has any data
            has_data = False
            for ax in fig.get_axes():
                if len(ax.lines) > 0 or len(ax.collections) > 0:
                    has_data = True
                    break
            
            if not has_data:
                messagebox.showwarning("No Plot", f"Please plot {phase_name} data first")
                return
            
            # Get export parameters
            fmt = format_var.get()
            width = width_var.get()
            height = height_var.get()
            dpi = dpi_var.get()
            
            # Get filename from shared data if available
            filename = self.shared_data.get('filename', 'kinetics_analysis')
            if filename:
                filename_prefix = os.path.splitext(filename)[0]
            else:
                filename_prefix = "kinetics_analysis"
            
            # Create default filename
            default_filename = f"{filename_prefix}_{phase_name}_R_k.{fmt}"
            
            # Set up filetypes based on format
            filetypes = []
            if fmt == "png":
                filetypes = [("PNG files", "*.png"), ("All files", "*.*")]
            elif fmt == "pdf":
                filetypes = [("PDF files", "*.pdf"), ("All files", "*.*")]
            elif fmt == "svg":
                filetypes = [("SVG files", "*.svg"), ("All files", "*.*")]
            
            # Open save dialog with fixed options
            filepath = filedialog.asksaveasfilename(
                title=f"Export {phase_name.title()} R & k Plot",
                defaultextension=f".{fmt}",
                filetypes=filetypes,
                initialdir=self.shared_data.get('last_folder', os.path.expanduser("~"))
            )
            
            if not filepath:
                return
            
            # Remember the folder for next time
            self.shared_data['last_folder'] = os.path.dirname(filepath)
            
            # Scale fonts & legends according to figure size
            scale = min(width / 6.0, height / 6.0)

            for ax in fig.get_axes():
                self.scale_plot_elements(ax, scale)

            # Export figure
            self.export_figure(fig, filepath, width, height, dpi)
            
            # Show success message
            messagebox.showinfo("Export Complete", 
                f"Exported {phase_name} R & k plot:\n{os.path.basename(filepath)}")
            
            self.update_status(f"Exported {phase_name} R & k plot to {os.path.basename(filepath)}")
            
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting {phase_name} figure:\n{str(e)}")
    
    def _get_overlay_color(self, file_index):
        """Return colour for file_index from shared palette."""
        import matplotlib.colors as mcolors
        colors = self.shared_data.get('overlay_colors', ['#1f77b4'])
        n = len(colors)
        base_color = colors[file_index % n]
        round_num = file_index // n
        if round_num == 0:
            return base_color
        elif round_num == 1:
            rgb = mcolors.to_rgb(base_color)
            return tuple(c + (1 - c) * 0.5 for c in rgb)
        else:
            rgb = mcolors.to_rgb(base_color)
            return tuple(c * 0.5 for c in rgb)

    def _get_cycle_shade(self, base_color, cycle_index, total_cycles):
        """Light shade for early cycles, dark for later ones."""
        import matplotlib.colors as mcolors
        rgb = mcolors.to_rgb(base_color)
        t = cycle_index / max(total_cycles - 1, 1)
        if t < 0.5:
            blend = 1 - t * 2
            return tuple(c + (1 - c) * blend * 0.6 for c in rgb)
        else:
            blend = (t - 0.5) * 2
            return tuple(c * (1 - blend * 0.4) for c in rgb)

    def _refresh_kin_files_panel(self):
        """Rebuild the multi-file panel rows."""
        loaded = self.shared_data.get('loaded_files', {})
        active = self.shared_data.get('active_file', None)
        colors = self.shared_data.get('overlay_colors', [])
        n_colors = len(colors)

        for widget in self.kin_files_inner.winfo_children():
            widget.destroy()

        existing_vars = self.kin_file_vars.copy()
        existing_checks = self.kin_file_check_vars.copy()
        self.kin_file_vars = {}
        self.kin_file_check_vars = {}

        for i, (fname, rec) in enumerate(loaded.items()):
            color = colors[i % n_colors] if n_colors else '#1f77b4'
            short = os.path.basename(fname)
            is_active = (fname == active)

            row = ttk.Frame(self.kin_files_inner)
            row.pack(fill=tk.X, pady=1)

            # Checkbox
            check_var = existing_checks.get(fname, tk.BooleanVar(value=True))
            self.kin_file_check_vars[fname] = check_var
            ttk.Checkbutton(row, variable=check_var).pack(side=tk.LEFT)

            # Colour dot
            dot = tk.Canvas(row, width=10, height=10, highlightthickness=0)
            dot.pack(side=tk.LEFT, padx=(2, 4))
            dot.create_oval(1, 1, 9, 9, fill=color, outline=color)

            # Filename label
            lbl_text = f"► {short}" if is_active else f"   {short}"
            lbl = ttk.Label(row, text=lbl_text, width=28,
                            foreground='darkblue' if is_active else '',
                            font=('TkDefaultFont', 9, 'bold' if is_active else 'normal'))
            lbl.pack(side=tk.LEFT, padx=(0, 4))
            lbl.bind('<Button-1>', lambda e, f=fname: self._set_kin_active_file(f))

            # Cycles entry
            if fname in existing_vars:
                cycles_var = existing_vars[fname]['cycles_var']
            else:
                default_cycles = f"{min(rec['cycle_list'])}-{max(rec['cycle_list'])}" \
                    if rec['cycle_list'] else ''
                cycles_var = tk.StringVar(value=default_cycles)
            self.kin_file_vars[fname] = {'cycles_var': cycles_var}
            ttk.Entry(row, textvariable=cycles_var, width=14).pack(side=tk.LEFT)

    def _set_kin_active_file(self, fname):
        """Set active file from kinetics panel click."""
        loaded = self.shared_data.get('loaded_files', {})
        if fname not in loaded:
            return
        rec = loaded[fname]
        # Snapshot the outgoing active file's regression_params before
        # switching — otherwise switching active file from this panel
        # (rather than Data Tab) silently drops it.
        old_fname = self.shared_data.get('active_file')
        if old_fname and old_fname != fname:
            self.shared_data.setdefault('all_regression_params', {})[old_fname] = \
                self.shared_data.get('regression_params', {}).copy()
        self.shared_data['active_file'] = fname
        self.shared_data['df_raw']      = rec['df_raw']
        self.shared_data['cycle_list']  = rec['cycle_list']
        self.shared_data['filename']    = rec['filename']
        all_params = self.shared_data.get('all_regression_params', {})
        self.shared_data['regression_params'] = all_params.get(fname, {})
        self.df_raw     = rec['df_raw']
        self.cycle_list = rec['cycle_list']
        ka.df_raw = self.df_raw
        ka.cycle_list = self.cycle_list
        self._refresh_kin_files_panel()
        self.update_status(f"Active: {os.path.basename(fname)}  |  {len(self.cycle_list)} cycles")

    def load_shared_data(self):
        """Load data from shared_data"""
        try:
            if 'df_raw' not in self.shared_data or self.shared_data['df_raw'] is None:
                # Reset stale state so this tab doesn't keep operating on
                # already-removed data (e.g. after Data tab's "Remove All").
                self.df_raw = None
                self.cycle_list = []
                self.update_status("No data loaded. Please load data in Tab 1 first.", error=True)
                if hasattr(self, 'kin_files_inner'):
                    self._refresh_kin_files_panel()
                return

            self.df_raw = self.shared_data['df_raw']
            self.cycle_list = self.shared_data.get('cycle_list', [])
            
            if len(self.cycle_list) == 0:
                self.cycle_list = sorted(self.df_raw['cycle'].unique().tolist())
            
            # Sync data with kinetic_analyzer module
            ka.df_raw = self.df_raw
            ka.cycle_list = self.cycle_list
            
            # Display available cycles
            if self.cycle_list:
                lo, hi = int(min(self.cycle_list)), int(max(self.cycle_list))
                available_text = f"{lo}-{hi}"
                self.available_label.config(text=available_text)
                self.update_status(f"Loaded {len(self.cycle_list)} cycles")

                # The cycle entry ships with a hardcoded "1-10" default (assumes
                # 1-indexed cycles), but cycles are 0-indexed - a file with 10
                # cycles is numbered 0-9, so leaving the default untouched
                # silently drops cycle 0 and includes a nonexistent cycle 10.
                # Only overwrite it if it's still that untouched default (or
                # empty), so a user's own custom cycle selection is preserved.
                if self.cycle_entry.get().strip() in ("", "1-10"):
                    self.cycle_entry.delete(0, tk.END)
                    self.cycle_entry.insert(0, available_text)
            else:
                self.update_status("No cycles found", error=True)
            
            if hasattr(self, 'kin_files_inner'):
                self._refresh_kin_files_panel()
                
        except Exception as e:
            self.update_status(f"Error loading data: {str(e)}", error=True)
            import traceback
            traceback.print_exc()
    
    def refresh_plots(self):
        """Refresh plots when title toggle changes"""
        # Only refresh if plots exist
        if len(self.charge_ax_R.lines) > 0 or len(self.discharge_ax_R.lines) > 0:
            
            # --- Charge Plot Updates ---
            if self.show_title_var.get():
                if hasattr(self, '_charge_title'):
                    self.charge_ax_R.set_title(self._charge_title, fontsize=13, fontweight='bold', color='blue')
            else:
                self._charge_title = self.charge_ax_R.get_title()
                self.charge_ax_R.set_title('')
            
            # FIX 1 & 2: Axis labels with absolute notation
            charge_xlabel = getattr(self, '_charge_xlabel', 'Voltage (V)')
            self.charge_ax_R.set_ylabel(r'Internal resistance, $R$ ($\Omega$)', fontsize=12)  # Updated
            self.charge_ax_R.set_xlabel(charge_xlabel, fontsize=12)
            self.charge_ax_k.set_xlabel(charge_xlabel, fontsize=12)
            self.charge_ax_k.set_ylabel(r'$k$ ($\Omega \cdot s^{-0.5}$)', fontsize=12)  # Updated

            # --- Discharge Plot Updates ---
            if self.show_title_var.get():
                if hasattr(self, '_discharge_title'):
                    self.discharge_ax_R.set_title(self._discharge_title, fontsize=13, fontweight='bold', color='red')
            else:
                self._discharge_title = self.discharge_ax_R.get_title()
                self.discharge_ax_R.set_title('')

            # FIX 1 & 2: Axis labels with absolute notation
            discharge_xlabel = getattr(self, '_discharge_xlabel', 'Voltage (V)')
            self.discharge_ax_R.set_ylabel(r'Internal resistance, $R$ ($\Omega$)', fontsize=12)  # Updated
            self.discharge_ax_R.set_xlabel(discharge_xlabel, fontsize=12)
            self.discharge_ax_k.set_xlabel(discharge_xlabel, fontsize=12)
            self.discharge_ax_k.set_ylabel(r'$k$ ($\Omega \cdot s^{-0.5}$)', fontsize=12)  # Updated
            
            # Redraw canvases
            self.charge_canvas.draw()
            self.discharge_canvas.draw()

    def _get_effective_all_regression_params(self):
        """all_regression_params, with the currently active file's *live*
        regression_params merged in.

        data_tab.py only copies a file's regression_params into
        all_regression_params when switching *away* from it, so the file
        that's currently active is otherwise invisible to overlay mode even
        though its checkbox may be ticked. This merge closes that gap
        without requiring the user to switch away and back first.
        """
        all_reg = dict(self.shared_data.get('all_regression_params', {}))
        active_fname = self.shared_data.get('active_file')
        live_params = self.shared_data.get('regression_params', {})
        if active_fname and live_params:
            all_reg[active_fname] = live_params
        return all_reg

    def _on_xaxis_changed(self, event=None):
        """Re-plot automatically when the X-axis selection changes, but only
        if a plot already exists — avoids popping up 'no data'/'no mass'
        warnings just from browsing the dropdown before anything's plotted."""
        has_existing_plot = (len(self.charge_ax_R.lines) > 0
                              or len(self.discharge_ax_R.lines) > 0)
        if has_existing_plot:
            self.plot_data()

    def _on_kin_overlay_toggled(self):
        """Re-plot immediately when 'Overlay selected files' is checked/
        unchecked, instead of requiring another click on a Plot button."""
        has_existing_plot = (len(self.charge_ax_R.lines) > 0
                              or len(self.discharge_ax_R.lines) > 0)
        if has_existing_plot:
            self.plot_data()

    def _sort_by_x(self, x, *arrays):
        """Sort x and any number of parallel arrays by x ascending.

        The connecting line in errorbar() is drawn in whatever order the
        arrays are given — pulse order, not x-order. That's fine for Voltage
        (roughly monotonic with pulse order already), but Capacity/Specific
        Capacity come from a nearest-voltage match that isn't guaranteed to
        be monotonic pulse-to-pulse (ICI's relaxation/IR-drop behavior means
        pre-pulse voltage can dip back down), so the line can fold backward
        without this sort even though every point itself is still valid.
        """
        order = np.argsort(x)
        return (x[order],) + tuple(a[order] for a in arrays)

    def _get_xaxis_choice(self):
        """Return (result_dict_key, axis_label) for the current X-axis selection."""
        choice = self.xaxis_var.get()
        if choice.startswith('Specific'):
            return 'specific_capacity', 'Specific Capacity (mAh/g)'
        elif choice.startswith('Capacity'):
            return 'capacity', 'Capacity (mAh)'
        return 'voltages', 'Voltage (V)'

    def _get_mass_for_file(self, fname):
        """Look up the sample mass (mg) entered for `fname` in Classification
        tab's Capacity vs Voltage subtab. Returns 0 (absolute capacity) if
        that file has no mass on record yet."""
        return self.shared_data.get('file_mass_mg', {}).get(fname, 0.0)

    def parse_and_validate_cycles(self):
        """Parse cycle input and validate"""
        input_str = self.cycle_entry.get()
        selected_cycles = ka.parse_cycle_input(input_str, self.cycle_list)
        
        if not selected_cycles:
            self.feedback_label.config(text="No valid cycles", foreground="red")
            return []
        
        feedback = f"Will plot {len(selected_cycles)} cycles: {selected_cycles[:5]}"
        if len(selected_cycles) > 5:
            feedback += f" ... (+{len(selected_cycles)-5} more)"
        self.feedback_label.config(text=feedback, foreground="blue")
        
        return selected_cycles
    
    def plot_data(self):
        """Plot R & k data for selected cycles"""
        # Overlay mode — bypass single file logic entirely
        if self.kin_overlay_var.get() and \
                len(self._get_effective_all_regression_params()) > 0:
            self.plot_overlay()
            return

        if self.df_raw is None:
            messagebox.showwarning("No Data", "Please load data first")
            return
        
        selected_cycles = self.parse_and_validate_cycles()
        if not selected_cycles:
            return
        
        # Check if regression data exists
        if 'regression_params' not in self.shared_data:
            messagebox.showwarning("No Regression Data", 
                "No regression parameters found.\n\n"
                "Please run Regression Analysis (Tab 4) first.\n"
                "The kinetic analysis uses the regression parameters.")
            return
        
        x_key, _ = self._get_xaxis_choice()
        mass_mg = self._get_mass_for_file(self.shared_data.get('active_file'))
        if x_key == 'specific_capacity' and mass_mg <= 0:
            messagebox.showwarning("No Mass Set",
                "No sample mass has been entered for this file yet.\n\n"
                "Go to Classification tab → Capacity vs Voltage, enter the mass, "
                "and plot capacity there once, then come back here.")
            return

        try:
            self.update_status("Computing R & k values...")

            # Get saved regression parameters
            saved_params = self.shared_data.get('regression_params', {})

            # Plot charge
            self.plot_charge(selected_cycles, saved_params, mass_mg)

            # Plot discharge
            self.plot_discharge(selected_cycles, saved_params, mass_mg)

            self.update_status(f"Plotted R & k for {len(selected_cycles)} cycles")
            
        except Exception as e:
            self.update_status(f"Plot error: {str(e)}", error=True)
            import traceback
            traceback.print_exc()
            messagebox.showerror("Plot Error", f"Error creating plots:\n{str(e)}")
    
    def plot_overlay(self):
        """Plot R & k for all selected files, one colour per file, shaded by cycle."""
        x_key, x_label = self._get_xaxis_choice()
        self._charge_xlabel = x_label
        self._discharge_xlabel = x_label
        all_reg = self._get_effective_all_regression_params()
        loaded = self.shared_data.get('loaded_files', {})

        # Filter to checked files only
        selected_files = {fname: params for fname, params in all_reg.items()
                          if self.kin_file_check_vars.get(fname, tk.BooleanVar(value=True)).get()
                          and params}

        if not selected_files:
            checked_fnames = [f for f, v in self.kin_file_check_vars.items() if v.get()]
            if not checked_fnames:
                detail = "No files are checked in the Multi-File panel."
            else:
                lines = []
                for f in checked_fnames:
                    short = os.path.basename(f)
                    n_params = len(all_reg.get(f, {}))
                    lines.append(f"  • {short}: {n_params} saved regression parameter(s)")
                detail = ("Checked files and their saved regression parameter count:\n"
                          + "\n".join(lines)
                          + "\n\nEach file needs at least one saved regression parameter "
                            "(Regression tab → save a fit) before it can appear in overlay.")
            messagebox.showwarning("No Files Selected", detail)
            self.update_status("Overlay: no checked file has saved regression parameters", error=True)
            return

        # Clear colorbars and axes
        for cb in [self.charge_colorbar_R, self.charge_colorbar_k,
                   self.discharge_colorbar_R, self.discharge_colorbar_k]:
            if cb is not None:
                try:
                    cb.remove()
                except Exception:
                    pass
        self.charge_colorbar_R = self.charge_colorbar_k = None
        self.discharge_colorbar_R = self.discharge_colorbar_k = None

        try:
            self.charge_fig.delaxes(self.charge_ax_R)
            self.charge_fig.delaxes(self.charge_ax_k)
        except Exception:
            pass
        try:
            self.discharge_fig.delaxes(self.discharge_ax_R)
            self.discharge_fig.delaxes(self.discharge_ax_k)
        except Exception:
            pass

        self.charge_ax_R    = self.charge_fig.add_subplot(211)
        self.charge_ax_k    = self.charge_fig.add_subplot(212)
        self.discharge_ax_R = self.discharge_fig.add_subplot(211)
        self.discharge_ax_k = self.discharge_fig.add_subplot(212)

        charge_legend    = []
        discharge_legend = []
        skipped_no_mass  = []

        orig_keys = list(all_reg.keys())

        for fname, saved_params in selected_files.items():
            orig_idx = orig_keys.index(fname)
            base_color = self._get_overlay_color(orig_idx)
            short = os.path.basename(fname)
            rec = loaded.get(fname)
            if rec is None:
                continue

            # Get cycles for this file from the panel entry
            file_vars = self.kin_file_vars.get(fname, {})
            try:
                cycles_str = file_vars['cycles_var'].get() if file_vars else ''
                selected_cycles = ka.parse_cycle_input(cycles_str, rec['cycle_list']) \
                    if cycles_str else rec['cycle_list']
            except Exception:
                selected_cycles = rec['cycle_list']

            if not selected_cycles:
                continue

            total_cycles = len(selected_cycles)

            # Sync ka with this file's data
            ka.df_raw = rec['df_raw']
            ka.cycle_list = rec['cycle_list']

            mass_mg = self._get_mass_for_file(fname)
            if x_key == 'specific_capacity' and mass_mg <= 0:
                # No mass on record for this file — skip it rather than plot a
                # column of NaNs; other checked files still get plotted.
                skipped_no_mass.append(short)
                continue

            # --- CHARGE ---
            charge_results = ka.compute_R_k_for_cycles(
                selected_cycles, 'charge', ka.DEFAULT_R1S, ka.DEFAULT_R1L, saved_params, mass_mg)

            for idx, result in enumerate(charge_results):
                x_vals   = result[x_key]
                R_vals   = np.abs(result['R'])
                R_errs   = np.abs(result['R_err'])
                k_vals   = np.abs(result['k'])
                k_errs   = np.abs(result['k_err'])
                cycle_num = result['cycle']

                valid_mask = ~(np.isnan(x_vals) | np.isnan(R_vals) | np.isnan(k_vals))
                if not np.any(valid_mask):
                    continue

                color = self._get_cycle_shade(base_color, idx, total_cycles)
                label = f"{short} C{cycle_num}"

                x_plot, R_plot, R_err_plot, k_plot, k_err_plot = self._sort_by_x(
                    x_vals[valid_mask], R_vals[valid_mask], R_errs[valid_mask],
                    k_vals[valid_mask], k_errs[valid_mask])

                self.charge_ax_R.errorbar(x_plot, R_plot,
                                           yerr=R_err_plot, fmt='o-',
                                           color=color, label=label,
                                           markersize=4, alpha=0.8, capsize=2)
                self.charge_ax_k.errorbar(x_plot, k_plot,
                                           yerr=k_err_plot, fmt='o-',
                                           color=color, label='_nolegend_',
                                           markersize=4, alpha=0.8, capsize=2)

            if charge_results:
                charge_legend.append(
                    Line2D([0], [0], color=base_color, marker='o',
                           label=f"{short} (charge)", markersize=6))

            # --- DISCHARGE ---
            discharge_results = ka.compute_R_k_for_cycles(
                selected_cycles, 'discharge', ka.DEFAULT_R1S, ka.DEFAULT_R1L, saved_params, mass_mg)

            for idx, result in enumerate(discharge_results):
                x_vals   = result[x_key]
                R_vals   = np.abs(result['R'])
                R_errs   = np.abs(result['R_err'])
                k_vals   = np.abs(result['k'])
                k_errs   = np.abs(result['k_err'])
                cycle_num = result['cycle']

                valid_mask = ~(np.isnan(x_vals) | np.isnan(R_vals) | np.isnan(k_vals))
                if not np.any(valid_mask):
                    continue

                color = self._get_cycle_shade(base_color, idx, total_cycles)
                label = f"{short} C{cycle_num}"

                x_plot, R_plot, R_err_plot, k_plot, k_err_plot = self._sort_by_x(
                    x_vals[valid_mask], R_vals[valid_mask], R_errs[valid_mask],
                    k_vals[valid_mask], k_errs[valid_mask])

                self.discharge_ax_R.errorbar(x_plot, R_plot,
                                              yerr=R_err_plot, fmt='s--',
                                              color=color, label=label,
                                              markersize=4, alpha=0.8, capsize=2)
                self.discharge_ax_k.errorbar(x_plot, k_plot,
                                              yerr=k_err_plot, fmt='s--',
                                              color=color, label='_nolegend_',
                                              markersize=4, alpha=0.8, capsize=2)

            if discharge_results:
                discharge_legend.append(
                    Line2D([0], [0], color=base_color, marker='s', linestyle='--',
                           label=f"{short} (discharge)", markersize=6))

        # --- Formatting charge ---
        if self.show_title_var.get():
            self.charge_ax_R.set_title('Charge — Overlay', fontsize=13,
                                        fontweight='bold', color='blue')
        self.charge_ax_R.set_ylabel(r'Internal resistance, $R$ ($\Omega$)', fontsize=12)
        self.charge_ax_R.set_xlabel(x_label, fontsize=12)
        self.charge_ax_R.grid(True, alpha=0.3)
        self.charge_ax_k.set_ylabel(r'$k$ ($\Omega \cdot s^{-0.5}$)', fontsize=12)
        self.charge_ax_k.set_xlabel(x_label, fontsize=12)
        self.charge_ax_k.grid(True, alpha=0.3)

        if charge_legend:
            leg = self.charge_ax_R.legend(handles=charge_legend, fontsize=8,
                                           bbox_to_anchor=(1.05, 1), loc='upper left')
            leg.set_draggable(True)
            leg.get_frame().set_facecolor('white')
            leg.get_frame().set_alpha(0.9)

        # --- Formatting discharge ---
        if self.show_title_var.get():
            self.discharge_ax_R.set_title('Discharge — Overlay', fontsize=13,
                                           fontweight='bold', color='red')
        self.discharge_ax_R.set_ylabel(r'Internal resistance, $R$ ($\Omega$)', fontsize=12)
        self.discharge_ax_R.set_xlabel(x_label, fontsize=12)
        self.discharge_ax_R.grid(True, alpha=0.3)
        self.discharge_ax_k.set_ylabel(r'$k$ ($\Omega \cdot s^{-0.5}$)', fontsize=12)
        self.discharge_ax_k.set_xlabel(x_label, fontsize=12)
        self.discharge_ax_k.grid(True, alpha=0.3)

        if discharge_legend:
            leg = self.discharge_ax_R.legend(handles=discharge_legend, fontsize=8,
                                              bbox_to_anchor=(1.05, 1), loc='upper left')
            leg.set_draggable(True)
            leg.get_frame().set_facecolor('white')
            leg.get_frame().set_alpha(0.9)

        self.charge_fig.tight_layout()
        self.discharge_fig.tight_layout()
        self.charge_canvas.draw()
        self.discharge_canvas.draw()

        if skipped_no_mass:
            self.update_status(
                f"Overlay: {len(selected_files) - len(skipped_no_mass)} files plotted, "
                f"skipped (no mass): {', '.join(skipped_no_mass)}", error=True)
        else:
            self.update_status(f"Overlay: {len(selected_files)} files plotted")

    def plot_charge(self, selected_cycles, saved_params, mass_mg=0):
        """Plot charge R & k with SMART COLORMAP SYSTEM (consistent layout)"""
        x_key, x_label = self._get_xaxis_choice()
        self._charge_xlabel = x_label
        
        # CRITICAL FIX 1: Remove old colorbars FIRST, BEFORE clearing axes
        # This prevents progressive shrinking from stacked colorbars
        if self.charge_colorbar_R is not None:
            try:
                self.charge_colorbar_R.remove()
            except:
                pass
            self.charge_colorbar_R = None
        if self.charge_colorbar_k is not None:
            try:
                self.charge_colorbar_k.remove()
            except:
                pass
            self.charge_colorbar_k = None
        
        # CRITICAL FIX 2: Clear and REDEFINE axes to force preservation of reserved space
        try:
            self.charge_fig.delaxes(self.charge_ax_R)
            self.charge_fig.delaxes(self.charge_ax_k)
        except AttributeError:
            # Handle case where axes might not exist yet (first run)
            pass

        self.charge_ax_R = self.charge_fig.add_subplot(211)
        self.charge_ax_k = self.charge_fig.add_subplot(212)
        
        charge_results = ka.compute_R_k_for_cycles(
            selected_cycles,
            'charge',
            ka.DEFAULT_R1S,
            ka.DEFAULT_R1L,
            saved_params,
            mass_mg
        )

        if not charge_results:
            self.charge_ax_R.text(0.5, 0.5, 'No charge data', 
                                ha='center', va='center', 
                                transform=self.charge_ax_R.transAxes)
            self.charge_canvas.draw()
            return
        
        # SMART COLORMAP SYSTEM
        charge_cmap = plt.colormaps['Blues']
        num_cycles = len(charge_results)
        
        # Decide: legend (<= 10 cycles) or colorbar (> 10 cycles)?
        use_colorbar = (num_cycles > 10)
        
        for idx, result in enumerate(charge_results):
            x_vals = result[x_key]
            R_vals = result['R']
            R_errs = result['R_err']
            k_vals = result['k']
            k_errs = result['k_err']
            cycle_num = result['cycle']

            valid_mask = ~(np.isnan(x_vals) | np.isnan(R_vals) | np.isnan(k_vals))

            if not np.any(valid_mask):
                continue

            # Color calculation
            if use_colorbar:
                min_c = min(selected_cycles)
                max_c = max(selected_cycles)
                if max_c == min_c: # Handle single cycle case
                    cycle_normalized = 0
                else:
                    cycle_normalized = (cycle_num - min_c) / (max_c - min_c)

                color_intensity = 0.4 + 0.6 * cycle_normalized  # Keep 0.4+0.6 range for Blues
                color = charge_cmap(color_intensity)
                # No label when using colorbar
                label_R = None
                label_k = None
            else:
                # Use index for distinct colors (few cycles)
                color_intensity = 0.4 + 0.6 * (idx / max(1, num_cycles - 1))
                color = charge_cmap(color_intensity)
                # Label for legend
                label_suffix = f' C{cycle_num}' if num_cycles > 1 else ''
                label_R = f'R{label_suffix}'
                label_k = f'k{label_suffix}'

            # MODIFIED: Use absolute values for R, k, and their error bars
            R_vals_abs = np.abs(R_vals[valid_mask])
            R_errs_abs = np.abs(R_errs[valid_mask])
            k_vals_abs = np.abs(k_vals[valid_mask])
            k_errs_abs = np.abs(k_errs[valid_mask])

            # Sort by x so the connecting line progresses monotonically
            # instead of following pulse order (see _sort_by_x docstring)
            x_plot, R_plot, R_err_plot, k_plot, k_err_plot = self._sort_by_x(
                x_vals[valid_mask], R_vals_abs, R_errs_abs, k_vals_abs, k_errs_abs)

            # Plot R with absolute values and absolute error bars
            self.charge_ax_R.errorbar(
                x_plot,
                R_plot,  # Absolute values
                yerr=R_err_plot,  # Absolute error bars
                fmt='o-',
                color=color,
                label=label_R,
                markersize=5,
                alpha=0.8,
                capsize=3
            )

            # Plot k with absolute values and absolute error bars
            self.charge_ax_k.errorbar(
                x_plot,
                k_plot,  # Absolute values
                yerr=k_err_plot,  # Absolute error bars
                fmt='o-',
                color=color,
                label=label_k,
                markersize=5,
                alpha=0.8,
                capsize=3
            )
        
        # Title and Labels
        cycles_text = f"Cycles {selected_cycles}" if num_cycles > 1 else f"Cycle {selected_cycles[0]}"

        # Conditional title
        if self.show_title_var.get():
            self.charge_ax_R.set_title(f'Charge - {cycles_text} (Absolute Values)',  # Added note
                                    fontsize=13, fontweight='bold', color='blue')
        else:
            self.charge_ax_R.set_title('')

        # FIX 1 & 2: Axis labels
        self.charge_ax_R.set_ylabel(r'Internal resistance, $R$ ($\Omega$)', fontsize=12)
        self.charge_ax_R.grid(True, alpha=0.3)
        self.charge_ax_R.set_xlabel(x_label, fontsize=12)

        self.charge_ax_k.set_xlabel(x_label, fontsize=12)
        self.charge_ax_k.set_ylabel(r'$k$ ($\Omega \cdot s^{-0.5}$)', fontsize=12)
        self.charge_ax_k.grid(True, alpha=0.3)
        
        # LEGEND OR COLORBAR - uses the reserved 15% space on right
        # Ensure previous legends/colorbars are removed before adding new ones
        if self.charge_ax_R.get_legend(): self.charge_ax_R.get_legend().remove()
        if self.charge_ax_k.get_legend(): self.charge_ax_k.get_legend().remove()
        
        if use_colorbar:
            # Many cycles: Add TWO colorbars (one for R, one for k)
            from matplotlib.cm import ScalarMappable
            from matplotlib.colors import Normalize
            
            # Normalize to 0.4-1.0 range (Blues range)
            norm = Normalize(vmin=min(selected_cycles), vmax=max(selected_cycles))
            sm = ScalarMappable(cmap=charge_cmap, norm=norm)
            sm.set_array([])
            
            # Use same tick logic for both colorbars
            min_cycle = min(selected_cycles)
            max_cycle = max(selected_cycles)
            
            if num_cycles <= 20:
                tick_positions = selected_cycles
            elif num_cycles <= 50:
                tick_positions = [c for c in selected_cycles if c % 5 == 0 or c == min_cycle or c == max_cycle]
            else:
                tick_positions = [c for c in selected_cycles if c % 10 == 0 or c == min_cycle or c == max_cycle]
            
            if min_cycle not in tick_positions:
                tick_positions = [min_cycle] + tick_positions
            if max_cycle not in tick_positions:
                tick_positions.append(max_cycle)
            
            final_ticks = sorted(set(tick_positions))

            # KEY FIX: Create explicit caxes to force height and eliminate blank space
            # IMPROVED: Better alignment with actual plot positions
            # Get actual axes positions for perfect alignment
            r_pos = self.charge_ax_R.get_position()
            k_pos = self.charge_ax_k.get_position()
            
            # Colorbar for R (Top Plot) - aligned with R plot bounds
            cax_R = self.charge_fig.add_axes([0.87, r_pos.y0, 0.03, r_pos.height]) 
            self.charge_colorbar_R = self.charge_fig.colorbar(sm, cax=cax_R)
            
            # FIX 1: Removed fontweight='bold'
            self.charge_colorbar_R.set_label('Cycle Number', rotation=270, labelpad=20, fontsize=11)
            self.charge_colorbar_R.set_ticks(final_ticks)
            self.charge_colorbar_R.set_ticklabels([str(int(t)) for t in final_ticks])
            
            # Colorbar for k (Bottom Plot) - aligned with k plot bounds
            cax_k = self.charge_fig.add_axes([0.87, k_pos.y0, 0.03, k_pos.height])
            self.charge_colorbar_k = self.charge_fig.colorbar(sm, cax=cax_k)
            
            # FIX 1: Removed fontweight='bold'
            self.charge_colorbar_k.set_label('Cycle Number', rotation=270, labelpad=20, fontsize=11)
            self.charge_colorbar_k.set_ticks(final_ticks)
            self.charge_colorbar_k.set_ticklabels([str(int(t)) for t in final_ticks])
            
        else:
            # Few cycles: Show legends (uses same reserved space)
            # Ensure colorbars are removed if this branch is hit
            if self.charge_colorbar_R: self.charge_colorbar_R.remove()
            if self.charge_colorbar_k: self.charge_colorbar_k.remove()
            self.charge_colorbar_R = None
            self.charge_colorbar_k = None
            
            # FIXED: Position legends outside plots without overlap
            # Position at right edge of reserved space, aligned with plot tops
            legend_r = self.charge_ax_R.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9)
            legend_r.set_draggable(True)
            legend_r.get_frame().set_facecolor('white')
            legend_r.get_frame().set_alpha(0.9)
            legend_r.get_frame().set_edgecolor('black')
            
            # Legend for k plot - aligned with k plot top
            legend_k = self.charge_ax_k.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9)
            legend_k.set_draggable(True)
            legend_k.get_frame().set_facecolor('white')
            legend_k.get_frame().set_alpha(0.9)
            legend_k.get_frame().set_edgecolor('black')
        
        # Draw without tight_layout (space already reserved by subplots_adjust)
        self.charge_canvas.draw()
                    
    def plot_discharge(self, selected_cycles, saved_params, mass_mg=0):
        """Plot discharge R & k with SMART COLORMAP SYSTEM (consistent layout)"""
        x_key, x_label = self._get_xaxis_choice()
        self._discharge_xlabel = x_label
        
        # CRITICAL FIX 1: Remove old colorbars FIRST, BEFORE clearing axes
        # This prevents progressive shrinking from stacked colorbars
        if self.discharge_colorbar_R is not None:
            try:
                self.discharge_colorbar_R.remove()
            except:
                pass
            self.discharge_colorbar_R = None
        if self.discharge_colorbar_k is not None:
            try:
                self.discharge_colorbar_k.remove()
            except:
                pass
            self.discharge_colorbar_k = None
        
        # CRITICAL FIX 2: Clear and REDEFINE axes to force preservation of reserved space
        try:
            self.discharge_fig.delaxes(self.discharge_ax_R)
            self.discharge_fig.delaxes(self.discharge_ax_k)
        except AttributeError:
            # Handle case where axes might not exist yet (first run)
            pass

        self.discharge_ax_R = self.discharge_fig.add_subplot(211)
        self.discharge_ax_k = self.discharge_fig.add_subplot(212)
        
        discharge_results = ka.compute_R_k_for_cycles(
            selected_cycles,
            'discharge',
            ka.DEFAULT_R1S,
            ka.DEFAULT_R1L,
            saved_params,
            mass_mg
        )

        if not discharge_results:
            self.discharge_ax_R.text(0.5, 0.5, 'No discharge data',
                                    ha='center', va='center',
                                    transform=self.discharge_ax_R.transAxes)
            self.discharge_canvas.draw()
            return
        
        # SMART COLORMAP SYSTEM
        discharge_cmap = plt.colormaps['Reds']
        num_cycles = len(discharge_results)
        
        # Decide: legend (<= 10 cycles) or colorbar (> 10 cycles)?
        use_colorbar = (num_cycles > 10)
        
        for idx, result in enumerate(discharge_results):
            x_vals = result[x_key]
            R_vals = result['R']
            R_errs = result['R_err']
            k_vals = result['k']
            k_errs = result['k_err']
            cycle_num = result['cycle']

            valid_mask = ~(np.isnan(x_vals) | np.isnan(R_vals) | np.isnan(k_vals))

            if not np.any(valid_mask):
                continue

            # Color calculation
            if use_colorbar:
                min_c = min(selected_cycles)
                max_c = max(selected_cycles)
                if max_c == min_c: # Handle single cycle case
                    cycle_normalized = 0
                else:
                    cycle_normalized = (cycle_num - min_c) / (max_c - min_c)

                color_intensity = 0.4 + 0.6 * cycle_normalized  # Keep 0.4+0.6 range for Reds
                color = discharge_cmap(color_intensity)
                # No label when using colorbar
                label_R = None
                label_k = None
            else:
                # Use index for distinct colors (few cycles)
                color_intensity = 0.4 + 0.6 * (idx / max(1, num_cycles - 1))
                color = discharge_cmap(color_intensity)
                # Label for legend
                label_suffix = f' C{cycle_num}' if num_cycles > 1 else ''
                label_R = f'R{label_suffix}'
                label_k = f'k{label_suffix}'

            # MODIFIED: Use absolute values for R, k, and their error bars
            R_vals_abs = np.abs(R_vals[valid_mask])
            R_errs_abs = np.abs(R_errs[valid_mask])
            k_vals_abs = np.abs(k_vals[valid_mask])
            k_errs_abs = np.abs(k_errs[valid_mask])

            # Sort by x so the connecting line progresses monotonically
            # instead of following pulse order (see _sort_by_x docstring)
            x_plot, R_plot, R_err_plot, k_plot, k_err_plot = self._sort_by_x(
                x_vals[valid_mask], R_vals_abs, R_errs_abs, k_vals_abs, k_errs_abs)

            # Plot R with absolute values and absolute error bars
            self.discharge_ax_R.errorbar(
                x_plot,
                R_plot,  # Absolute values
                yerr=R_err_plot,  # Absolute error bars
                fmt='s-',
                color=color,
                label=label_R,
                markersize=5,
                alpha=0.8,
                capsize=3
            )

            # Plot k with absolute values and absolute error bars
            self.discharge_ax_k.errorbar(
                x_plot,
                k_plot,  # Absolute values
                yerr=k_err_plot,  # Absolute error bars
                fmt='s-',
                color=color,
                label=label_k,
                markersize=5,
                alpha=0.8,
                capsize=3
            )
        
        # Title and Labels
        cycles_text = f"Cycles {selected_cycles}" if num_cycles > 1 else f"Cycle {selected_cycles[0]}"

        # Conditional title
        if self.show_title_var.get():
            self.discharge_ax_R.set_title(f'Discharge - {cycles_text} (Absolute Values)',  # Added note
                                        fontsize=13, fontweight='bold', color='red')
        else:
            self.discharge_ax_R.set_title('')
        
        # FIX 1 & 2: Axis labels
        self.discharge_ax_R.set_ylabel(r'Internal resistance, $R$ ($\Omega$)', fontsize=12)
        self.discharge_ax_R.grid(True, alpha=0.3)
        self.discharge_ax_R.set_xlabel(x_label, fontsize=12)

        self.discharge_ax_k.set_xlabel(x_label, fontsize=12)
        self.discharge_ax_k.set_ylabel(r'$k$ ($\Omega \cdot s^{-0.5}$)', fontsize=12)
        self.discharge_ax_k.grid(True, alpha=0.3)
        
        # LEGEND OR COLORBAR - uses the reserved 15% space on right
        # Ensure previous legends/colorbars are removed before adding new ones
        if self.discharge_ax_R.get_legend(): self.discharge_ax_R.get_legend().remove()
        if self.discharge_ax_k.get_legend(): self.discharge_ax_k.get_legend().remove()

        if use_colorbar:
            # Many cycles: Add TWO colorbars (one for R, one for k)
            from matplotlib.cm import ScalarMappable
            from matplotlib.colors import Normalize
            
            # Normalize to 0.4-1.0 range (Reds range)
            norm = Normalize(vmin=min(selected_cycles), vmax=max(selected_cycles))
            sm = ScalarMappable(cmap=discharge_cmap, norm=norm)
            sm.set_array([])
            
            # Use same tick logic for both colorbars
            min_cycle = min(selected_cycles)
            max_cycle = max(selected_cycles)
            
            if num_cycles <= 20:
                tick_positions = selected_cycles
            elif num_cycles <= 50:
                tick_positions = [c for c in selected_cycles if c % 5 == 0 or c == min_cycle or c == max_cycle]
            else:
                tick_positions = [c for c in selected_cycles if c % 10 == 0 or c == min_cycle or c == max_cycle]
            
            if min_cycle not in tick_positions:
                tick_positions = [min_cycle] + tick_positions
            if max_cycle not in tick_positions:
                tick_positions.append(max_cycle)
            
            final_ticks = sorted(set(tick_positions))

            # KEY FIX: Create explicit caxes to force height and eliminate blank space
            # IMPROVED: Better alignment with actual plot positions
            # Get actual axes positions for perfect alignment
            r_pos = self.discharge_ax_R.get_position()
            k_pos = self.discharge_ax_k.get_position()
            
            # Colorbar for R (Top Plot) - aligned with R plot bounds
            cax_R = self.discharge_fig.add_axes([0.87, r_pos.y0, 0.03, r_pos.height]) 
            self.discharge_colorbar_R = self.discharge_fig.colorbar(sm, cax=cax_R)
            
            # FIX 1: Removed fontweight='bold'
            self.discharge_colorbar_R.set_label('Cycle Number', rotation=270, labelpad=20, fontsize=11)
            self.discharge_colorbar_R.set_ticks(final_ticks)
            self.discharge_colorbar_R.set_ticklabels([str(int(t)) for t in final_ticks])
            
            # Colorbar for k (Bottom Plot) - aligned with k plot bounds
            cax_k = self.discharge_fig.add_axes([0.87, k_pos.y0, 0.03, k_pos.height])
            self.discharge_colorbar_k = self.discharge_fig.colorbar(sm, cax=cax_k)
            
            # FIX 1: Removed fontweight='bold'
            self.discharge_colorbar_k.set_label('Cycle Number', rotation=270, labelpad=20, fontsize=11)
            self.discharge_colorbar_k.set_ticks(final_ticks)
            self.discharge_colorbar_k.set_ticklabels([str(int(t)) for t in final_ticks])
            
        else:
            # Few cycles: Show legends (uses same reserved space)
            # Ensure colorbars are removed if this branch is hit
            if self.discharge_colorbar_R: self.discharge_colorbar_R.remove()
            if self.discharge_colorbar_k: self.discharge_colorbar_k.remove()
            self.discharge_colorbar_R = None
            self.discharge_colorbar_k = None
            
            # FIXED: Position legends outside plots without overlap
            # Position at right edge of reserved space, aligned with plot tops
            legend_r = self.discharge_ax_R.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9)
            legend_r.set_draggable(True)
            legend_r.get_frame().set_facecolor('white')
            legend_r.get_frame().set_alpha(0.9)
            legend_r.get_frame().set_edgecolor('black')
            
            # Legend for k plot - aligned with k plot top
            legend_k = self.discharge_ax_k.legend(bbox_to_anchor=(1.02, 1.0), loc='upper left', fontsize=9)
            legend_k.set_draggable(True)
            legend_k.get_frame().set_facecolor('white')
            legend_k.get_frame().set_alpha(0.9)
            legend_k.get_frame().set_edgecolor('black')
        
        # Draw without tight_layout (space already reserved by subplots_adjust)
        self.discharge_canvas.draw()
    
    def export_data(self):
        """Export R & k data to CSV with folder selection and filename prefix"""

        # Overlay mode — export all selected files independently
        if self.kin_overlay_var.get() and \
                len(self._get_effective_all_regression_params()) > 0:
            self.export_data_overlay()
            return

        if self.df_raw is None:
            messagebox.showwarning("No Data", "Please load data first")
            return
        
        selected_cycles = self.parse_and_validate_cycles()
        if not selected_cycles:
            return
        
        # Ask user to select output folder
        output_folder = filedialog.askdirectory(
            title="Select Export Folder",
            initialdir=self.shared_data.get('last_folder', os.path.expanduser("~"))
        )
        
        if not output_folder:
            self.update_status("Export cancelled by user")
            return
        
        self.shared_data['last_folder'] = output_folder
        
        try:
            saved_params = self.shared_data.get('regression_params', {})
            filename = self.shared_data.get('filename', '')
            filename_prefix = os.path.splitext(filename)[0] if filename else "kinetic_analysis"
            mass_mg = self._get_mass_for_file(self.shared_data.get('active_file'))

            success = ka.export_R_k_results(
                selected_cycles, ka.DEFAULT_R1S, ka.DEFAULT_R1L,
                saved_params, output_folder, filename_prefix, mass_mg)
            
            if success:
                messagebox.showinfo("Export Complete", 
                    f"Exported R & k data for {len(selected_cycles)} cycles\n\n"
                    f"Folder: {output_folder}\n"
                    f"Files: {filename_prefix}_R_k_results_charge.csv\n"
                    f"        {filename_prefix}_R_k_results_discharge.csv")
                self.update_status(f"Exported R & k for {len(selected_cycles)} cycles to {output_folder}")
            else:
                messagebox.showerror("Export Failed", "Failed to export data")
                self.update_status("Export failed", error=True)
                
        except Exception as e:
            messagebox.showerror("Export Error", f"Error exporting data:\n{str(e)}")
            self.update_status(f"Export error: {str(e)}", error=True)
            import traceback
            traceback.print_exc()

    def export_data_overlay(self):
        """Export R & k data for all selected files in overlay mode."""
        all_reg = self._get_effective_all_regression_params()
        loaded = self.shared_data.get('loaded_files', {})

        selected_files = {fname: params for fname, params in all_reg.items()
                          if self.kin_file_check_vars.get(fname, tk.BooleanVar(value=True)).get()
                          and params}

        if not selected_files:
            checked_fnames = [f for f, v in self.kin_file_check_vars.items() if v.get()]
            if not checked_fnames:
                detail = "No files are checked in the Multi-File panel."
            else:
                lines = []
                for f in checked_fnames:
                    short = os.path.basename(f)
                    n_params = len(all_reg.get(f, {}))
                    lines.append(f"  • {short}: {n_params} saved regression parameter(s)")
                detail = ("Checked files and their saved regression parameter count:\n"
                          + "\n".join(lines)
                          + "\n\nEach file needs at least one saved regression parameter "
                            "(Regression tab → save a fit) before it can be exported in overlay.")
            messagebox.showwarning("No Files Selected", detail)
            return

        output_folder = filedialog.askdirectory(
            title="Select Export Folder",
            initialdir=self.shared_data.get('last_folder', os.path.expanduser("~")))

        if not output_folder:
            self.update_status("Export cancelled by user")
            return

        self.shared_data['last_folder'] = output_folder

        exported = []
        failed = []

        for fname, saved_params in selected_files.items():
            rec = loaded.get(fname)
            if rec is None:
                failed.append(os.path.basename(fname))
                continue

            # Get cycles for this file from the panel entry
            file_vars = self.kin_file_vars.get(fname, {})
            try:
                cycles_str = file_vars['cycles_var'].get() if file_vars else ''
                selected_cycles = ka.parse_cycle_input(cycles_str, rec['cycle_list']) \
                    if cycles_str else rec['cycle_list']
            except Exception:
                selected_cycles = rec['cycle_list']

            if not selected_cycles:
                continue

            # Sync ka with this file
            ka.df_raw = rec['df_raw']
            ka.cycle_list = rec['cycle_list']

            filename_prefix = os.path.splitext(os.path.basename(fname))[0]
            mass_mg = self._get_mass_for_file(fname)

            try:
                success = ka.export_R_k_results(
                    selected_cycles, ka.DEFAULT_R1S, ka.DEFAULT_R1L,
                    saved_params, output_folder, filename_prefix, mass_mg)
                if success:
                    exported.append(filename_prefix)
                else:
                    failed.append(filename_prefix)
            except Exception as e:
                failed.append(filename_prefix)
                print(f"Export error for {fname}: {e}")

        # Restore active file ka state
        if self.df_raw is not None:
            ka.df_raw = self.df_raw
            ka.cycle_list = self.cycle_list

        msg = f"Exported {len(exported)} files to:\n{output_folder}\n\n"
        if exported:
            msg += "✅ " + "\n✅ ".join(exported)
        if failed:
            msg += "\n\n❌ Failed:\n" + "\n".join(failed)

        messagebox.showinfo("Export Complete", msg)
        self.update_status(f"Overlay export: {len(exported)} files exported to {output_folder}")
    
    def update_status(self, message, error=False):
        """Update the bottom status bar"""
        if error:
            self.bottom_status.config(text=f"{message}", foreground='red')
        else:
            self.bottom_status.config(text=message, foreground='black')