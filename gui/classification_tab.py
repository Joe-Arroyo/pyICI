#!/usr/bin/env python3
"""
Classification Tab - GUI for ICI Battery Analysis Phase Classification & Capacity Analysis
Uses the actual phase_classifier.py functions following established workflow pattern
NEW: Added Capacity vs Voltage plotting as second subtab
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import pandas as pd
import numpy as np

# Import the actual phase_classifier module
import analysis.phase_classifier as phase_classifier

def export_figure(fig, filepath, width_in=8, height_in=6, dpi=300):
    """Simple figure export function"""
    # Store original size
    original_size = fig.get_size_inches()
    original_titles = []
    for ax in fig.axes:
        original_titles.append(ax.get_title())
        ax.set_title("")  # Remove title for export
    
    try:
        # Set new size
        fig.set_size_inches(width_in, height_in)
        
        # Save with tight layout
        fig.savefig(filepath, dpi=dpi, bbox_inches='tight', facecolor='white')
        
    finally:
        # Restore original size
        fig.set_size_inches(original_size)

class ClassificationTab:
    def __init__(self, parent, shared_data):
        """
        Initialize Classification Tab with Phase Classification and Capacity Analysis
        
        Args:
            parent: Parent frame (notebook tab)
            shared_data: Dictionary to share data between tabs
        """
        self.parent = parent
        self.shared_data = shared_data
        
        # Data storage - will reference shared_data from Data Tab
        self.df_raw = None
        self.cycle_list = []
        self.classified_data = None
        self.current_cycle = None
        self.phase_stats = {}
        
        # Colorbar tracking (to prevent stacking) - separate for each tab
        self.phase_colorbar = None
        self.capacity_colorbar = None
        
        # Title storage for toggle functionality
        self._phase_multi_title = ""
        self._phase_single_title = ""
        self._capacity_title = ""
        
        # Shared title toggle variable (must be defined before create_widgets)
        self.show_title_var = tk.BooleanVar(value=True)
        
        # Shared legend toggle variable
        self.show_legend_var = tk.BooleanVar(value=True)
        
        # Create GUI with notebook structure
        self.create_widgets()
        
        # Try to load data from shared_data if available
        self.load_shared_data()
    
    def create_widgets(self):
        """Create notebook with Phase Classification and Capacity Analysis tabs"""
        
        # Create notebook for subtabs
        self.notebook = ttk.Notebook(self.parent)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Phase Classification (existing functionality)
        self.phase_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.phase_frame, text="Phase Classification")
        self.create_phase_tab()
        
        # Tab 2: Capacity vs Voltage (new functionality)
        self.capacity_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.capacity_frame, text="Capacity vs Voltage")
        self.create_capacity_tab()
        
        # Status bar for entire tab
        self.status_label = ttk.Label(self.parent, text="Ready - Load data in Data Tab first", 
                                      relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def create_phase_tab(self):
        """Create Phase Classification tab (existing functionality)"""
        
        # Top control frame
        control_frame = ttk.Frame(self.phase_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        # Create horizontal frame for Controls and Statistics side by side
        controls_stats_frame = ttk.Frame(control_frame)
        controls_stats_frame.pack(fill=tk.BOTH, expand=True)
        
        # Left side: Classification controls
        class_frame = ttk.LabelFrame(controls_stats_frame, text="Phase Classification Controls", padding=10)
        class_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # Single cycle controls
        single_frame = ttk.Frame(class_frame)
        single_frame.grid(row=0, column=0, columnspan=4, sticky=tk.EW, pady=(0,10))
        
        ttk.Label(single_frame, text="Single Cycle:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.cycle_var = tk.StringVar()
        self.cycle_combo = ttk.Combobox(single_frame, textvariable=self.cycle_var, 
                                       width=15, state='readonly')
        self.cycle_combo.grid(row=0, column=1, padx=5, sticky=tk.W)
        self.cycle_combo.bind('<<ComboboxSelected>>', self.on_cycle_selected)
        
        ttk.Button(single_frame, text="Plot Cycle", 
                  command=self.classify_and_plot_single_cycle).grid(row=0, column=2, padx=10)
        
        # Multi-cycle controls
        multi_frame = ttk.Frame(class_frame)
        multi_frame.grid(row=1, column=0, columnspan=4, sticky=tk.EW, pady=(10,0))
        
        ttk.Label(multi_frame, text="Multi-Cycle:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.multi_cycle_var = tk.StringVar()
        self.multi_cycle_entry = ttk.Entry(multi_frame, textvariable=self.multi_cycle_var, width=30)
        self.multi_cycle_entry.grid(row=0, column=1, padx=5, sticky=tk.EW)
        self.multi_cycle_entry.insert(0, "1,2,3")  # Default example
        
        ttk.Button(multi_frame, text="Plot Selected Cycles", 
                  command=self.classify_and_plot_multi_cycles).grid(row=0, column=2, padx=10)
        ttk.Button(multi_frame, text="Plot All Cycles", 
                  command=self.classify_and_plot_all_cycles).grid(row=0, column=3, padx=5)
        
        multi_frame.columnconfigure(1, weight=1)
        
        # Help text
        help_label = ttk.Label(class_frame, text="Multi-cycle format: '1,3,5' or '1-5' or '1,3-7,10'", 
                              font=('Arial', 8), foreground='gray')
        help_label.grid(row=2, column=0, columnspan=4, sticky=tk.W, padx=5, pady=(5,0))
        
        # Title toggle checkbox
        ttk.Checkbutton(class_frame, text="Show plot titles", 
                       variable=self.show_title_var,
                       command=self.refresh_titles).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,0))
        
        # Legend toggle checkbox
        ttk.Checkbutton(class_frame, text="Show legend/colorbar", 
                       variable=self.show_legend_var,
                       command=self.toggle_legend).grid(row=3, column=2, columnspan=2, sticky=tk.W, padx=5, pady=(10,0))
        
        # Combined frame for Axis Limits and Export (side by side)
        combined_frame = ttk.Frame(class_frame)
        combined_frame.grid(row=4, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=(10,0))
        
        # Left side: Axis limits controls for Phase Classification
        limits_frame = ttk.LabelFrame(combined_frame, text="Axis Limits", padding=5)
        limits_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # X-axis limits (Time in hours)
        ttk.Label(limits_frame, text="X-axis (Time h):").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Label(limits_frame, text="Min:").grid(row=0, column=1, sticky=tk.W, padx=(10,2))
        self.phase_x_min_var = tk.StringVar()
        ttk.Entry(limits_frame, textvariable=self.phase_x_min_var, width=8).grid(row=0, column=2, padx=2)
        ttk.Label(limits_frame, text="Max:").grid(row=0, column=3, sticky=tk.W, padx=(10,2))
        self.phase_x_max_var = tk.StringVar()
        ttk.Entry(limits_frame, textvariable=self.phase_x_max_var, width=8).grid(row=0, column=4, padx=2)
        
        # Y-axis limits (Voltage)
        ttk.Label(limits_frame, text="Y-axis (Voltage V):").grid(row=1, column=0, sticky=tk.W, padx=5)
        ttk.Label(limits_frame, text="Min:").grid(row=1, column=1, sticky=tk.W, padx=(10,2))
        self.phase_y_min_var = tk.StringVar()
        ttk.Entry(limits_frame, textvariable=self.phase_y_min_var, width=8).grid(row=1, column=2, padx=2)
        ttk.Label(limits_frame, text="Max:").grid(row=1, column=3, sticky=tk.W, padx=(10,2))
        self.phase_y_max_var = tk.StringVar()
        ttk.Entry(limits_frame, textvariable=self.phase_y_max_var, width=8).grid(row=1, column=4, padx=2)
        
        # Buttons
        ttk.Button(limits_frame, text="Apply Limits", 
                  command=self.apply_phase_limits).grid(row=0, column=5, padx=10, rowspan=2)
        ttk.Button(limits_frame, text="Auto Scale", 
                  command=self.auto_scale_phase).grid(row=0, column=6, padx=5, rowspan=2)

        # Right side: Export controls for Phase Classification
        phase_export_frame = ttk.LabelFrame(combined_frame, text="Export Plot", padding=5)
        phase_export_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(phase_export_frame, text="Width (in):").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.phase_export_width_var = tk.DoubleVar(value=8.0)
        ttk.Entry(phase_export_frame, textvariable=self.phase_export_width_var, width=6).grid(row=0, column=1, padx=2)

        ttk.Label(phase_export_frame, text="Height (in):").grid(row=1, column=0, sticky=tk.W, padx=2)
        self.phase_export_height_var = tk.DoubleVar(value=6.0)
        ttk.Entry(phase_export_frame, textvariable=self.phase_export_height_var, width=6).grid(row=1, column=1, padx=2)

        ttk.Label(phase_export_frame, text="DPI:").grid(row=0, column=2, sticky=tk.W, padx=(10,2))
        self.phase_export_dpi_var = tk.IntVar(value=300)
        ttk.Entry(phase_export_frame, textvariable=self.phase_export_dpi_var, width=6).grid(row=0, column=3, padx=2)

        ttk.Label(phase_export_frame, text="Format:").grid(row=1, column=2, sticky=tk.W, padx=(10,2))
        self.phase_export_format_var = tk.StringVar(value="png")
        ttk.Combobox(
            phase_export_frame,
            textvariable=self.phase_export_format_var,
            values=["png", "pdf", "svg"],
            width=5,
            state="readonly"
        ).grid(row=1, column=3, padx=2)

        ttk.Button(
            phase_export_frame,
            text="Export",
            command=self.export_phase_figure
        ).grid(row=0, column=4, padx=10, rowspan=2)
        
        # Right side: Phase statistics
        stats_frame = ttk.LabelFrame(controls_stats_frame, text="Phase Statistics", padding=10)
        stats_frame.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))
        
        self.stats_text = tk.Text(stats_frame, height=6, width=35, state='disabled')
        self.stats_text.pack(fill=tk.BOTH, expand=True)
        
        # Plotting frame
        plot_frame = ttk.LabelFrame(self.phase_frame, text="Phase Classification Visualization", padding=5)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create matplotlib figure
        self.phase_fig = Figure(figsize=(12, 8))
        self.phase_ax = self.phase_fig.add_subplot(111)
        
        self.phase_canvas = FigureCanvasTkAgg(self.phase_fig, plot_frame)
        
        # Add navigation toolbar for zoom/pan functionality
        self.phase_toolbar = NavigationToolbar2Tk(self.phase_canvas, plot_frame)
        self.phase_toolbar.update()
        
        # Pack in correct order: toolbar at bottom, canvas fills remaining space
        self.phase_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.phase_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
    def create_capacity_tab(self):
        """Create Capacity vs Voltage tab (new functionality)"""
        
        # Top control frame
        control_frame = ttk.Frame(self.capacity_frame)
        control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        # Controls frame
        controls_frame = ttk.LabelFrame(control_frame, text="Capacity Analysis Controls", padding=10)
        controls_frame.pack(fill=tk.X)
        
        # Mass input
        mass_frame = ttk.Frame(controls_frame)
        mass_frame.grid(row=0, column=0, columnspan=4, sticky=tk.EW, pady=(0,10))
        
        ttk.Label(mass_frame, text="Sample Mass (mg):").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.mass_var = tk.StringVar(value="0")
        mass_entry = ttk.Entry(mass_frame, textvariable=self.mass_var, width=15)
        mass_entry.grid(row=0, column=1, padx=5, sticky=tk.W)
        ttk.Label(mass_frame, text="(0 = absolute capacity)", font=('Arial', 8), foreground='gray').grid(row=0, column=2, sticky=tk.W, padx=5)
        
        # Cycle selection (reuse multi-cycle logic)
        cycle_frame = ttk.Frame(controls_frame)
        cycle_frame.grid(row=1, column=0, columnspan=4, sticky=tk.EW, pady=(10,0))
        
        ttk.Label(cycle_frame, text="Cycles:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.capacity_cycle_var = tk.StringVar()
        capacity_cycle_entry = ttk.Entry(cycle_frame, textvariable=self.capacity_cycle_var, width=30)
        capacity_cycle_entry.grid(row=0, column=1, padx=5, sticky=tk.EW)
        self.capacity_cycle_var.set("1,2,3")  # Default example
        
        ttk.Button(cycle_frame, text="Plot Capacity vs Voltage", 
                  command=self.plot_capacity_vs_voltage).grid(row=0, column=2, padx=10)
        ttk.Button(cycle_frame, text="Plot All Cycles", 
                  command=self.plot_all_capacity_cycles).grid(row=0, column=3, padx=5)
        
        cycle_frame.columnconfigure(1, weight=1)
        
        # Help text
        help_label = ttk.Label(controls_frame, text="Format: '1,3,5' or '1-5' | Mass=0 for absolute capacity (mAh), Mass>0 for specific capacity (mAh/g)", 
                              font=('Arial', 8), foreground='gray')
        help_label.grid(row=2, column=0, columnspan=4, sticky=tk.W, padx=5, pady=(5,0))
        
        # Title toggle checkbox (shared with phase tab)
        ttk.Checkbutton(controls_frame, text="Show plot titles", 
                       variable=self.show_title_var,
                       command=self.refresh_titles).grid(row=3, column=0, columnspan=2, sticky=tk.W, padx=5, pady=(10,0))
        
        # Legend toggle checkbox (shared with phase tab)
        ttk.Checkbutton(controls_frame, text="Show legend/colorbar", 
                       variable=self.show_legend_var,
                       command=self.toggle_legend).grid(row=3, column=2, columnspan=2, sticky=tk.W, padx=5, pady=(10,0))
        
        # Combined frame for Axis Limits and Export (side by side)
        cap_combined_frame = ttk.Frame(controls_frame)
        cap_combined_frame.grid(row=4, column=0, columnspan=4, sticky=tk.EW, padx=5, pady=(10,0))
        
        # Left side: Axis limits controls for Capacity
        cap_limits_frame = ttk.LabelFrame(cap_combined_frame, text="Axis Limits", padding=5)
        cap_limits_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))
        
        # X-axis limits (Capacity)
        ttk.Label(cap_limits_frame, text="X-axis (Capacity):").grid(row=0, column=0, sticky=tk.W, padx=5)
        ttk.Label(cap_limits_frame, text="Min:").grid(row=0, column=1, sticky=tk.W, padx=(10,2))
        self.capacity_x_min_var = tk.StringVar()
        ttk.Entry(cap_limits_frame, textvariable=self.capacity_x_min_var, width=8).grid(row=0, column=2, padx=2)
        ttk.Label(cap_limits_frame, text="Max:").grid(row=0, column=3, sticky=tk.W, padx=(10,2))
        self.capacity_x_max_var = tk.StringVar()
        ttk.Entry(cap_limits_frame, textvariable=self.capacity_x_max_var, width=8).grid(row=0, column=4, padx=2)
        
        # Y-axis limits (Voltage)
        ttk.Label(cap_limits_frame, text="Y-axis (Voltage V):").grid(row=1, column=0, sticky=tk.W, padx=5)
        ttk.Label(cap_limits_frame, text="Min:").grid(row=1, column=1, sticky=tk.W, padx=(10,2))
        self.capacity_y_min_var = tk.StringVar()
        ttk.Entry(cap_limits_frame, textvariable=self.capacity_y_min_var, width=8).grid(row=1, column=2, padx=2)
        ttk.Label(cap_limits_frame, text="Max:").grid(row=1, column=3, sticky=tk.W, padx=(10,2))
        self.capacity_y_max_var = tk.StringVar()
        ttk.Entry(cap_limits_frame, textvariable=self.capacity_y_max_var, width=8).grid(row=1, column=4, padx=2)
        
        # Buttons
        ttk.Button(cap_limits_frame, text="Apply Limits", 
                  command=self.apply_capacity_limits).grid(row=0, column=5, padx=10, rowspan=2)
        ttk.Button(cap_limits_frame, text="Auto Scale", 
                  command=self.auto_scale_capacity).grid(row=0, column=6, padx=5, rowspan=2)

        # Right side: Export controls for Capacity
        capacity_export_frame = ttk.LabelFrame(cap_combined_frame, text="Export Capacity Plot", padding=5)
        capacity_export_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 0))

        ttk.Label(capacity_export_frame, text="Width (in):").grid(row=0, column=0, sticky=tk.W, padx=2)
        self.capacity_export_width_var = tk.DoubleVar(value=8.0)
        ttk.Entry(capacity_export_frame, textvariable=self.capacity_export_width_var, width=6).grid(row=0, column=1, padx=2)

        ttk.Label(capacity_export_frame, text="Height (in):").grid(row=1, column=0, sticky=tk.W, padx=2)
        self.capacity_export_height_var = tk.DoubleVar(value=6.0)
        ttk.Entry(capacity_export_frame, textvariable=self.capacity_export_height_var, width=6).grid(row=1, column=1, padx=2)

        ttk.Label(capacity_export_frame, text="DPI:").grid(row=0, column=2, sticky=tk.W, padx=(10,2))
        self.capacity_export_dpi_var = tk.IntVar(value=300)
        ttk.Entry(capacity_export_frame, textvariable=self.capacity_export_dpi_var, width=6).grid(row=0, column=3, padx=2)

        ttk.Label(capacity_export_frame, text="Format:").grid(row=1, column=2, sticky=tk.W, padx=(10,2))
        self.capacity_export_format_var = tk.StringVar(value="png")
        ttk.Combobox(
            capacity_export_frame,
            textvariable=self.capacity_export_format_var,
            values=["png", "pdf", "svg"],
            width=5,
            state="readonly"
        ).grid(row=1, column=3, padx=2)

        ttk.Button(
            capacity_export_frame,
            text="Export",
            command=self.export_capacity_figure
        ).grid(row=0, column=4, padx=10, rowspan=2)
        
        # Plotting frame
        plot_frame = ttk.LabelFrame(self.capacity_frame, text="Capacity vs Voltage Visualization", padding=5)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create matplotlib figure
        self.capacity_fig = Figure(figsize=(12, 8))
        self.capacity_ax = self.capacity_fig.add_subplot(111)
        
        self.capacity_canvas = FigureCanvasTkAgg(self.capacity_fig, plot_frame)
        
        # Add navigation toolbar
        self.capacity_toolbar = NavigationToolbar2Tk(self.capacity_canvas, plot_frame)
        self.capacity_toolbar.update()
        
        # Pack in correct order
        self.capacity_toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.capacity_canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
    
    def load_shared_data(self):
        """Load data references from the shared data dictionary"""
        if 'df_raw' in self.shared_data and self.shared_data['df_raw'] is not None:
            self.df_raw = self.shared_data['df_raw']
            self.cycle_list = self.shared_data.get('cycle_list', [])
            self.update_cycle_selector()
            
            # Check if all cycles are already classified (from Data Tab)
            if 'cycle_phase' in self.df_raw.columns:
                self.status_label.config(text=f"Data loaded, {len(self.cycle_list)} cycles pre-classified.")
            else:
                self.status_label.config(text=f"Data loaded, {len(self.cycle_list)} cycles ready for classification.")
        else:
            self.status_label.config(text="Ready - Load data in Data Tab first")

    def update_cycle_selector(self):
        """Update the cycle selector combobox with available cycles"""
        if self.cycle_list:
            cycle_options = [f'Cycle {c}' for c in self.cycle_list]
            self.cycle_combo['values'] = cycle_options
            if cycle_options:
                self.cycle_combo.current(0)  # Default to the first cycle
        else:
            self.cycle_combo['values'] = []
    
    def on_cycle_selected(self, event=None):
        """Handle cycle selection from combobox"""
        # Automatically plot the selected cycle
        self.classify_and_plot_single_cycle()
    
    def refresh_titles(self):
        """Refresh plot titles when the title toggle changes."""
        
        # Get current tab
        current_tab = self.notebook.select()
        current_tab_index = self.notebook.index(current_tab)
        
        if current_tab_index == 0:  # Phase Classification tab
            # Check if the plot is currently showing anything
            if not self.phase_ax.has_data() and not self.phase_ax.get_title():
                return
            
            # Determine plot type (single vs multi-cycle)
            has_twinx = any(isinstance(a, plt.Axes) and a.get_label() == 'secondary_y' for a in self.phase_fig.axes)
            
            if has_twinx:
                # Single-cycle plot
                saved_title = self._phase_single_title
            else:
                # Multi-cycle plot
                saved_title = self._phase_multi_title
                
            if self.show_title_var.get():
                # Show titles: Restore saved title
                if saved_title:
                    if not has_twinx:
                        self.phase_ax.set_title(saved_title, fontsize=12, fontweight='bold')
                    else:
                        self.phase_ax.set_title(saved_title)
            else:
                # Hide titles
                self.phase_ax.set_title('')
                
            self.phase_canvas.draw()
            
        elif current_tab_index == 1:  # Capacity vs Voltage tab
            # Check if plot exists
            if len(self.capacity_ax.lines) == 0:
                return
                
            if self.show_title_var.get():
                # Show title: Restore saved title
                if self._capacity_title:
                    self.capacity_ax.set_title(self._capacity_title, fontsize=12, fontweight='bold')
            else:
                # Hide title
                self.capacity_ax.set_title('')
                
            self.capacity_canvas.draw()
    
    def toggle_legend(self):
        """Toggle legend/colorbar visibility on existing plots"""
        # Get current tab
        current_tab = self.notebook.select()
        current_tab_index = self.notebook.index(current_tab)
        
        if current_tab_index == 0:  # Phase Classification tab
            # Handle legend
            legend = self.phase_ax.get_legend()
            if legend:
                legend.set_visible(self.show_legend_var.get())
            
            # Handle colorbar
            if self.phase_colorbar:
                if self.show_legend_var.get():
                    self.phase_colorbar.ax.set_visible(True)
                else:
                    self.phase_colorbar.ax.set_visible(False)
            
            self.phase_canvas.draw()
            
        elif current_tab_index == 1:  # Capacity tab
            # Handle legend
            legend = self.capacity_ax.get_legend()
            if legend:
                legend.set_visible(self.show_legend_var.get())
            
            # Handle colorbar
            if self.capacity_colorbar:
                if self.show_legend_var.get():
                    self.capacity_colorbar.ax.set_visible(True)
                else:
                    self.capacity_colorbar.ax.set_visible(False)
                    
            self.capacity_canvas.draw()
    
    # ===========================================================================================
    # PHASE CLASSIFICATION METHODS (EXISTING - UNCHANGED)
    # ===========================================================================================
    
    def classify_and_plot_single_cycle(self):
        """Plot single cycle using phase_classifier.py function"""
        if self.df_raw is None:
            messagebox.showwarning("No Data", "Please load data in Data Tab first")
            return
        
        # Get selected cycle
        selection = self.cycle_var.get()
        if not selection.startswith('Cycle '):
            messagebox.showwarning("No Cycle Selected", "Please select a specific cycle")
            return
        
        cycle_num = int(selection.split(' ')[1])
        
        try:
            self.status_label.config(text=f"Plotting cycle {cycle_num}...")
            self.parent.update()
            
            # Use the phase_classifier.py function with plot capture
            self.capture_phase_classifier_plot(lambda: phase_classifier.plot_single_cycle_classification(cycle_num, self.df_raw))
            
            # Get cycle data for statistics
            cycle_data = self.df_raw[self.df_raw['cycle'] == cycle_num].copy()
            
            # Ensure it has classification
            if 'cycle_phase' not in cycle_data.columns:
                cycle_data['cycle_phase'] = phase_classifier.classify_charge_discharge(cycle_data)
            
            self.classified_data = cycle_data
            self.current_cycle = cycle_num
            
            # Calculate and display statistics
            self.calculate_phase_statistics()
            
            self.status_label.config(text=f"Cycle {cycle_num} plotted successfully")
            
        except Exception as e:
            messagebox.showerror("Plot Error", f"Error plotting cycle {cycle_num}:\n{str(e)}")
            print(f"Single cycle plot error: {e}")
            import traceback
            traceback.print_exc()
    
    def classify_and_plot_multi_cycles(self):
        """Plot user-selected cycles DIRECTLY in GUI with smart colormap system"""
        if self.df_raw is None:
            messagebox.showwarning("No Data", "Please load data in Data Tab first")
            return
        
        # Parse cycle input
        cycle_input = self.multi_cycle_var.get().strip()
        if not cycle_input:
            messagebox.showwarning("No Cycles", "Please enter cycle numbers (e.g., '1,3,5' or '1-5')")
            return
        
        try:
            selected_cycles = self.parse_cycle_input(cycle_input)
            if not selected_cycles:
                messagebox.showwarning("Invalid Input", "Please enter valid cycle numbers")
                return
            
            self.status_label.config(text=f"Plotting {len(selected_cycles)} cycles...")
            self.parent.update()
            
            # PLOT DIRECTLY IN GUI (not using phase_classifier capture)
            self.plot_multi_cycle_direct(selected_cycles)
            
            # Update classified data for statistics
            self.classify_selected_cycles(selected_cycles)
            
            self.status_label.config(text=f"Multi-cycle plot completed for cycles: {selected_cycles}")
            
        except Exception as e:
            messagebox.showerror("Plot Error", f"Error plotting cycles:\n{str(e)}")
            print(f"Multi-cycle plot error: {e}")
            import traceback
            traceback.print_exc()
    
    def classify_and_plot_all_cycles(self):
        """Plot all available cycles"""
        if self.df_raw is None:
            messagebox.showwarning("No Data", "Please load data in Data Tab first")
            return
        
        if not self.cycle_list:
            messagebox.showwarning("No Cycles", "No cycles found in the loaded data.")
            return

        try:
            # Set multi-cycle entry to all cycles
            all_cycles_str = ','.join(map(str, self.cycle_list))
            self.multi_cycle_var.set(all_cycles_str)
            
            # Use multi-cycle plotting
            self.classify_and_plot_multi_cycles()
            
        except Exception as e:
            messagebox.showerror("Plot Error", f"Error plotting all cycles:\n{str(e)}")
            print(f"All cycles plot error: {e}")
    
    def plot_multi_cycle_direct(self, selected_cycles):
        """Plot multiple cycles DIRECTLY in GUI with smart colormap system (matching Tab 1)"""
        
        # Remove old colorbar if exists (with error handling)
        if self.phase_colorbar is not None:
            try:
                self.phase_colorbar.remove()
            except (KeyError, ValueError, AttributeError):
                # Colorbar already removed or invalid - ignore
                pass
            self.phase_colorbar = None
        
        # Clear and prepare plot
        self.phase_fig.clear()
        self.phase_ax = self.phase_fig.add_subplot(111)
        
        num_cycles = len(selected_cycles)
        total_points = 0
        
        # SMART COLORMAP SYSTEM (matching notebook exactly)
        if num_cycles <= 10:
            # Few cycles: sample colors from viridis colormap
            cmap = plt.colormaps['viridis']
            colors = cmap(np.linspace(0, 1, num_cycles))  # Sample from viridis
            use_colorbar = False
        else:
            # Many cycles: viridis with colorbar
            cmap = plt.colormaps['viridis']
            use_colorbar = True
        
        # Plot cycles with appropriate coloring
        for i, cycle_num in enumerate(selected_cycles):
            cycle_data = self.df_raw[self.df_raw['cycle'] == cycle_num].copy()
            
            if len(cycle_data) == 0:
                continue
            
            # Find cycle start (first non-zero current)
            first_nonzero_idx = cycle_data[cycle_data['I/mA'] != 0].index
            if len(first_nonzero_idx) > 0:
                cycle_start_time = cycle_data.loc[first_nonzero_idx[0], 't/s']
            else:
                cycle_start_time = cycle_data['t/s'].min()
            
            # Normalize time to start from cycle start AND convert to hours
            cycle_data['time_norm'] = (cycle_data['t/s'] - cycle_start_time) / 3600  # Convert to hours
            
            # Count points
            total_points += len(cycle_data)
            
            # Color calculation - FIXED: Use position within ALL available cycles (not selected cycles)
            if use_colorbar:
                # viridis: Use actual cycle number position in FULL dataset for consistent colors
                if len(self.cycle_list) > 1:
                    cycle_normalized = (cycle_num - min(self.cycle_list)) / (max(self.cycle_list) - min(self.cycle_list))
                else:
                    cycle_normalized = 0.0  # Single cycle case
                cycle_color = cmap(cycle_normalized)
                # No label when using colorbar
                self.phase_ax.plot(cycle_data['time_norm'], cycle_data['E/V'], '-o', 
                            color=cycle_color, linewidth=1, alpha=0.8, markersize=1)
            else:
                # viridis: Use position within ALL cycles for consistent coloring (not index in selected)
                if len(self.cycle_list) > 1:
                    cycle_normalized = (cycle_num - min(self.cycle_list)) / (max(self.cycle_list) - min(self.cycle_list))
                else:
                    cycle_normalized = 0.0  # Single cycle case
                cycle_color = cmap(cycle_normalized)  # Use normalized position, not colors[i]
                self.phase_ax.plot(cycle_data['time_norm'], cycle_data['E/V'], '-o', 
                            color=cycle_color, label=f'Cycle {cycle_num}',
                            linewidth=1, alpha=0.8, markersize=1)
        
        # --- TITLE LOGIC MODIFICATION: Save and apply title ---
        cycles_display = ', '.join(map(str, selected_cycles[:8]))
        if len(selected_cycles) > 8:
            cycles_display += f' ... (+{len(selected_cycles)-8} more)'
        
        # Save full title
        full_title = (f'Multi-Cycle Comparison - Complete Data ({len(selected_cycles)} Cycles)\n'
                      f'Cycles: {cycles_display} | Total Points: {total_points}')
        self._phase_multi_title = full_title # SAVE full title

        # Apply title based on the checkbox
        if self.show_title_var.get():
            self.phase_ax.set_title(full_title, # Use full title
                            fontsize=12, fontweight='bold')
        else:
            self.phase_ax.set_title('')
        # --- END TITLE LOGIC ---
        
        # Formatting
        self.phase_ax.set_xlabel('Time (h)', fontsize=12)
        self.phase_ax.set_ylabel('Voltage (V)', fontsize=12)
        self.phase_ax.grid(True, alpha=0.3)
        
        # LEGEND/COLORBAR LOGIC (matching Tab 1)
        if use_colorbar:
            # Many cycles: Use colorbar instead of legend
            from matplotlib.cm import ScalarMappable
            from matplotlib.colors import Normalize
            
            # Normalize cycle numbers - FIXED: Use FULL dataset range for consistent colors
            norm = Normalize(vmin=min(self.cycle_list), vmax=max(self.cycle_list))
            sm = ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            
            # Add colorbar and SAVE REFERENCE
            self.phase_colorbar = self.phase_fig.colorbar(sm, ax=self.phase_ax, pad=0.02, fraction=0.046)
            self.phase_colorbar.set_label('Cycle Number', rotation=270, labelpad=20, 
                                           fontsize=11, fontweight='bold')
            
            # Set explicit ticks (matching Tab 1 logic)
            min_cycle = min(selected_cycles)
            max_cycle = max(selected_cycles)
            
            if num_cycles <= 20:
                tick_positions = selected_cycles
            elif num_cycles <= 50:
                tick_positions = [c for c in selected_cycles if c % 5 == 0 or c == min_cycle or c == max_cycle]
            else:
                tick_positions = [c for c in selected_cycles if c % 10 == 0 or c == min_cycle or c == max_cycle]
            
            # Ensure min and max included
            if min_cycle not in tick_positions:
                tick_positions = [min_cycle] + tick_positions
            if max_cycle not in tick_positions:
                tick_positions = tick_positions + [max_cycle]
            
            self.phase_colorbar.set_ticks(sorted(set(tick_positions)))
            self.phase_colorbar.set_ticklabels([str(int(t)) for t in sorted(set(tick_positions))])
        else:
            # Few cycles: Use regular legend (matching notebook)
            if selected_cycles:  # Only show legend if we have cycles
                legend = self.phase_ax.legend(loc='best', fontsize=10)
                legend.set_draggable(True)  # Make legend draggable
                legend.set_zorder(100)
                legend.get_frame().set_facecolor('white')
                legend.get_frame().set_alpha(0.9)
                legend.get_frame().set_edgecolor('black')
        
        self.phase_fig.tight_layout()
        self.phase_canvas.draw()
    
    def parse_cycle_input(self, input_str):
        """Parse cycle input string (e.g., '1,3-5,7') into a list of cycle numbers"""
        cycle_set = set()
        parts = input_str.replace(" ", "").split(',')
        
        for part in parts:
            if '-' in part:
                try:
                    start, end = map(int, part.split('-'))
                    if start <= end:
                        cycle_set.update(range(start, end + 1))
                except ValueError:
                    continue  # Skip invalid range
            else:
                try:
                    cycle_set.add(int(part))
                except ValueError:
                    continue  # Skip invalid single number
        
        # Filter cycles to only include those available in the data
        available_cycles = set(self.cycle_list)
        valid_cycles = sorted([c for c in cycle_set if c in available_cycles])
        
        return valid_cycles
    
    def classify_selected_cycles(self, selected_cycles):
        """Classify only the selected cycles and update statistics"""
        
        # Filter data for selected cycles
        data_to_classify = self.df_raw[self.df_raw['cycle'].isin(selected_cycles)].copy()
        
        if 'cycle_phase' not in data_to_classify.columns:
            # Classify if not already done by Tab 1
            data_to_classify['cycle_phase'] = phase_classifier.classify_charge_discharge(data_to_classify)
            
        self.classified_data = data_to_classify
        self.calculate_phase_statistics()

    # ===========================================================================================
    # AXIS LIMIT CONTROL METHODS (NEW)
    # ===========================================================================================
    
    def apply_phase_limits(self):
        """Apply user-defined axis limits to phase classification plot"""
        if not hasattr(self, 'phase_ax') or self.phase_ax is None:
            messagebox.showwarning("No Plot", "Please create a plot first")
            return
        
        try:
            # Get limit values
            x_min = self.phase_x_min_var.get().strip()
            x_max = self.phase_x_max_var.get().strip()
            y_min = self.phase_y_min_var.get().strip()
            y_max = self.phase_y_max_var.get().strip()
            
            # Apply X limits if provided
            if x_min or x_max:
                current_xlim = self.phase_ax.get_xlim()
                new_x_min = float(x_min) if x_min else current_xlim[0]
                new_x_max = float(x_max) if x_max else current_xlim[1]
                self.phase_ax.set_xlim(new_x_min, new_x_max)
            
            # Apply Y limits if provided
            if y_min or y_max:
                current_ylim = self.phase_ax.get_ylim()
                new_y_min = float(y_min) if y_min else current_ylim[0]
                new_y_max = float(y_max) if y_max else current_ylim[1]
                self.phase_ax.set_ylim(new_y_min, new_y_max)
            
            self.phase_canvas.draw()
            self.update_status("Phase axis limits applied")
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid numbers for axis limits.\nError: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Error applying axis limits: {str(e)}")
    
    def auto_scale_phase(self):
        """Auto-scale phase classification plot and clear limit inputs"""
        if not hasattr(self, 'phase_ax') or self.phase_ax is None:
            messagebox.showwarning("No Plot", "Please create a plot first")
            return
        
        try:
            self.phase_ax.autoscale()
            self.phase_canvas.draw()
            
            # Clear the input fields
            self.phase_x_min_var.set("")
            self.phase_x_max_var.set("")
            self.phase_y_min_var.set("")
            self.phase_y_max_var.set("")
            
            self.update_status("Phase plot auto-scaled")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error auto-scaling: {str(e)}")
    
    def apply_capacity_limits(self):
        """Apply user-defined axis limits to capacity plot"""
        if not hasattr(self, 'capacity_ax') or self.capacity_ax is None:
            messagebox.showwarning("No Plot", "Please create a plot first")
            return
        
        try:
            # Get limit values
            x_min = self.capacity_x_min_var.get().strip()
            x_max = self.capacity_x_max_var.get().strip()
            y_min = self.capacity_y_min_var.get().strip()
            y_max = self.capacity_y_max_var.get().strip()
            
            # Apply X limits if provided
            if x_min or x_max:
                current_xlim = self.capacity_ax.get_xlim()
                new_x_min = float(x_min) if x_min else current_xlim[0]
                new_x_max = float(x_max) if x_max else current_xlim[1]
                self.capacity_ax.set_xlim(new_x_min, new_x_max)
            
            # Apply Y limits if provided
            if y_min or y_max:
                current_ylim = self.capacity_ax.get_ylim()
                new_y_min = float(y_min) if y_min else current_ylim[0]
                new_y_max = float(y_max) if y_max else current_ylim[1]
                self.capacity_ax.set_ylim(new_y_min, new_y_max)
            
            self.capacity_canvas.draw()
            self.update_status("Capacity axis limits applied")
            
        except ValueError as e:
            messagebox.showerror("Invalid Input", f"Please enter valid numbers for axis limits.\nError: {str(e)}")
        except Exception as e:
            messagebox.showerror("Error", f"Error applying axis limits: {str(e)}")
    
    def auto_scale_capacity(self):
        """Auto-scale capacity plot and clear limit inputs"""
        if not hasattr(self, 'capacity_ax') or self.capacity_ax is None:
            messagebox.showwarning("No Plot", "Please create a plot first")
            return
        
        try:
            self.capacity_ax.autoscale()
            self.capacity_canvas.draw()
            
            # Clear the input fields
            self.capacity_x_min_var.set("")
            self.capacity_x_max_var.set("")
            self.capacity_y_min_var.set("")
            self.capacity_y_max_var.set("")
            
            self.update_status("Capacity plot auto-scaled")
            
        except Exception as e:
            messagebox.showerror("Error", f"Error auto-scaling: {str(e)}")

    def update_status(self, message):
        """Update status label"""
        self.status_label.config(text=message)

    # ===========================================================================================
    # EXPORT METHODS (NEW)
    # ===========================================================================================

    def export_phase_figure(self):
        """Export phase classification plot"""
        if not hasattr(self, 'phase_fig') or self.phase_fig is None:
            messagebox.showwarning("No figure", "No phase plot to export")
            return

        fmt = self.phase_export_format_var.get()
        filepath = filedialog.asksaveasfilename(
            title="Export Phase Classification Plot",
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")]
        )

        if not filepath:
            return

        try:
            export_figure(
                self.phase_fig,
                filepath,
                width_in=self.phase_export_width_var.get(),
                height_in=self.phase_export_height_var.get(),
                dpi=self.phase_export_dpi_var.get()
            )
            messagebox.showinfo("Export", f"Phase plot exported:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def export_capacity_figure(self):
        """Export capacity vs voltage plot"""
        if not hasattr(self, 'capacity_fig') or self.capacity_fig is None:
            messagebox.showwarning("No figure", "No capacity plot to export")
            return

        fmt = self.capacity_export_format_var.get()
        filepath = filedialog.asksaveasfilename(
            title="Export Capacity vs Voltage Plot",
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}")]
        )

        if not filepath:
            return

        try:
            export_figure(
                self.capacity_fig,
                filepath,
                width_in=self.capacity_export_width_var.get(),
                height_in=self.capacity_export_height_var.get(),
                dpi=self.capacity_export_dpi_var.get()
            )
            messagebox.showinfo("Export", f"Capacity plot exported:\n{filepath}")

        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    # ===========================================================================================
    # PHASE STATISTICS (EXISTING)
    # ===========================================================================================

    def capture_phase_classifier_plot(self, plot_function):
        """Capture the plot from phase_classifier.py functions and display in GUI"""
        original_backend = plt.get_backend()
        plt.switch_backend('Agg')
        
        original_show = plt.show
        
        def capture_plot():
            current_fig = plt.gcf()
            
            self.phase_fig.clear()
            # Add main subplot
            self.phase_ax = self.phase_fig.add_subplot(111)
            
            if len(current_fig.axes) >= 1:
                source_ax = current_fig.axes[0]
                
                # Copy plot elements (lines, scatter, patches, etc.) with x-axis conversion to hours
                for line in source_ax.get_lines():
                    # Convert x-data from seconds to hours (handle both lists and arrays)
                    x_data = np.array(line.get_xdata())  # Convert to numpy array first
                    x_data_hours = x_data / 3600  # Convert seconds to hours
                    self.phase_ax.plot(x_data_hours, line.get_ydata(), 
                                color=line.get_color(), label=line.get_label(),
                                linewidth=line.get_linewidth(), alpha=line.get_alpha(),
                                marker=line.get_marker(), markersize=line.get_markersize())
                
                for collection in source_ax.collections:
                    if hasattr(collection, 'get_offsets') and len(collection.get_offsets()) > 0:
                        offsets = collection.get_offsets()
                        colors = collection.get_facecolors()
                        sizes = collection.get_sizes()
                        # Convert x-coordinates (offsets[:, 0]) from seconds to hours
                        offsets_hours = offsets.copy()
                        offsets_hours[:, 0] = offsets[:, 0] / 3600  # Convert seconds to hours
                        self.phase_ax.scatter(offsets_hours[:, 0], offsets_hours[:, 1], 
                                       c=colors, s=sizes, alpha=collection.get_alpha())
                
                for patch in source_ax.patches:
                    if hasattr(patch, 'get_x') and hasattr(patch, 'get_width'):
                        x = patch.get_x() / 3600  # Convert x position from seconds to hours
                        width = patch.get_width() / 3600  # Convert width from seconds to hours
                        self.phase_ax.axvspan(x, x + width, color=patch.get_facecolor(), 
                                       alpha=patch.get_alpha())
                
                # --- TITLE LOGIC MODIFICATION: Save and apply title ---
                # 1. Capture the title generated by the external function
                full_title = source_ax.get_title()
                self._phase_single_title = full_title # SAVE full title
                
                # 2. Apply title based on the checkbox
                if self.show_title_var.get():
                    self.phase_ax.set_title(full_title) # Use full title
                else:
                    self.phase_ax.set_title('')  # Empty title
                # --- END TITLE LOGIC ---
                
                # Copy formatting with hours conversion
                self.phase_ax.set_xlabel('Time (h)', fontsize=12)  # Force hours label
                self.phase_ax.set_ylabel(source_ax.get_ylabel())
                self.phase_ax.grid(True, alpha=0.3)
                # Convert x-axis limits from seconds to hours (handle potential list/array issues)
                xlim_seconds = source_ax.get_xlim()
                xlim_hours = (float(xlim_seconds[0]) / 3600, float(xlim_seconds[1]) / 3600)
                self.phase_ax.set_xlim(xlim_hours)
                self.phase_ax.set_ylim(source_ax.get_ylim())
                
                handles_combined = []
                labels_combined = []
                
                # Get legend from main axis
                if source_ax.get_legend():
                    handles1, labels1 = source_ax.get_legend_handles_labels()
                    handles_combined.extend(handles1)
                    labels_combined.extend(labels1)
                
                # Handle dual y-axis (if exists)
                if len(current_fig.axes) >= 2:
                    source_ax2 = current_fig.axes[1]
                    # Create the secondary axis on the new plot
                    ax2 = self.phase_ax.twinx() 
                    ax2.set_label('secondary_y') # Label for refresh_titles heuristic
                    
                    for line in source_ax2.get_lines():
                        # Convert x-data from seconds to hours for secondary axis too (handle both lists and arrays)
                        x_data = np.array(line.get_xdata())  # Convert to numpy array first
                        x_data_hours = x_data / 3600  # Convert seconds to hours
                        ax2.plot(x_data_hours, line.get_ydata(), 
                                color=line.get_color(), label=line.get_label(),
                                linewidth=line.get_linewidth(), alpha=line.get_alpha(),
                                linestyle=line.get_linestyle(), marker=line.get_marker(),
                                markersize=line.get_markersize())
                    
                    ax2.set_ylabel(source_ax2.get_ylabel(), color='orange')
                    ax2.tick_params(axis='y', labelcolor='orange')
                    ax2.set_ylim(source_ax2.get_ylim())
                    
                    # Get legend from secondary axis
                    if source_ax2.get_legend():
                        handles2, labels2 = source_ax2.get_legend_handles_labels()
                        handles_combined.extend(handles2)
                        labels_combined.extend(labels2)
                
                # Create single combined legend on main axis
                if handles_combined:
                    legend = self.phase_ax.legend(handles_combined, labels_combined, loc='best')
                    legend.set_draggable(True)  # Make the combined legend draggable!
                    legend.set_zorder(100)  # Bring legend to front
                    legend.get_frame().set_facecolor('white')
                    legend.get_frame().set_alpha(0.9)  # Semi-transparent background
                    legend.get_frame().set_edgecolor('black')
                elif source_ax.get_legend():
                    legend1 = self.phase_ax.legend(loc='lower left')
                    legend1.set_draggable(True)  # Make legend draggable!
                    legend1.set_zorder(100)  # Bring legend to front
                    legend1.get_frame().set_facecolor('white')
                    legend1.get_frame().set_alpha(0.9)  # Semi-transparent background
                    legend1.get_frame().set_edgecolor('black')
            
            plt.clf()
            self.phase_fig.tight_layout()
            self.phase_canvas.draw()
        
        plt.show = capture_plot
        
        try:
            plot_function()
        finally:
            plt.show = original_show
            plt.switch_backend(original_backend)
    
    def calculate_phase_statistics(self):
        """Calculate and display phase statistics"""
        if self.classified_data is None:
            return
        
        phase_counts = self.classified_data['cycle_phase'].value_counts()
        total_points = len(self.classified_data)
        
        stats_info = []
        stats_info.append("Phase Classification Statistics:")
        stats_info.append("")
        
        for phase in ['charge', 'discharge', 'rest']:
            count = phase_counts.get(phase, 0)
            percentage = (count / total_points * 100) if total_points > 0 else 0
            stats_info.append(f"{phase.title()}: {count:,} points ({percentage:.1f}%)")
        
        self.stats_text.config(state='normal')
        self.stats_text.delete(1.0, tk.END)
        self.stats_text.insert(1.0, '\n'.join(stats_info))
        self.stats_text.config(state='disabled')
    
    # ===========================================================================================
    # CAPACITY ANALYSIS METHODS (NEW)
    # ===========================================================================================
    
    def calculate_capacity(self, data, mass_mg):
        """Calculate capacity from current integration with reset at each phase change"""
        data = data.copy()
        
        # Ensure we have phase classification
        if 'cycle_phase' not in data.columns:
            data['cycle_phase'] = phase_classifier.classify_charge_discharge(data)
        
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
        
        # Calculate specific capacity if mass provided
        if mass_mg > 0:
            data['specific_capacity'] = data['capacity_mAh'] / (mass_mg / 1000)
        else:
            data['specific_capacity'] = 0.0 # Avoid undefined state
        
        return data
    
    def plot_capacity_vs_voltage(self):
        """Plot capacity vs voltage for selected cycles"""
        if self.df_raw is None:
            messagebox.showwarning("No Data", "Please load data in Data Tab first")
            return
        
        # Parse cycle input
        cycle_input = self.capacity_cycle_var.get().strip()
        if not cycle_input:
            messagebox.showwarning("No Cycles", "Please enter cycle numbers (e.g., '1,3,5' or '1-5')")
            return
        
        try:
            selected_cycles = self.parse_cycle_input(cycle_input)
            if not selected_cycles:
                messagebox.showwarning("Invalid Input", "Please enter valid cycle numbers")
                return
            
            # Get mass
            try:
                mass_mg = float(self.mass_var.get())
            except ValueError:
                mass_mg = 0.0
            
            self.status_label.config(text=f"Plotting capacity vs voltage for {len(selected_cycles)} cycles...")
            self.parent.update()
            
            self.plot_capacity_direct(selected_cycles, mass_mg)
            
            capacity_type = "specific" if mass_mg > 0 else "absolute"
            self.status_label.config(text=f"Capacity plot completed: {len(selected_cycles)} cycles ({capacity_type} capacity)")
            
        except Exception as e:
            messagebox.showerror("Plot Error", f"Error plotting capacity:\n{str(e)}")
            print(f"Capacity plot error: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_all_capacity_cycles(self):
        """Plot capacity vs voltage for all available cycles"""
        if self.df_raw is None:
            messagebox.showwarning("No Data", "Please load data in Data Tab first")
            return
        
        if not self.cycle_list:
            messagebox.showwarning("No Cycles", "No cycles found in the loaded data.")
            return

        try:
            # Set capacity cycle entry to all cycles
            all_cycles_str = ','.join(map(str, self.cycle_list))
            self.capacity_cycle_var.set(all_cycles_str)
            
            # Use capacity plotting
            self.plot_capacity_vs_voltage()
            
        except Exception as e:
            messagebox.showerror("Plot Error", f"Error plotting all capacity cycles:\n{str(e)}")
            print(f"All capacity cycles plot error: {e}")
    
    def plot_capacity_direct(self, selected_cycles, mass_mg):
        """Plot capacity vs voltage with SAME color/legend logic as phase classification"""
        
        # Remove old colorbar if exists (with error handling)
        if self.capacity_colorbar is not None:
            try:
                self.capacity_colorbar.remove()
            except (KeyError, ValueError, AttributeError):
                # Colorbar already removed or invalid - ignore
                pass
            self.capacity_colorbar = None
        
        # Clear and prepare plot
        self.capacity_fig.clear()
        self.capacity_ax = self.capacity_fig.add_subplot(111)
        
        num_cycles = len(selected_cycles)
        
        # Calculate capacity for selected data
        selected_data = self.df_raw[self.df_raw['cycle'].isin(selected_cycles)].copy()
        if len(selected_data) == 0:
            messagebox.showerror("No Data", "No data found for selected cycles")
            return
            
        # Add capacity calculation
        capacity_data = self.calculate_capacity(selected_data, mass_mg)
        
        # Ensure phase classification exists
        if 'cycle_phase' not in capacity_data.columns:
            capacity_data['cycle_phase'] = phase_classifier.classify_charge_discharge(capacity_data)
        
        # SMART COLORMAP SYSTEM (matching notebook exactly)
        if num_cycles <= 10:
            # Few cycles: sample colors from viridis colormap
            cmap = plt.colormaps['viridis']
            colors = cmap(np.linspace(0, 1, num_cycles))  # Sample from viridis
            use_colorbar = False
        else:
            # Many cycles: viridis with colorbar
            cmap = plt.colormaps['viridis']
            use_colorbar = True
        
        # Plot cycles with appropriate coloring
        for i, cycle_num in enumerate(selected_cycles):
            cycle_data = capacity_data[capacity_data['cycle'] == cycle_num].copy()
            
            if len(cycle_data) == 0:
                continue
            
            # Separate charge and discharge data
            charge_data = cycle_data[cycle_data['cycle_phase'] == 'charge']
            discharge_data = cycle_data[cycle_data['cycle_phase'] == 'discharge']
            
            # Color calculation - FIXED: Use position within ALL available cycles (not selected cycles)
            if use_colorbar:
                # viridis: Use actual cycle number position in FULL dataset for consistent colors
                if len(self.cycle_list) > 1:
                    cycle_normalized = (cycle_num - min(self.cycle_list)) / (max(self.cycle_list) - min(self.cycle_list))
                else:
                    cycle_normalized = 0.0  # Single cycle case
                cycle_color = cmap(cycle_normalized)
                label = None  # No label when using colorbar
            else:
                # viridis: Use position within ALL cycles for consistent coloring (not index in selected)
                if len(self.cycle_list) > 1:
                    cycle_normalized = (cycle_num - min(self.cycle_list)) / (max(self.cycle_list) - min(self.cycle_list))
                else:
                    cycle_normalized = 0.0  # Single cycle case
                cycle_color = cmap(cycle_normalized)  # Use normalized position, not colors[i]
                label = f'Cycle {cycle_num}'
            
            # Determine x-axis data (capacity type)
            if mass_mg > 0:
                x_col = 'specific_capacity'
            else:
                x_col = 'capacity_mAh'
            
            # Plot charge and discharge (matching notebook logic)
            if not charge_data.empty:
                self.capacity_ax.plot(charge_data[x_col], charge_data['E/V'], '-o',
                              color=cycle_color, label=label,
                              linewidth=1, alpha=0.8, markersize=1)
            
            if not discharge_data.empty:
                self.capacity_ax.plot(discharge_data[x_col], discharge_data['E/V'], '-o',
                              color=cycle_color,  # No label for discharge (matches notebook)
                              linewidth=1, alpha=0.8, markersize=1)
        
        # Title logic
        cycles_display = ', '.join(map(str, selected_cycles[:8]))
        if len(selected_cycles) > 8:
            cycles_display += f' ... (+{len(selected_cycles)-8} more)'
        
        # Capacity type for title
        if mass_mg > 0:
            capacity_type = f"Specific Capacity (mass = {mass_mg:.1f} mg)"
            xlabel = 'Specific Capacity (mAh/g)'
        else:
            capacity_type = "Absolute Capacity"
            xlabel = 'Capacity (mAh)'
        
        # Save and apply title
        full_title = (f'Capacity vs Voltage - {capacity_type} ({len(selected_cycles)} Cycles)\n'
                      f'Cycles: {cycles_display}')
        self._capacity_title = full_title
        
        if self.show_title_var.get():
            self.capacity_ax.set_title(full_title, fontsize=12, fontweight='bold')
        else:
            self.capacity_ax.set_title('')
        
        # Formatting
        self.capacity_ax.set_xlabel(xlabel, fontsize=12)
        self.capacity_ax.set_ylabel('Voltage (V)', fontsize=12)
        self.capacity_ax.grid(True, alpha=0.3)
        
        # LEGEND/COLORBAR LOGIC (matching phase classification)
        if use_colorbar:
            # Many cycles: Use colorbar instead of legend
            from matplotlib.cm import ScalarMappable
            from matplotlib.colors import Normalize
            
            # Normalize cycle numbers - FIXED: Use FULL dataset range for consistent colors
            norm = Normalize(vmin=min(self.cycle_list), vmax=max(self.cycle_list))
            sm = ScalarMappable(cmap=cmap, norm=norm)
            sm.set_array([])
            
            # Add colorbar and SAVE REFERENCE
            self.capacity_colorbar = self.capacity_fig.colorbar(sm, ax=self.capacity_ax, pad=0.02, fraction=0.046)
            self.capacity_colorbar.set_label('Cycle Number', rotation=270, labelpad=20, 
                                           fontsize=11, fontweight='bold')
            
            # Set explicit ticks
            min_cycle = min(selected_cycles)
            max_cycle = max(selected_cycles)
            
            if num_cycles <= 20:
                tick_positions = selected_cycles
            elif num_cycles <= 50:
                tick_positions = [c for c in selected_cycles if c % 5 == 0 or c == min_cycle or c == max_cycle]
            else:
                tick_positions = [c for c in selected_cycles if c % 10 == 0 or c == min_cycle or c == max_cycle]
            
            # Ensure min and max included
            if min_cycle not in tick_positions:
                tick_positions = [min_cycle] + tick_positions
            if max_cycle not in tick_positions:
                tick_positions = tick_positions + [max_cycle]
            
            self.capacity_colorbar.set_ticks(sorted(set(tick_positions)))
            self.capacity_colorbar.set_ticklabels([str(int(t)) for t in sorted(set(tick_positions))])
        else:
            # Few cycles: Use regular legend
            legend = self.capacity_ax.legend(loc='best')
            legend.set_draggable(True)  # Make legend draggable
            legend.set_zorder(100)
            legend.get_frame().set_facecolor('white')
            legend.get_frame().set_alpha(0.9)
            legend.get_frame().set_edgecolor('black')
        
        self.capacity_fig.tight_layout()
        self.capacity_canvas.draw()
    
    def get_classification_data(self):
        """Return classification data for other tabs to use"""
        return {
            'classified_data': self.classified_data,
            'current_cycle': self.current_cycle,
            'phase_stats': self.phase_stats
        }