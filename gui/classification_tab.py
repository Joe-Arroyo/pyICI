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
import os

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

        # Data behind the last-drawn Capacity vs Voltage plot, for "Export Data"
        self._last_capacity_export_df = None

        # Per-file capacity panel data: {fname: {'cycles_var': StringVar, 'mass_var': StringVar}}
        self.cap_file_vars = {}
        
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

        # Centre: Loaded Files selector
        files_panel = ttk.LabelFrame(controls_stats_frame, text="Loaded Files", padding=5)
        files_panel.pack(side=tk.LEFT, fill=tk.BOTH, padx=(5, 0))

        self.files_listbox = tk.Listbox(files_panel, height=4, width=35,
                                        selectmode=tk.SINGLE, exportselection=False)
        files_scroll = ttk.Scrollbar(files_panel, orient=tk.VERTICAL,
                                    command=self.files_listbox.yview)
        self.files_listbox.configure(yscrollcommand=files_scroll.set)
        self.files_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        files_scroll.pack(side=tk.LEFT, fill=tk.Y)

        self.files_listbox.bind('<<ListboxSelect>>', self._on_files_listbox_select)
        
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
        
        # Side-by-side layout: controls left, loaded files right
        cap_top_frame = ttk.Frame(control_frame)
        cap_top_frame.pack(fill=tk.X)

        # Controls frame (left)
        controls_frame = ttk.LabelFrame(cap_top_frame, text="Capacity Analysis Controls", padding=10)
        controls_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 5))

        # Loaded Files panel (right)
        cap_files_panel = ttk.LabelFrame(cap_top_frame, text="Loaded Files", padding=5)
        cap_files_panel.pack(side=tk.RIGHT, fill=tk.BOTH, padx=(5, 0))

        # Column headers
        headers_frame = ttk.Frame(cap_files_panel)
        headers_frame.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(headers_frame, text="File", font=('Arial', 8), foreground='gray').pack(side=tk.LEFT, padx=(18, 0))
        ttk.Label(headers_frame, text="Cycles", font=('Arial', 8), foreground='gray').pack(side=tk.RIGHT, padx=(0, 62))
        ttk.Label(headers_frame, text="Mass (mg)", font=('Arial', 8), foreground='gray').pack(side=tk.RIGHT, padx=(0, 4))

        # Scrollable rows frame
        cap_rows_canvas = tk.Canvas(cap_files_panel, height=80, highlightthickness=0)
        cap_rows_scroll = ttk.Scrollbar(cap_files_panel, orient=tk.VERTICAL,
                                         command=cap_rows_canvas.yview)
        cap_rows_canvas.configure(yscrollcommand=cap_rows_scroll.set)
        cap_rows_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cap_rows_scroll.pack(side=tk.LEFT, fill=tk.Y)

        self.cap_rows_inner = ttk.Frame(cap_rows_canvas)
        self.cap_rows_window = cap_rows_canvas.create_window((0, 0), window=self.cap_rows_inner, anchor='nw')

        def _on_cap_rows_configure(event):
            cap_rows_canvas.configure(scrollregion=cap_rows_canvas.bbox('all'))
            cap_rows_canvas.itemconfig(self.cap_rows_window, width=cap_rows_canvas.winfo_width())

        self.cap_rows_inner.bind('<Configure>', _on_cap_rows_configure)
        cap_rows_canvas.bind('<Configure>', lambda e: cap_rows_canvas.itemconfig(
            self.cap_rows_window, width=e.width))

        # Overlay checkbox
        self.cap_overlay_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(cap_files_panel, text="Overlay all files",
                        variable=self.cap_overlay_var,
                        command=self._on_cap_overlay_toggled).pack(anchor=tk.W, pady=(6, 0))
        
        # Mass is set per file in the "Loaded Files" panel (right side) — no
        # shared/global mass field here, since a single field can't tell
        # files apart and silently carries over the wrong mass when the
        # active file is switched.
        mass_frame = ttk.Frame(controls_frame)
        mass_frame.grid(row=0, column=0, columnspan=4, sticky=tk.EW, pady=(0,10))
        ttk.Label(mass_frame, text="Sample mass is set per file in the ‘Loaded Files’ panel →",
                  font=('Arial', 9), foreground='gray').pack(side=tk.LEFT, padx=5)

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

        ttk.Button(
            capacity_export_frame,
            text="Export Data",
            command=self.export_capacity_data
        ).grid(row=2, column=0, columnspan=5, padx=10, pady=(4, 0), sticky=tk.EW)
        
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

        self.notebook.bind('<<NotebookTabChanged>>', self._on_tab_changed)

    def _get_cycle_shade(self, base_color, cycle_index, total_cycles):
        """Return a shade of base_color: light for early cycles, dark for later ones."""
        import matplotlib.colors as mcolors
        rgb = mcolors.to_rgb(base_color)
        t = cycle_index / max(total_cycles - 1, 1)  # 0.0 → 1.0
        if t < 0.5:
            blend = 1 - t * 2        # 1.0 → 0.0: blend towards white
            return tuple(c + (1 - c) * blend * 0.6 for c in rgb)
        else:
            blend = (t - 0.5) * 2   # 0.0 → 1.0: blend towards black
            return tuple(c * (1 - blend * 0.4) for c in rgb)

    def _get_overlay_color(self, file_index):
        """Return a colour for file_index, with shading for >10 files."""
        import matplotlib.colors as mcolors
        colors = self.shared_data.get('overlay_colors', ['#1f77b4'])
        n = len(colors)
        base_color = colors[file_index % n]
        round_num = file_index // n   # 0 = normal, 1 = light, 2 = dark
        if round_num == 0:
            return base_color
        elif round_num == 1:
            rgb = mcolors.to_rgb(base_color)
            return tuple(c + (1 - c) * 0.5 for c in rgb)  # lighten
        else:
            rgb = mcolors.to_rgb(base_color)
            return tuple(c * 0.5 for c in rgb)             # darken

    def _on_tab_changed(self, event=None):
        """Refresh file lists when switching subtabs, and force whichever
        subtab's plot canvas just became visible to resize its figure to
        the widget's real, fully laid-out pixel size. A canvas that was
        hidden when its tab was built can be handed a stale/undersized
        widget geometry (Tk hasn't allocated it real screen space yet),
        which bakes in a smaller figure - and correspondingly smaller-
        looking fonts - until something forces a resize."""
        if hasattr(self, '_files_listbox'):
            self._refresh_files_listbox()
        if hasattr(self, 'cap_rows_inner'):
            self._refresh_cap_files_listbox()

        self.parent.update_idletasks()
        try:
            current = self.notebook.nametowidget(self.notebook.select())
        except Exception:
            return
        for frame, canvas in ((self.phase_frame, getattr(self, 'phase_canvas', None)),
                              (self.capacity_frame, getattr(self, 'capacity_canvas', None))):
            if canvas is None or frame is not current:
                continue
            tkcanvas = canvas._tkcanvas
            tkcanvas.event_generate('<Configure>',
                                     width=tkcanvas.winfo_width(),
                                     height=tkcanvas.winfo_height())

    def _refresh_cap_files_listbox(self):
        """Rebuild the capacity tab per-file rows panel."""
        loaded = self.shared_data.get('loaded_files', {})
        active = self.shared_data.get('active_file', None)
        colors = self.shared_data.get('overlay_colors', [])
        n_colors = len(colors)

        # Destroy existing rows
        for widget in self.cap_rows_inner.winfo_children():
            widget.destroy()

        # Keep existing StringVars to preserve user edits
        existing_vars = self.cap_file_vars.copy()
        self.cap_file_vars = {}

        # Header row
        ttk.Label(self.cap_rows_inner, text='File', foreground='gray').grid(
            row=0, column=1, columnspan=2, sticky=tk.W, padx=2, pady=(0, 2))
        ttk.Label(self.cap_rows_inner, text='Cycles', foreground='gray').grid(
            row=0, column=3, sticky=tk.W, padx=2, pady=(0, 2))
        ttk.Label(self.cap_rows_inner, text='Mass (mg)', foreground='gray').grid(
            row=0, column=4, sticky=tk.W, padx=2, pady=(0, 2))

        for i, (fname, rec) in enumerate(loaded.items()):
            row_num = i + 1
            color = colors[i % n_colors] if n_colors else '#1f77b4'
            short = os.path.basename(fname)
            is_active = (fname == active)

            # Colour dot
            dot = tk.Canvas(self.cap_rows_inner, width=10, height=10, highlightthickness=0)
            dot.grid(row=row_num, column=0, padx=(4, 2), pady=2)
            dot.create_oval(1, 1, 9, 9, fill=color, outline=color)

            # Filename label
            lbl_text = f"► {short}" if is_active else f"   {short}"
            lbl = ttk.Label(self.cap_rows_inner, text=lbl_text, width=22,
                            foreground='darkblue' if is_active else '',
                            font=('TkDefaultFont', 9, 'bold' if is_active else 'normal'))
            lbl.grid(row=row_num, column=1, columnspan=2, sticky=tk.W, padx=2, pady=2)
            lbl.bind('<Button-1>', lambda e, f=fname: self._set_cap_active_file(f))

            # Restore or create StringVars
            if fname in existing_vars:
                cycles_var = existing_vars[fname]['cycles_var']
                mass_var   = existing_vars[fname]['mass_var']
            else:
                default_cycles = ','.join(map(str, rec['cycle_list']))
                cycles_var = tk.StringVar(value=default_cycles)
                mass_var   = tk.StringVar(value='0')

            self.cap_file_vars[fname] = {'cycles_var': cycles_var, 'mass_var': mass_var}

            # Cycles entry
            ttk.Entry(self.cap_rows_inner, textvariable=cycles_var, width=10).grid(
                row=row_num, column=3, padx=2, pady=2, sticky=tk.W)

            # Mass entry
            ttk.Entry(self.cap_rows_inner, textvariable=mass_var, width=7).grid(
                row=row_num, column=4, padx=2, pady=2, sticky=tk.W)

        self.cap_rows_inner.columnconfigure(2, weight=1)

    def _save_outgoing_regression_params(self, new_fname):
        """Snapshot the currently-active file's regression_params into
        all_regression_params before switching away from it. Without this,
        switching active file via this panel (rather than Data Tab) silently
        drops whatever regression work was done on the outgoing file."""
        old_fname = self.shared_data.get('active_file')
        if old_fname and old_fname != new_fname:
            self.shared_data.setdefault('all_regression_params', {})[old_fname] = \
                self.shared_data.get('regression_params', {}).copy()

    def _set_cap_active_file(self, fname):
        """Set active file from capacity panel click."""
        loaded = self.shared_data.get('loaded_files', {})
        if fname not in loaded:
            return
        rec = loaded[fname]
        self._save_outgoing_regression_params(fname)
        self.shared_data['active_file'] = fname
        self.shared_data['df_raw']      = rec['df_raw']
        self.shared_data['cycle_list']  = rec['cycle_list']
        self.shared_data['filename']    = rec['filename']
        all_params = self.shared_data.get('all_regression_params', {})
        self.shared_data['regression_params'] = all_params.get(fname, {})
        self.df_raw     = rec['df_raw']
        self.cycle_list = rec['cycle_list']
        self._refresh_cap_files_listbox()
        self._refresh_files_listbox()
        self.status_label.config(
            text=f"Active: {os.path.basename(fname)}  |  {len(self.cycle_list)} cycles")
    
    def _refresh_files_listbox(self):
        """Rebuild the files listbox from shared_data['loaded_files']."""
        loaded = self.shared_data.get('loaded_files', {})
        active = self.shared_data.get('active_file', None)
        self.files_listbox.delete(0, tk.END)
        self._listbox_filenames = list(loaded.keys())
        for i, fname in enumerate(self._listbox_filenames):
            import os
            short = os.path.basename(fname)
            display = f"► {short}" if fname == active else f"   {short}"
            self.files_listbox.insert(tk.END, display)
            if fname == active:
                self.files_listbox.itemconfig(i, bg='#d0eaff')

    def _on_files_listbox_select(self, event=None):
        """Switch active file when user selects from listbox."""
        sel = self.files_listbox.curselection()
        if not sel:
            return
        fname = self._listbox_filenames[sel[0]]
        loaded = self.shared_data.get('loaded_files', {})
        if fname not in loaded:
            return
        rec = loaded[fname]
        # Push selected file into shared_data and local state
        self._save_outgoing_regression_params(fname)
        self.shared_data['active_file'] = fname
        self.shared_data['df_raw']      = rec['df_raw']
        self.shared_data['cycle_list']  = rec['cycle_list']
        self.shared_data['ici_starts']  = rec['ici_starts']
        self.shared_data['filename']    = rec['filename']
        all_params = self.shared_data.get('all_regression_params', {})
        self.shared_data['regression_params'] = all_params.get(fname, {})
        self.df_raw      = rec['df_raw']
        self.cycle_list  = rec['cycle_list']
        self.update_cycle_selector()
        self._refresh_files_listbox()
        self.status_label.config(
            text=f"Active: {os.path.basename(fname)}  |  {len(self.cycle_list)} cycles")


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
            # Reset stale state so this tab doesn't keep operating on
            # already-removed data (e.g. after Data tab's "Remove All").
            self.df_raw = None
            self.cycle_list = []
            self.update_cycle_selector()
            self.status_label.config(text="Ready - Load data in Data Tab first")

        # Always refresh the file panels, even when df_raw is None — otherwise
        # removing all files in Data tab leaves stale entries showing here.
        self._refresh_files_listbox()
        if hasattr(self, 'cap_rows_inner'):
            self._refresh_cap_files_listbox()

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
            
            # PLOT DIRECTLY IN GUI 
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
                            color=cycle_color, linewidth=1.5, alpha=0.8, markersize=2)
            else:
                # viridis: Use position within ALL cycles for consistent coloring (not index in selected)
                if len(self.cycle_list) > 1:
                    cycle_normalized = (cycle_num - min(self.cycle_list)) / (max(self.cycle_list) - min(self.cycle_list))
                else:
                    cycle_normalized = 0.0  # Single cycle case
                cycle_color = cmap(cycle_normalized)  # Use normalized position, not colors[i]
                self.phase_ax.plot(cycle_data['time_norm'], cycle_data['E/V'], '-o',
                            color=cycle_color, label=f'Cycle {cycle_num}',
                            linewidth=1.5, alpha=0.8, markersize=2)
        
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

    def export_capacity_data(self):
        """Export the underlying data of the last-drawn Capacity vs Voltage plot as CSV."""
        if self._last_capacity_export_df is None or self._last_capacity_export_df.empty:
            messagebox.showwarning("No Data", "Plot capacity vs voltage first.")
            return

        # Same "<filename>_<thing>.csv" naming scheme as Tab 5's export
        # (e.g. "10 cycles data_R_k_results_charge.csv").
        if 'File' in self._last_capacity_export_df.columns:
            default_name = "capacity_overlay.csv"
        else:
            active_fname = self.shared_data.get('active_file') or self.shared_data.get('filename') or ''
            prefix = os.path.splitext(os.path.basename(active_fname))[0] if active_fname else "capacity_analysis"
            default_name = f"{prefix}_capacity.csv"

        filepath = filedialog.asksaveasfilename(
            title="Export Capacity vs Voltage Data",
            defaultextension=".csv",
            initialfile=default_name,
            filetypes=[("CSV", "*.csv")]
        )

        if not filepath:
            return

        try:
            self._last_capacity_export_df.to_csv(filepath, index=False)
            messagebox.showinfo("Export", f"Capacity data exported:\n{filepath}")

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
                self.phase_ax.set_ylabel(source_ax.get_ylabel(), fontsize=12)
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
                    
                    ax2.set_ylabel(source_ax2.get_ylabel(), color='orange', fontsize=12)
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
        """Calculate capacity from current integration with reset at each phase change.

        Delegates to analysis.phase_classifier.calculate_capacity so the Kinetics
        tab can reuse the exact same computation (single source of truth).
        """
        return phase_classifier.calculate_capacity(data, mass_mg)

    def _sync_mass_to_shared(self, fname, mass_mg):
        """Record the mass used to compute a capacity plot for `fname` so the
        Kinetics tab can look it up (via shared_data['file_mass_mg']) without
        needing its own mass field or recomputing capacity itself."""
        if fname:
            self.shared_data.setdefault('file_mass_mg', {})[fname] = mass_mg

    def _get_cap_mass_for_file(self, fname):
        """Read the mass (mg) entered for `fname` in the per-file 'Loaded
        Files' panel. This is the single source of truth for mass — there is
        no shared/global mass field, so each file's own value is always used
        regardless of which file is currently active."""
        file_vars = self.cap_file_vars.get(fname, {})
        try:
            return float(file_vars['mass_var'].get()) if file_vars else 0.0
        except (ValueError, KeyError):
            return 0.0

    def _on_cap_overlay_toggled(self):
        """Re-plot immediately when 'Overlay all files' is checked/unchecked,
        instead of waiting for another click on a Plot button."""
        if self.df_raw is None or not self.capacity_cycle_var.get().strip():
            return
        self.plot_capacity_vs_voltage()

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

            # Get mass from this file's row in the per-file panel
            active_fname = self.shared_data.get('active_file')
            mass_mg = self._get_cap_mass_for_file(active_fname)

            self.status_label.config(text=f"Plotting capacity vs voltage for {len(selected_cycles)} cycles...")
            self.parent.update()

            if self.cap_overlay_var.get() and len(self.shared_data.get('loaded_files', {})) > 1:
                self.plot_capacity_overlay()
            else:
                self._sync_mass_to_shared(active_fname, mass_mg)
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
            
            # Use capacity plotting — overlay uses per-file entries, not the shared cycle var
            if self.cap_overlay_var.get() and len(self.shared_data.get('loaded_files', {})) > 1:
                self.plot_capacity_overlay()
            else:
                self.plot_capacity_vs_voltage()
            
        except Exception as e:
            messagebox.showerror("Plot Error", f"Error plotting all capacity cycles:\n{str(e)}")
            print(f"All capacity cycles plot error: {e}")
    
    def plot_capacity_overlay(self):
        """Plot capacity vs voltage for ALL loaded files, one colour per file."""
        loaded = self.shared_data.get('loaded_files', {})
        if not loaded:
            messagebox.showwarning("No Data", "No files loaded.")
            return

        # Remove old colorbar
        if self.capacity_colorbar is not None:
            try:
                self.capacity_colorbar.remove()
            except (KeyError, ValueError, AttributeError):
                pass
            self.capacity_colorbar = None

        self.capacity_fig.clear()
        self.capacity_ax = self.capacity_fig.add_subplot(111)

        any_specific = False
        export_frames = []

        for i, (fname, rec) in enumerate(loaded.items()):
            color = self._get_overlay_color(i)
            short = os.path.basename(fname)

            # Get per-file cycles and mass from the panel
            file_vars = self.cap_file_vars.get(fname, {})
            try:
                cycles_str = file_vars['cycles_var'].get() if file_vars else ''
                selected_cycles = self.parse_cycle_input(cycles_str) if cycles_str else rec['cycle_list']
            except Exception:
                selected_cycles = rec['cycle_list']
            mass_mg = self._get_cap_mass_for_file(fname)
            self._sync_mass_to_shared(fname, mass_mg)

            if mass_mg > 0:
                any_specific = True

            df = rec['df_raw']
            selected_data = df[df['cycle'].isin(selected_cycles)].copy()
            if len(selected_data) == 0:
                continue

            capacity_data = self.calculate_capacity(selected_data, mass_mg)
            if 'cycle_phase' not in capacity_data.columns:
                capacity_data['cycle_phase'] = phase_classifier.classify_charge_discharge(capacity_data)

            file_export = capacity_data[['cycle', 'cycle_phase', 't/s', 'E/V',
                                          'capacity_mAh', 'specific_capacity']].copy()
            file_export.insert(0, 'File', short)
            file_export.columns = ['File', 'Cycle', 'Phase', 'Time (s)', 'Voltage (V)',
                                    'Capacity (mAh)', 'Specific Capacity (mAh/g)']
            export_frames.append(file_export)

            x_col = 'specific_capacity' if mass_mg > 0 else 'capacity_mAh'

            total_cycles = len(selected_cycles)
            for j, cycle_num in enumerate(selected_cycles):
                cycle_data = capacity_data[capacity_data['cycle'] == cycle_num].copy()
                if len(cycle_data) == 0:
                    continue
                charge_data    = cycle_data[cycle_data['cycle_phase'] == 'charge']
                discharge_data = cycle_data[cycle_data['cycle_phase'] == 'discharge']
                cycle_color = self._get_cycle_shade(color, j, total_cycles)
                label = f"{short} C{cycle_num}" if j == 0 else f"{short} C{cycle_num}"

                if not charge_data.empty:
                    self.capacity_ax.plot(charge_data[x_col], charge_data['E/V'], '-o',
                                        color=cycle_color, label=label,
                                        linewidth=1.5, alpha=0.8, markersize=2)
                if not discharge_data.empty:
                    self.capacity_ax.plot(discharge_data[x_col], discharge_data['E/V'], '-o',
                                        color=cycle_color, label='_nolegend_',
                                        linewidth=1.5, alpha=0.8, markersize=2)

        self._last_capacity_export_df = (
            pd.concat(export_frames, ignore_index=True) if export_frames else None)

        xlabel = 'Specific Capacity (mAh/g)' if any_specific else 'Capacity (mAh)'
        self.capacity_ax.set_xlabel(xlabel, fontsize=12)
        self.capacity_ax.set_ylabel('Voltage (V)', fontsize=12)
        self.capacity_ax.grid(True, alpha=0.3)

        full_title = f'Capacity vs Voltage - Overlay ({len(loaded)} files)'
        self._capacity_title = full_title
        if self.show_title_var.get():
            self.capacity_ax.set_title(full_title, fontsize=12, fontweight='bold')

        legend = self.capacity_ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
        legend.set_draggable(True)
        legend.set_zorder(100)
        legend.get_frame().set_facecolor('white')
        legend.get_frame().set_alpha(0.9)
        legend.get_frame().set_edgecolor('black')

        self.capacity_fig.tight_layout()
        self.capacity_canvas.draw()
        self.status_label.config(text=f"Overlay: {len(loaded)} files plotted")


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

        # Stash the plotted data so "Export Data" can save exactly what's on screen
        export_df = capacity_data[['cycle', 'cycle_phase', 't/s', 'E/V',
                                    'capacity_mAh', 'specific_capacity']].copy()
        export_df.columns = ['Cycle', 'Phase', 'Time (s)', 'Voltage (V)',
                              'Capacity (mAh)', 'Specific Capacity (mAh/g)']
        self._last_capacity_export_df = export_df

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
                              linewidth=1.5, alpha=0.8, markersize=2)
            
            if not discharge_data.empty:
                self.capacity_ax.plot(discharge_data[x_col], discharge_data['E/V'], '-o',
                              color=cycle_color,  # No label for discharge (matches notebook)
                              linewidth=1.5, alpha=0.8, markersize=2)
        
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