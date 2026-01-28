#!/usr/bin/env python3
"""
Data Loading Tab - UPGRADED Version with Inline Export
GUI for ICI Battery Analysis with Smart Export Controls
Uses the actual data_loader.py functions with 3/4 column support
WITH AUTO-CLASSIFICATION: Automatically classifies all cycles after loading

UPGRADES ADDED:
✅ Inline export function (no external dependency)
✅ Export controls positioned next to Data Visualization  
✅ No titles in exported plots (professional output)
✅ Maintains all existing functionality
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib.figure import Figure
import pandas as pd
import numpy as np
import os

# Import the actual data_loader module
import analysis.data_loader as data_loader
# Import phase classifier for auto-classification
from analysis.phase_classifier import classify_charge_discharge

# INLINE EXPORT FUNCTION (no external dependency)
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

class DataTab:
    def __init__(self, parent, shared_data):
        """
        Initialize Data Loading Tab using actual data_loader.py functions
        
        Args:
            parent: Parent frame (notebook tab)
            shared_data: Dictionary to share data between tabs
        """
        self.parent = parent
        self.shared_data = shared_data
        
        # Data storage - will reference data_loader module variables
        self.df_raw = None
        self.cycle_list = []
        self.ici_starts = {}  # Changed to dict like data_loader.py
        self.plot_data = None
        self.current_file = None
        
        # Track colorbar to remove old ones
        self.current_colorbar = None
        
        # Variables to store full title text for easy toggling
        self._overview_title = ""
        self._individual_v_title = ""
        self._individual_c_title = ""
        
        # Remember last browsed folder (shared across tabs via shared_data)
        if 'last_folder' not in self.shared_data:
            self.shared_data['last_folder'] = os.path.expanduser("~")
        
        # Create GUI
        self.create_widgets()
    
    def create_widgets(self):
        """Create all GUI widgets for data loading tab - COMPACT LAYOUT"""
        
        # ==============================
        # SINGLE ROW CONTROL LAYOUT - MAXIMIZES PLOT SPACE
        # ==============================
        main_control_frame = ttk.Frame(self.parent)
        main_control_frame.pack(side=tk.TOP, fill=tk.X, padx=10, pady=10)
        
        # File selection (spans full width)
        file_frame = ttk.LabelFrame(main_control_frame, text="Data File Selection", padding=5)
        file_frame.pack(fill=tk.X, pady=(0, 5))
        
        ttk.Label(file_frame, text="File:").grid(row=0, column=0, sticky=tk.W, padx=5)
        self.file_entry = ttk.Entry(file_frame, width=40)
        self.file_entry.grid(row=0, column=1, padx=5, sticky=tk.EW)
        
        ttk.Button(file_frame, text="Browse...", command=self.browse_file).grid(row=0, column=2, padx=5)
        ttk.Button(file_frame, text="Load Data", command=self.load_data_file).grid(row=0, column=3, padx=5)
        
        file_frame.columnconfigure(1, weight=1)
        
        # ALL CONTROLS IN ONE ROW
        controls_row_frame = ttk.Frame(main_control_frame)
        controls_row_frame.pack(fill=tk.X, pady=5)
        
        # 1. Data Visualization Controls (LEFT)
        viz_frame = ttk.LabelFrame(controls_row_frame, text="Data Visualization", padding=5)
        viz_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        
        ttk.Label(viz_frame, text="Select:").grid(row=0, column=0, padx=2, pady=1, sticky=tk.W)
        self.cycle_var = tk.StringVar()
        self.cycle_combo = ttk.Combobox(viz_frame, textvariable=self.cycle_var, 
                                       width=10, state='readonly')
        self.cycle_combo.grid(row=0, column=1, padx=2, pady=1, sticky=tk.W)
        self.cycle_combo.bind('<<ComboboxSelected>>', self.on_cycle_selected)
        
        ttk.Button(viz_frame, text="All Cycles", 
                  command=self.plot_overview_proper).grid(row=1, column=0, padx=2, pady=1, sticky=tk.EW)
        ttk.Button(viz_frame, text="Individual", 
                  command=self.plot_individual_cycle).grid(row=1, column=1, padx=2, pady=1, sticky=tk.EW)
        
        # Title toggle
        self.show_title_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(viz_frame, text="Show titles", variable=self.show_title_var,
                       command=self.refresh_titles).grid(row=2, column=0, columnspan=2, padx=2, pady=2, sticky=tk.W)
        
        # 2. Export Figure Controls (CENTER-LEFT)
        export_frame = ttk.LabelFrame(controls_row_frame, text="Export Figure", padding=5)
        export_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5)

        ttk.Label(export_frame, text="Width (in):").grid(row=0, column=0, padx=2, pady=1, sticky=tk.W)
        self.export_width_var = tk.DoubleVar(value=8.0)
        ttk.Entry(export_frame, textvariable=self.export_width_var, width=6).grid(row=0, column=1, padx=2, pady=1)

        ttk.Label(export_frame, text="Height (in):").grid(row=0, column=2, padx=2, pady=1, sticky=tk.W)
        self.export_height_var = tk.DoubleVar(value=6.0)
        ttk.Entry(export_frame, textvariable=self.export_height_var, width=6).grid(row=0, column=3, padx=2, pady=1)

        ttk.Label(export_frame, text="DPI:").grid(row=1, column=0, padx=2, pady=1, sticky=tk.W)
        self.export_dpi_var = tk.IntVar(value=300)
        ttk.Entry(export_frame, textvariable=self.export_dpi_var, width=6).grid(row=1, column=1, padx=2, pady=1)

        ttk.Label(export_frame, text="Format:").grid(row=1, column=2, padx=2, pady=1, sticky=tk.W)
        self.export_format_var = tk.StringVar(value="png")
        ttk.Combobox(export_frame, textvariable=self.export_format_var, values=["png", "pdf", "svg"], 
                    width=5, state="readonly").grid(row=1, column=3, padx=2, pady=1)

        ttk.Button(export_frame, text="Export", 
                  command=self.export_current_figure).grid(row=2, column=0, columnspan=4, pady=3, sticky=tk.W)
        
        # 3. Data Information (CENTER-RIGHT) 
        info_frame = ttk.LabelFrame(controls_row_frame, text="Data Information", padding=5)
        info_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=5)

        info_frame.config(width=500)
        info_frame.pack_propagate(False)
        
        # Create frame for text widget with scrollbar
        info_text_frame = ttk.Frame(info_frame)
        info_text_frame.pack(fill=tk.BOTH, expand=True)
        
        self.info_text = tk.Text(info_text_frame, height=4, width=30, state='disabled', 
                                font=('Arial', 8), wrap=tk.WORD)
        info_scrollbar = ttk.Scrollbar(info_text_frame, orient=tk.VERTICAL, command=self.info_text.yview)
        self.info_text.configure(yscrollcommand=info_scrollbar.set)
        
        self.info_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        info_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # 4. Analysis Parameters (LEFT)
        params_frame = ttk.LabelFrame(controls_row_frame, text="Analysis Parameters", padding=5)
        params_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(5, 0))
        
        ttk.Label(params_frame, text="Max Rest (s):").grid(row=0, column=0, sticky=tk.W, padx=2, pady=1)
        self.max_rest_var = tk.StringVar(value=str(data_loader.MAX_REST_DURATION))
        ttk.Entry(params_frame, textvariable=self.max_rest_var, width=8).grid(row=0, column=1, padx=2, pady=1)
        
        ttk.Label(params_frame, text="Current (mA):").grid(row=1, column=0, sticky=tk.W, padx=2, pady=1)
        self.current_threshold_var = tk.StringVar(value=str(data_loader.CURRENT_THRESHOLD))
        ttk.Entry(params_frame, textvariable=self.current_threshold_var, width=8).grid(row=1, column=1, padx=2, pady=1)
        
        # Help text (smaller)
        help_label = ttk.Label(params_frame, text="ℹ️ Affects pulse detection", 
                              font=('Arial', 7), foreground='gray')
        help_label.grid(row=2, column=0, columnspan=2, pady=2)
        
        # ==============================
        # PLOT FRAME - MAXIMIZED SPACE
        # ==============================
        plot_frame = ttk.LabelFrame(self.parent, text="Plot Area", padding=5)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        # ==============================
        # PLOT FRAME - MAXIMIZED SPACE
        # ==============================
        plot_frame = ttk.LabelFrame(self.parent, text="Plot Area", padding=5)
        plot_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create matplotlib figure with proper backend for GUI
        self.fig = Figure(figsize=(12, 8))
        self.ax1 = self.fig.add_subplot(211)  # Top plot: Voltage
        self.ax2 = self.fig.add_subplot(212)  # Bottom plot: Current
        
        self.canvas = FigureCanvasTkAgg(self.fig, plot_frame)
        
        # Add navigation toolbar for zoom/pan functionality
        self.toolbar = NavigationToolbar2Tk(self.canvas, plot_frame)
        self.toolbar.update()
        
        # Pack in correct order: toolbar at bottom, canvas fills remaining space
        self.toolbar.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True)
                
        # Status bar
        self.status_label = ttk.Label(self.parent, text="Ready - Select a data file to begin", 
                                      relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
    
    def export_current_figure(self):
        """Export current figure with NO TITLES"""
        if self.fig is None:
            messagebox.showwarning("No Figure", "No figure to export")
            return

        fmt = self.export_format_var.get()
        filepath = filedialog.asksaveasfilename(
            title="Export Data Visualization",
            defaultextension=f".{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")],
            initialdir=self.shared_data.get('last_folder', os.path.expanduser("~"))
        )

        if not filepath:
            return
        
        # Remember folder for next time
        self.shared_data['last_folder'] = os.path.dirname(filepath)

        try:
            export_figure(
                self.fig,
                filepath,
                width_in=self.export_width_var.get(),
                height_in=self.export_height_var.get(),
                dpi=self.export_dpi_var.get()
            )
            # Redraw canvas to restore any title changes
            self.canvas.draw()
            
        except Exception as e:
            messagebox.showerror("Export Error", str(e))
            import traceback
            traceback.print_exc()
    
    # ==============================
    # ORIGINAL FUNCTIONALITY (PRESERVED)
    # ==============================
    
    def browse_file(self):
        """Open file browser to select data file"""
        filename = filedialog.askopenfilename(
            title="Select ICI Data File",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialdir=self.shared_data.get('last_folder', os.path.expanduser("~"))
        )
        
        if filename:
            # Remember the folder for next time
            self.shared_data['last_folder'] = os.path.dirname(filename)
            
            self.file_entry.delete(0, tk.END)
            self.file_entry.insert(0, filename)
            self.status_label.config(text=f"Selected: {os.path.basename(filename)}")
    
    def load_data_file(self):
        """Load and process the selected data file using data_loader.py"""
        filepath = self.file_entry.get().strip()
        
        if not filepath:
            messagebox.showwarning("No File", "Please select a data file first")
            return
        
        if not os.path.exists(filepath):
            messagebox.showerror("File Not Found", f"File does not exist:\n{filepath}")
            return
        
        try:
            self.status_label.config(text="Loading data using data_loader.py...")
            self.parent.update()
            
            # Extract folder and filename
            folder_path = os.path.dirname(filepath)
            filename = os.path.basename(filepath)
            
            # Update data_loader parameters with GUI values
            try:
                data_loader.MAX_REST_DURATION = float(self.max_rest_var.get())
                data_loader.CURRENT_THRESHOLD = float(self.current_threshold_var.get())
            except ValueError:
                messagebox.showwarning("Invalid Parameters", 
                    "Invalid parameter values. Using defaults.")
                data_loader.MAX_REST_DURATION = 1800
                data_loader.CURRENT_THRESHOLD = 1.0
            
            # Temporarily disable matplotlib plotting to prevent popup windows
            original_backend = plt.get_backend()
            plt.switch_backend('Agg')  # Non-interactive backend
            
            # Temporarily replace plt.show with a no-op function
            original_show = plt.show
            plt.show = lambda: None
            
            try:
                # Call the actual data_loader function in non-interactive mode
                success = data_loader.run_data_analysis(
                    folder_path=folder_path,
                    txt_file_name=filename,
                    interactive=False
                )
            finally:
                # Restore original matplotlib settings
                plt.show = original_show
                plt.switch_backend(original_backend)
            
            if not success:
                messagebox.showerror("Load Error", 
                    "Failed to load data. Check console for details.")
                return
            
            # Get the loaded data from data_loader module
            if data_loader.df_raw is None:
                messagebox.showerror("Load Error", 
                    "No data was loaded. Check file format and content.")
                return
            
            # Store references to the loaded data
            self.df_raw = data_loader.df_raw
            self.cycle_list = data_loader.cycle_list if data_loader.cycle_list else []
            self.ici_starts = data_loader.ici_starts if data_loader.ici_starts else {}
            self.plot_data = data_loader.plot_data if hasattr(data_loader, 'plot_data') else self.df_raw
            self.current_file = filename
            
            # ===================================================================
            # AUTO-CLASSIFICATION: Classify all cycles automatically
            # ===================================================================
            self.status_label.config(text="Auto-classifying all cycles...")
            self.parent.update()
            
            try:
                print("\n" + "="*60)
                print("AUTO-CLASSIFICATION")
                print("="*60)
                
                # Classify the entire dataset at once
                self.df_raw['cycle_phase'] = classify_charge_discharge(self.df_raw)
                
                # Calculate and display statistics
                phase_counts = self.df_raw['cycle_phase'].value_counts()
                total = len(self.df_raw)
                
                print(f"\nAuto-classification complete for ALL cycles:")
                print(f"  Charge: {phase_counts.get('charge', 0):,} points ({phase_counts.get('charge', 0)/total*100:.1f}%)")
                print(f"  Discharge: {phase_counts.get('discharge', 0):,} points ({phase_counts.get('discharge', 0)/total*100:.1f}%)")
                print(f"  Rest: {phase_counts.get('rest', 0):,} points ({phase_counts.get('rest', 0)/total*100:.1f}%)")
                print("="*60)
                
                # Update data_loader module variable too
                data_loader.df_raw = self.df_raw
                
            except Exception as e:
                print(f"Warning: Auto-classification failed: {e}")
                print("Tabs will auto-classify as needed")
                import traceback
                traceback.print_exc()
            
            # ===================================================================
            # END AUTO-CLASSIFICATION
            # ===================================================================
            
            # Update shared data for other tabs (now includes cycle_phase column)
            self.shared_data['df_raw'] = self.df_raw
            self.shared_data['cycle_list'] = self.cycle_list
            self.shared_data['ici_starts'] = self.ici_starts
            self.shared_data['plot_data'] = self.plot_data
            self.shared_data['filename'] = filename
            self.shared_data['data_format'] = getattr(data_loader, 'data_format', 'unknown')
            self.shared_data['phase_classified'] = 'cycle_phase' in self.df_raw.columns
            
            # Update cycle selector
            self.update_cycle_selector()
            
            # Update info display
            self.update_info_display()
            
            # Plot overview using data_loader.py function
            self.plot_overview_proper()
            
            # Status message includes classification info
            phase_status = " (all cycles pre-classified)" if 'cycle_phase' in self.df_raw.columns else ""
            self.status_label.config(text=f"Loaded: {filename} - {len(self.df_raw)} points, {len(self.cycle_list)} cycles{phase_status}")
            
            # Show success message
            data_format_info = getattr(data_loader, 'data_format', 'unknown')
            classification_info = "\nAll cycles auto-classified!" if 'cycle_phase' in self.df_raw.columns else ""
            
            messagebox.showinfo("Success", 
                f"Data loaded successfully!{classification_info}\n\n"
                f"File: {filename}\n"
                f"Format: {data_format_info}\n"
                f"Data points: {len(self.df_raw):,}\n"
                f"Cycles: {len(self.cycle_list)}\n"
                f"ICI starts found: {len(self.ici_starts)}")
            
        except Exception as e:
            self.status_label.config(text="Load failed")
            messagebox.showerror("Error", f"Failed to load data:\n{str(e)}")
            import traceback
            traceback.print_exc()
    
    def update_info_display(self):
        """Update the information text display"""
        if self.df_raw is None:
            return
        
        info = []
        info.append(f"File: {self.current_file}")
        info.append(f"Data Points: {len(self.df_raw):,}")
        
        if hasattr(data_loader, 'data_format'):
            info.append(f"Format: {data_loader.data_format}")
            
        info.append(f"Cycles: {len(self.cycle_list)} - Range: {min(self.cycle_list) if self.cycle_list else 'N/A'} to {max(self.cycle_list) if self.cycle_list else 'N/A'}")
        info.append(f"ICI Start Points: {len(self.ici_starts)}")
        
        # Show classification status
        if 'cycle_phase' in self.df_raw.columns:
            phase_counts = self.df_raw['cycle_phase'].value_counts()
            info.append(f"Classification: ALL CYCLES AUTO-CLASSIFIED")
            info.append(f"  - Charge: {phase_counts.get('charge', 0):,} | Discharge: {phase_counts.get('discharge', 0):,} | Rest: {phase_counts.get('rest', 0):,}")
        
        # Find column names (support different naming conventions)
        time_col = self.find_column(['t/s', 'time', 't(s)', 'Time'])
        voltage_col = self.find_column(['E/V', 'Ewe/V', 'voltage', 'potential'])
        current_col = self.find_column(['I/mA', 'current', 'i(ma)', 'Current'])
        
        if time_col:
            info.append(f"Time Range: {self.df_raw[time_col].min():.1f} - {self.df_raw[time_col].max():.1f} s")
        if voltage_col:
            info.append(f"Voltage Range: {self.df_raw[voltage_col].min():.3f} - {self.df_raw[voltage_col].max():.3f} V")
        if current_col:
            info.append(f"Current Range: {self.df_raw[current_col].min():.2f} - {self.df_raw[current_col].max():.2f} mA")
        
        self.info_text.config(state='normal')
        self.info_text.delete(1.0, tk.END)
        self.info_text.insert(1.0, '\n'.join(info))
        self.info_text.config(state='disabled')
    
    def find_column(self, possible_names):
        """Find column by checking multiple possible names"""
        if self.df_raw is None:
            return None
        
        for col in self.df_raw.columns:
            if col in possible_names:
                return col
            # Case-insensitive check
            for name in possible_names:
                if col.lower() == name.lower():
                    return col
        return None
    
    def update_cycle_selector(self):
        """Update the cycle selector combobox with available cycles"""
        if self.cycle_list:
            cycle_options = ['All Cycles'] + [f'Cycle {c}' for c in self.cycle_list]
            self.cycle_combo['values'] = cycle_options
            self.cycle_combo.current(0)  # Default to "All Cycles"
        else:
            self.cycle_combo['values'] = []
    
    def on_cycle_selected(self, event=None):
        """Handle cycle selection from combobox"""
        selection = self.cycle_var.get()
        if selection == 'All Cycles':
            self.plot_overview_proper()
        elif selection.startswith('Cycle '):
            cycle_num = int(selection.split(' ')[1])
            self.plot_individual_cycle(cycle_num)
    
    def refresh_titles(self):
        """Refresh plot titles when the title toggle changes."""
        
        # Check if any plot data exists
        if len(self.ax1.lines) == 0:
            return

        # Overview plot uses ax1 only (ax2 is None)
        # Individual plot uses ax1 and ax2
        is_individual_cycle = (self.ax2 is not None)

        if self.show_title_var.get():
            # SHOW TITLES: Restore saved titles
            if hasattr(self, '_overview_title') and not is_individual_cycle:
                self.ax1.set_title(self._overview_title, fontsize=14, fontweight='bold')
            elif hasattr(self, '_individual_v_title') and is_individual_cycle:
                self.ax1.set_title(self._individual_v_title)
                self.ax2.set_title(self._individual_c_title)
        else:
            # HIDE TITLES: Save current titles (if not already saved) and set to empty string
            if not is_individual_cycle:
                # The plot functions already set the title based on the checkbox state, 
                # but we explicitly save the full title text here for safety.
                if self.ax1.get_title() != '':
                    self._overview_title = self.ax1.get_title()
                self.ax1.set_title('')
            else:
                if self.ax1.get_title() != '':
                    self._individual_v_title = self.ax1.get_title()
                if self.ax2.get_title() != '':
                    self._individual_c_title = self.ax2.get_title()
                self.ax1.set_title('')
                self.ax2.set_title('')
        
        # FIX: Adjust layout to prevent title cutting
        self.fig.tight_layout()
        self.canvas.draw()

    def plot_individual_cycle(self, cycle_num=None):
        """Plot individual cycle with detailed voltage and current plots (like data_loader.py)"""
        if self.df_raw is None:
            return
        
        # Get cycle number from combobox if not provided
        if cycle_num is None:
            selection = self.cycle_var.get()
            if not selection.startswith('Cycle '):
                messagebox.showwarning("No Cycle Selected", "Please select a specific cycle")
                return
            cycle_num = int(selection.split(' ')[1])
        
        # Get cycle data
        plot_data = self.plot_data if self.plot_data is not None else self.df_raw
        cycle_data = plot_data[plot_data['cycle'] == cycle_num]
        
        if len(cycle_data) == 0:
            messagebox.showerror("No Data", f"No data found for cycle {cycle_num}")
            return
        
        try:
            # CRITICAL: Remove colorbar if exists (from overview mode)
            if self.current_colorbar is not None:
                self.current_colorbar.remove()
                self.current_colorbar = None
            
            # Restore 2-subplot layout for individual cycle view
            self.fig.clear()  # Clear entire figure
            self.ax1 = self.fig.add_subplot(211)  # Top plot: Voltage
            self.ax2 = self.fig.add_subplot(212)  # Bottom plot: Current
            
            # --- VOLTAGE PLOT (ax1) ---
            
            # Save the full title text first
            full_title_v = f'Cycle {cycle_num} - Voltage vs Time'
            self._individual_v_title = full_title_v # SAVE full title

            # Plot 1: Voltage vs Time (same as data_loader.py plot_cycle function)
            line_voltage, = self.ax1.plot(cycle_data['t/s'], cycle_data['E/V'], 'b-', linewidth=2, label='Voltage')
            self.ax1.set_xlabel('Time (s)')
            self.ax1.set_ylabel('Voltage (V)')
            
            # Set title based on checkbox
            if self.show_title_var.get():
                self.ax1.set_title(full_title_v) # Use saved full title
            else:
                self.ax1.set_title('')
            
            self.ax1.grid(True, alpha=0.3)
            
            # --- CURRENT PLOT (ax2) ---
            
            # Save the full title text first
            full_title_c = f'Cycle {cycle_num} - Current vs Time'
            self._individual_c_title = full_title_c # SAVE full title

            # Plot 2: Current vs Time
            line_current, = self.ax2.plot(cycle_data['t/s'], cycle_data['I/mA'], 'g-', linewidth=2, label='Current')
            self.ax2.axhline(y=0, color='black', linestyle='--', alpha=0.5)
            self.ax2.set_xlabel('Time (s)')
            self.ax2.set_ylabel('Current (mA)')
            
            # Set title based on checkbox
            if self.show_title_var.get():
                self.ax2.set_title(full_title_c) # Use saved full title
            else:
                self.ax2.set_title('')
            
            self.ax2.grid(True, alpha=0.3)
            
            # Collect all legend handles and labels
            handles = [line_voltage, line_current]
            labels = ['Voltage', 'Current']
            
            # Add ICI start markers if available
            if cycle_num in self.ici_starts:
                start_idx = self.ici_starts[cycle_num]
                if start_idx in cycle_data.index:
                    start_point = cycle_data.loc[start_idx]
                    # Mark on voltage plot (smaller markers)
                    scatter_v = self.ax1.scatter(start_point['t/s'], start_point['E/V'], 
                                   color='red', s=30, marker='o', 
                                   label=f'ICI Start', zorder=5, edgecolor='black', linewidth=1)
                    # Mark on current plot (smaller markers)
                    self.ax2.scatter(start_point['t/s'], start_point['I/mA'], 
                                   color='red', s=30, marker='o', 
                                   zorder=5, edgecolor='black', linewidth=1)
                    # Add to legend handles
                    handles.append(scatter_v)
                    labels.append('ICI Start')
            
            # Create single combined legend on top plot (voltage)
            legend = self.ax1.legend(handles, labels, loc='best')
            legend.set_draggable(True)  # Make the combined legend draggable!
            legend.set_zorder(100)  # Bring legend to front
            legend.get_frame().set_facecolor('white')
            legend.get_frame().set_alpha(0.9)  # Semi-transparent background
            legend.get_frame().set_edgecolor('black')
            
            self.fig.tight_layout()
            self.canvas.draw()
            
            # Update status with cycle statistics (like data_loader.py)
            duration = cycle_data['t/s'].max() - cycle_data['t/s'].min()
            voltage_range = f"{cycle_data['E/V'].min():.3f} - {cycle_data['E/V'].max():.3f}"
            self.status_label.config(text=f"Cycle {cycle_num}: {len(cycle_data)} points, {duration:.1f}s, {voltage_range}V")
            
        except Exception as e:
            messagebox.showerror("Plot Error", f"Error plotting cycle {cycle_num}:\n{str(e)}")
            print(f"Individual cycle plot error: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_overview_proper(self):
        """
        Plot data overview using the EXACT same function from data_loader.py
        This will show ICI start points and proper cycle differentiation
        FIXED: Uses full figure area and prevents shrinking
        """
        if self.df_raw is None or not self.cycle_list:
            self.ax1.clear()
            self.ax2.clear()
            self.ax1.text(0.5, 0.5, 'No data loaded', 
                         ha='center', va='center', transform=self.ax1.transAxes)
            self.canvas.draw()
            return
        
        try:
            # CRITICAL: Remove old colorbar first to prevent layout issues
            if self.current_colorbar is not None:
                self.current_colorbar.remove()
                self.current_colorbar = None
            
            # Clear and reconfigure for FULL FIGURE overview plot
            self.fig.clear()  # Clear entire figure to reset layout
            self.ax1 = self.fig.add_subplot(111)  # Use FULL figure (not 211)
            self.ax2 = None  # No second plot for overview
            
            # Use the plot_data from data_loader (downsampled if needed)
            plot_data = self.plot_data if self.plot_data is not None else self.df_raw
            
            # SMART COLORMAP SYSTEM based on number of cycles
            num_cycles = len(self.cycle_list)
            
            if num_cycles <= 10:
                # Use tab10 colormap for few cycles (≤10)
                cmap = plt.cm.tab10
                colors = cmap(np.linspace(0, 1, num_cycles))
                use_colorbar = False
            else:
                # Use viridis colormap for many cycles (>10)
                cmap = plt.colormaps['viridis']
                use_colorbar = True
            
            # Plot each cycle with appropriate colors
            for i, cycle_num in enumerate(self.cycle_list):
                cycle_data = plot_data[plot_data['cycle'] == cycle_num]
                if len(cycle_data) > 0:
                    if use_colorbar:
                        # viridis: gradient coloring for many cycles
                        # Map cycle_num to 0-1 range to match colorbar EXACTLY
                        cycle_normalized = (cycle_num - min(self.cycle_list)) / (max(self.cycle_list) - min(self.cycle_list))
                        # Use full viridis range to match colorbar (no offset!)
                        cycle_color = cmap(cycle_normalized)
                    else:
                        # tab10: distinct colors for few cycles
                        cycle_color = colors[i]
                    
                    # Plot cycle data (only add to legend if NOT using colorbar)
                    if use_colorbar:
                        # No label when using colorbar
                        self.ax1.plot(cycle_data['t/s'], cycle_data['E/V'], 
                                    color=cycle_color, alpha=0.7, linewidth=1.5)
                    else:
                        # Add label when using regular legend
                        self.ax1.plot(cycle_data['t/s'], cycle_data['E/V'], 
                                    label=f'Cycle {cycle_num}', color=cycle_color, alpha=0.7, linewidth=1.5)
                    
                    # Mark ICI start point if available (smaller markers)
                    if cycle_num in self.ici_starts:
                        start_idx = self.ici_starts[cycle_num]
                        if start_idx in cycle_data.index:
                            start_point = cycle_data.loc[start_idx]
                            self.ax1.scatter(start_point['t/s'], start_point['E/V'], 
                                          color=cycle_color, s=30, marker='o', edgecolor='black', linewidth=1,
                                          zorder=5)
            
            # Formatting (same as data_loader.py)
            self.ax1.set_xlabel('Time (s)', fontsize=12)
            self.ax1.set_ylabel('Voltage (V)', fontsize=12)
            
            # Add classification status to title if available
            title_suffix = " (All Cycles Auto-Classified)" if 'cycle_phase' in self.df_raw.columns else ""
            
            # --- TITLE LOGIC ---
            full_title_o = f'ICI Analysis - Overview (Raw data): All Cycles with ICI Start Points{title_suffix}'
            self._overview_title = full_title_o # SAVE full title

            # Set title based on checkbox
            if self.show_title_var.get():
                self.ax1.set_title(full_title_o, 
                                 fontsize=14, fontweight='bold')
            else:
                self.ax1.set_title('')
            
            # LEGEND/COLORBAR LOGIC based on number of cycles
            # CRITICAL: Remove old colorbar first to prevent stacking
            if self.current_colorbar is not None:
                self.current_colorbar.remove()
                self.current_colorbar = None
            
            if num_cycles > 10:
                # MANY CYCLES: Use COLORBAR only (no regular legend)
                from matplotlib.cm import ScalarMappable
                from matplotlib.colors import Normalize
                
                # Normalize cycle numbers to 0-1 range
                norm = Normalize(vmin=min(self.cycle_list), vmax=max(self.cycle_list))
                sm = ScalarMappable(cmap=cmap, norm=norm)
                sm.set_array([])  # Required for colorbar
                
                # Add colorbar on the right side and SAVE REFERENCE
                self.current_colorbar = self.fig.colorbar(sm, ax=self.ax1, pad=0.02, fraction=0.046)
                self.current_colorbar.set_label('Cycle Number', rotation=270, labelpad=20, fontsize=11, fontweight='bold')
                
                # Set explicit ticks
                min_cycle = min(self.cycle_list)
                max_cycle = max(self.cycle_list)
                
                # Calculate nice tick positions
                if num_cycles <= 20:
                    # Show all cycles for small ranges
                    tick_positions = self.cycle_list
                elif num_cycles <= 50:
                    # Show every 5th cycle
                    tick_positions = [c for c in self.cycle_list if c % 5 == 0 or c == min_cycle or c == max_cycle]
                else:
                    # Show every 10th cycle for large ranges
                    tick_positions = [c for c in self.cycle_list if c % 10 == 0 or c == min_cycle or c == max_cycle]
                
                # Ensure min and max are always included
                if min_cycle not in tick_positions:
                    tick_positions = [min_cycle] + tick_positions
                if max_cycle not in tick_positions:
                    tick_positions = tick_positions + [max_cycle]
                
                # Set ticks
                self.current_colorbar.set_ticks(sorted(set(tick_positions)))
                self.current_colorbar.set_ticklabels([str(int(t)) for t in sorted(set(tick_positions))])
                
                # Add ICI start points text annotation (no legend box)
                if len(self.ici_starts) > 0:
                    self.ax1.text(0.02, 0.98, f'⚫ ICI Start Points ({len(self.ici_starts)})',
                                transform=self.ax1.transAxes,
                                verticalalignment='top',
                                bbox=dict(boxstyle='round', facecolor='white', alpha=0.9, edgecolor='black'),
                                fontsize=10, zorder=100)
            else:
                # FEW CYCLES: Use REGULAR LEGEND (tab10 colors)
                # Add ICI Start Points to legend
                if len(self.ici_starts) > 0:
                    self.ax1.scatter([], [], color='gray', s=80, marker='o', edgecolor='black', 
                                  linewidth=2, label=f'ICI Start Points ({len(self.ici_starts)})')
                
                # Regular legend on right side
                legend = self.ax1.legend(bbox_to_anchor=(1.05, 1), loc='upper left')
                legend.set_draggable(True)  # Make legend draggable!
                legend.set_zorder(100)  # Bring legend to front
                legend.get_frame().set_facecolor('white')
                legend.get_frame().set_alpha(0.9)  # Semi-transparent background
                legend.get_frame().set_edgecolor('black')
            
            self.ax1.grid(True, alpha=0.3)
            
            self.fig.tight_layout()
            self.canvas.draw()
            
            # Reset status
            class_status = " - All cycles pre-classified" if 'cycle_phase' in self.df_raw.columns else ""
            self.status_label.config(text=f"Overview: {len(self.cycle_list)} cycles, {len(self.ici_starts)} ICI starts{class_status}")
            
            print(f"GUI Overview plot created with {len(self.ici_starts)} ICI start points marked")
            
        except Exception as e:
            self.ax1.clear()
            self.ax1.text(0.5, 0.5, f'Plot error:\n{str(e)}', 
                         ha='center', va='center', transform=self.ax1.transAxes)
            self.canvas.draw()
            print(f"Plot error: {e}")
            import traceback
            traceback.print_exc()
    
    def plot_overview(self):
        """Legacy function - now redirects to proper plotting function"""
        self.plot_overview_proper()
    
    def get_data(self):
        """Return loaded data for other tabs to use"""
        return {
            'df_raw': self.df_raw,
            'cycle_list': self.cycle_list,
            'ici_starts': self.ici_starts,
            'plot_data': self.plot_data,
            'filename': self.current_file,
            'data_format': getattr(data_loader, 'data_format', 'unknown'),
            'phase_classified': 'cycle_phase' in self.df_raw.columns if self.df_raw is not None else False
        }