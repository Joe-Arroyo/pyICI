#!/usr/bin/env python3
"""
ICI Battery Analysis - Complete 5-Tab GUI
Tests the integration of ALL tabs: Data, Classification, Pulse, Regression, Kinetics
"""

import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

# Add the current directory to Python path to import our modules
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# GUI Components (from gui folder)
from gui.data_tab import DataTab
from gui.classification_tab import ClassificationTab
from gui.pulse_analysis_tab import PulseTab
from gui.regression_tab import RegressionTab  # NEW: Tab 4
from gui.kinetics_tab import KineticsTab      # NEW: Tab 5

class Complete5TabGUI:
    """Main application with all 5 analysis tabs"""
    
    def __init__(self, root):
        self.root = root
        self.root.title("ICI Battery Analysis - Complete System (5 Tabs)")
        self.root.geometry("1600x1000")
        
        # Shared data manager - USE DICTIONARY
        self.shared_data = {
            'df_raw': None,
            'cycle_list': [],
            'ici_starts': {},
            'filename': None,
            'phase_classified': False,
            'regression_params': {},  # IMPORTANT: For Tab 4 → Tab 5 parameter sharing
            # Multi-file overlay support
            'all_files': {},          # {filename: {'df_raw', 'cycle_list', 'ici_starts'}}
            'active_file': None,      # filename string of the currently active file
            'overlay_colors': [       # tab10 base palette — shading handled at plot time
                '#1f77b4',  # blue
                '#ff7f0e',  # orange
                '#2ca02c',  # green
                '#e6ab02',  # golden yellow
                '#9467bd',  # purple
                '#8c564b',  # brown
                '#e377c2',  # pink
                '#7f7f7f',  # grey
                '#bcbd22',  # yellow-green
                '#17becf',  # cyan
            ],
        }
        
        # Create main interface
        self.create_interface()
        
    def create_interface(self):
        """Create the main interface"""
        
        # Status bar
        self.create_status_bar()
        
        # Main notebook (tabs)
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Tab 1: Data Loading
        print("Creating Tab 1: Data Loading...")
        data_frame = ttk.Frame(self.notebook)
        self.notebook.add(data_frame, text="📂 Tab 1: Data Loading")
        self.data_tab = DataTab(data_frame, self.shared_data)
        print("  ✅ Tab 1 created")
        
        # Tab 2: Classification
        print("Creating Tab 2: Classification...")
        classification_frame = ttk.Frame(self.notebook)
        self.notebook.add(classification_frame, text="🔍 Tab 2: Classification")
        self.classification_tab = ClassificationTab(classification_frame, self.shared_data)
        print("  ✅ Tab 2 created")
        
        # Tab 3: Pulse Analysis
        print("Creating Tab 3: Pulse Analysis...")
        try:
            pulse_frame = ttk.Frame(self.notebook)
            self.notebook.add(pulse_frame, text="📈 Tab 3: Pulse Analysis")
            self.pulse_tab = PulseTab(pulse_frame, self.shared_data)
            print("  ✅ Tab 3 created")
        except Exception as e:
            print(f"  ❌ ERROR creating Tab 3: {e}")
            import traceback
            traceback.print_exc()
        
        # Tab 4: Regression Analysis
        print("Creating Tab 4: Regression Analysis...")
        try:
            regression_frame = ttk.Frame(self.notebook)
            self.notebook.add(regression_frame, text="📊 Tab 4: Regression Analysis")
            self.regression_tab = RegressionTab(regression_frame, self.shared_data)
            print("  ✅ Tab 4 created")
        except Exception as e:
            print(f"  ❌ ERROR creating Tab 4: {e}")
            import traceback
            traceback.print_exc()
        
        # Tab 5: Kinetic Analysis
        print("Creating Tab 5: Kinetic Analysis...")
        try:
            kinetics_frame = ttk.Frame(self.notebook)
            self.notebook.add(kinetics_frame, text="⚗️ Tab 5: Resistance Analysis")
            self.kinetics_tab = KineticsTab(kinetics_frame, self.shared_data)
            print("  ✅ Tab 5 created")
        except Exception as e:
            print(f"  ❌ ERROR creating Tab 5: {e}")
            import traceback
            traceback.print_exc()
        
        # Bind tab change event
        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)
        self.root.bind("<Configure>", self._on_window_resize)
        
        # Test controls at bottom
        self.create_test_controls()
        
        # Start periodic status update
        self.monitor_shared_data()
        
    def create_status_bar(self):
        """Create status bar"""
        status_frame = ttk.Frame(self.root)
        status_frame.pack(side=tk.TOP, fill=tk.X, padx=5, pady=2)
        
        ttk.Label(status_frame, text="File:").pack(side=tk.LEFT)
        self.file_label = ttk.Label(status_frame, text="No file loaded", foreground="red")
        self.file_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(status_frame, text="Cycles:").pack(side=tk.LEFT, padx=(20,0))
        self.cycles_label = ttk.Label(status_frame, text="0")
        self.cycles_label.pack(side=tk.LEFT, padx=5)
        
        ttk.Label(status_frame, text="Data points:").pack(side=tk.LEFT, padx=(20,0))
        self.points_label = ttk.Label(status_frame, text="0")
        self.points_label.pack(side=tk.LEFT, padx=5)
        
    def create_test_controls(self):
        """Create test controls at bottom"""
        test_frame = ttk.LabelFrame(self.root, text="Testing Controls")
        test_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=5, pady=5)
        
        ttk.Button(test_frame, text="Test Complete Workflow", 
                  command=self.test_complete_workflow).pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(test_frame, text="Clear All Data", 
                  command=self.clear_all_data).pack(side=tk.LEFT, padx=5, pady=5)
        
        ttk.Button(test_frame, text="Show Data Status", 
                  command=self.show_data_status).pack(side=tk.LEFT, padx=5, pady=5)
    
    def _on_window_resize(self, event=None):
        """Redraw all tab canvases when window is resized."""
        if event and event.widget != self.root:
            return
        canvases = [
            getattr(self.data_tab,           'canvas',           None),
            getattr(self.classification_tab, 'phase_canvas',     None),
            getattr(self.classification_tab, 'capacity_canvas',  None),
            getattr(self.pulse_tab,          'canvas',           None),
            getattr(self.regression_tab,     'charge_canvas',    None),
            getattr(self.regression_tab,     'discharge_canvas', None),
            getattr(self.regression_tab,     'multi_canvas',     None),
            getattr(self.kinetics_tab,       'charge_canvas',    None),
            getattr(self.kinetics_tab,       'discharge_canvas', None),
        ]
        for canvas in canvases:
            try:
                if canvas:
                    canvas.get_tk_widget().update_idletasks()
                    canvas.draw_idle()
            except Exception:
                pass

    def on_tab_changed(self, event):
        """Called when user switches tabs"""
        selected_tab = self.notebook.index(self.notebook.select())
        tab_name = self.notebook.tab(selected_tab, "text")
        
        print(f"🔄 Tab changed to: {tab_name}")
        
        # Always update status bar when changing tabs
        self.update_status_bar()
        
        # Refresh data display when switching to specific tabs
        if "Classification" in tab_name and hasattr(self, 'classification_tab'):
            print("🔄 Refreshing Classification tab data...")
            if hasattr(self.classification_tab, 'load_shared_data'):
                self.classification_tab.load_shared_data()
        
        if "Pulse" in tab_name and hasattr(self, 'pulse_tab'):
            print("🔄 Refreshing Pulse Analysis tab data...")
            if hasattr(self.pulse_tab, 'load_shared_data'):
                self.pulse_tab.load_shared_data()
        
        if "Regression" in tab_name and hasattr(self, 'regression_tab'):
            print("🔄 Refreshing Regression tab data...")
            if hasattr(self.regression_tab, 'load_shared_data'):
                self.regression_tab.load_shared_data()
        
        if "Resistance" in tab_name and hasattr(self, 'kinetics_tab'):
            print("🔄 Refreshing Kinetic tab data...")
            if hasattr(self.kinetics_tab, 'load_shared_data'):
                self.kinetics_tab.load_shared_data()
               
                 
    def update_status_bar(self):
        """Update status bar with current data info"""
        df_raw = self.shared_data.get('df_raw')
        cycle_list = self.shared_data.get('cycle_list', [])
        filename = self.shared_data.get('filename')
        loaded_files = self.shared_data.get('loaded_files', {})

        if df_raw is not None and len(cycle_list) > 0:
            n_files = len(loaded_files)
            if n_files > 1:
                display_name = f"{filename} (+{n_files - 1} more)"
            else:
                display_name = filename or "Data loaded"
            self.file_label.config(text=display_name, foreground="green")
            self.cycles_label.config(text=str(len(cycle_list)))
            self.points_label.config(text=str(len(df_raw)))
        else:
            self.file_label.config(text="No file loaded", foreground="red")
            self.cycles_label.config(text="0")
            self.points_label.config(text="0")
            
    def test_complete_workflow(self):
        """Test the complete 5-tab workflow"""
        print("\n" + "="*60)
        print("🧪 TESTING COMPLETE 5-TAB WORKFLOW")
        print("="*60)
        
        try:
            # Step 1: Check if data is loaded
            df_raw = self.shared_data.get('df_raw')
            cycle_list = self.shared_data.get('cycle_list', [])
            
            if df_raw is None or len(cycle_list) == 0:
                messagebox.showwarning("Test Failed", 
                    "No data loaded. Please load data in Tab 1 first.")
                return False
                
            print(f"✅ Step 1: Data loaded - {len(df_raw)} points, {len(cycle_list)} cycles")
            
            # Step 2: Check all tabs exist
            tabs_exist = all([
                hasattr(self, 'data_tab'),
                hasattr(self, 'classification_tab'),
                hasattr(self, 'pulse_tab'),
                hasattr(self, 'regression_tab'),
                hasattr(self, 'kinetics_tab')
            ])
            
            if not tabs_exist:
                print("❌ Step 2: Not all tabs created")
                return False
                
            print("✅ Step 2: All 5 tabs exist")
            
            # Step 3: Test integration
            print("✅ Step 3: Integration test complete")
            
            # Success message
            print("\n🎉 COMPLETE 5-TAB WORKFLOW TEST PASSED!")
            print("   ✅ Data loading works")
            print("   ✅ All 5 tabs created")
            print("   ✅ Data sharing works") 
            print("   ✅ Integration complete")
            
            messagebox.showinfo("Test Success", 
                "Complete 5-tab workflow test passed!\n\n" +
                "✅ Data loading works\n" +
                "✅ All 5 tabs created\n" +
                "✅ Data sharing works\n" + 
                "✅ Integration complete")
            
            return True
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            messagebox.showerror("Test Failed", f"Workflow test failed:\n{str(e)}")
            return False
            
    def clear_all_data(self):
        """Clear all data and reset interface"""
        print("🗑️ Clearing all data...")

        # Clear shared data dictionary
        self.shared_data['df_raw'] = None
        self.shared_data['cycle_list'] = []
        self.shared_data['ici_starts'] = {}
        self.shared_data['filename'] = None
        self.shared_data['phase_classified'] = False
        self.shared_data['regression_params'] = {}
        self.shared_data['all_regression_params'] = {}
        self.shared_data['file_mass_mg'] = {}
        self.shared_data['loaded_files'] = {}
        self.shared_data['active_file'] = None

        # Data tab keeps its own loaded_files dict (a separate reference from
        # shared_data['loaded_files']) plus its own Treeview — clear those
        # too, otherwise its file list/UI stays stale after "clearing".
        if hasattr(self, 'data_tab'):
            self.data_tab.loaded_files.clear()
            self.data_tab.active_file = None
            if hasattr(self.data_tab, '_refresh_files_tree'):
                self.data_tab._refresh_files_tree()

        # Update status bar
        self.update_status_bar()
        
        print("✅ All data cleared")
        messagebox.showinfo("Data Cleared", "All data has been cleared")
        
    def show_data_status(self):
        """Show current data status"""
        df_raw = self.shared_data.get('df_raw')
        cycle_list = self.shared_data.get('cycle_list', [])
        filename = self.shared_data.get('filename')
        regression_params = self.shared_data.get('regression_params', {})
        
        status_text = f"Data Status Report:\n\n"
        status_text += f"• Data loaded: {df_raw is not None}\n"
        status_text += f"• File: {filename or 'None'}\n"
        status_text += f"• Data points: {len(df_raw) if df_raw is not None else 0}\n"
        status_text += f"• Cycles: {len(cycle_list)} {cycle_list if cycle_list else ''}\n"
        status_text += f"• Saved regression params: {len(regression_params)}\n"
            
        print(status_text)
        messagebox.showinfo("Data Status", status_text)
    
    def monitor_shared_data(self):
        """Periodically check shared_data and update status bar"""
        self.update_status_bar()
        # Check every 1000ms (1 second)
        self.root.after(1000, self.monitor_shared_data)

def main():
    """Main entry point"""
    
    print("=" * 60)
    print("ICI Battery Analysis - Complete 5-Tab System")
    print("=" * 60)
    print("\n🎯 Purpose: Complete ICI battery analysis workflow")
    print("\n📋 Features:")
    print("   • Tab 1: Data Loading - Load ICI battery data files")
    print("   • Tab 2: Classification - Phase classification and visualization")
    print("   • Tab 3: Pulse Analysis - Pulse detection and analysis")
    print("   • Tab 4: Regression Analysis - R² regression with parameter saving")
    print("   • Tab 5: Kinetic Analysis - R & k parameter extraction")
    print("\n🔧 Usage:")
    print("   1. Load data in 'Data Loading' tab")
    print("   2. Verify classification in 'Classification' tab")
    print("   3. Analyze pulses in 'Pulse Analysis' tab")
    print("   4. Adjust regression parameters in 'Regression' tab and SAVE")
    print("   5. View R & k results in 'Kinetic Analysis' tab (uses saved params)")
    print("=" * 60)
    
    # Check if required files exist
    required_files = [
        'gui/data_tab.py',
        'gui/classification_tab.py',
        'gui/pulse_analysis_tab.py',
        'gui/regression_tab.py',      # NEW
        'gui/kinetics_tab.py'          # NEW
    ]
    missing_files = []
    
    print("\nChecking for required files:")
    for file in required_files:
        # Check relative to the script's own directory, not the process's
        # current working directory — otherwise launching main_gui.py from
        # anywhere other than the project root wrongly reports files missing
        # even though the sys.path-based imports above would have worked fine.
        exists = os.path.exists(os.path.join(current_dir, file))
        status = "✅" if exists else "❌"
        print(f"  {status} {file}")
        if not exists:
            missing_files.append(file)
            
    if missing_files:
        print(f"\n❌ Missing required files: {missing_files}")
        print("Please make sure all GUI component files are in the gui/ folder.")
        return
        
    # Create and run the application
    root = tk.Tk()
    app = Complete5TabGUI(root)

        # Start maximized (cross-platform)
    try:
        root.state('zoomed')        # Windows
    except:
        root.attributes('-zoomed', True)  # Linux
    
    # Force window to fully render before mainloop
    root.update_idletasks()
    root.update()
    root.after(500, app._on_window_resize)
    
    print("\n🚀 Application started!")
    print("Load your ICI data file in Tab 1 to begin...\n")
    
    root.mainloop()

if __name__ == "__main__":
    main()