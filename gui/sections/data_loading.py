#!/usr/bin/env python3
"""Data-loading section for the new pyICI GUI.

Two views, both ported from the original app:
  * "Voltage vs time"  (data_tab overview / overlay): one colour per cycle
    (tab10 + legend <=10, viridis + colorbar >10) with ICI start markers; or one
    colour per file in overlay. Optional current subplot.
  * "Capacity vs voltage" (classification tab): capacity (or specific capacity
    when a mass is given) vs voltage, charge + discharge per cycle, viridis
    coloured by cycle (legend / colorbar), or one colour per file in overlay.

Uses the real analysis layer (analysis.data_loader, analysis.phase_classifier).
"""
import os
import tkinter as tk
from tkinter import filedialog

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import customtkinter as ctk

from gui import theme
from gui.components.plot_panel import PlotPanel
from gui.components.export_helper import export_figure
from gui.components.scroll import AutoHideScrollableFrame
import analysis.data_loader as data_loader
import analysis.phase_classifier as phase_classifier
import analysis.rk_analyzer as ka

# One colour per file for the overlay view (tab10-style palette).
FILE_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

VIEW_TIME = "Voltage vs time"
VIEW_CAPACITY = "Capacity vs voltage"


def _truncate_cmap(cmap, lo=0.4, hi=1.0, n=256):
    """A colormap restricted to [lo, hi] of ``cmap`` so a colorbar reads the same
    0.4->1.0 shades the per-cycle lines use."""
    from matplotlib.colors import LinearSegmentedColormap
    return LinearSegmentedColormap.from_list(f"{cmap.name}_t", cmap(np.linspace(lo, hi, n)))


class DataLoadingSection(ctk.CTkFrame):
    """Left controls + right plot for loading data, viewing cycles and capacity."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self.files = {}          # name -> {path, df_raw, plot_data, cycle_list, ici_starts, mass}
        self.active_name = None
        self._capacity_export_df = None   # data behind the last capacity plot (for CSV export)

        self.view_var = tk.StringVar(value=VIEW_TIME)
        self.show_current_var = tk.BooleanVar(value=False)
        self.overlay_var = tk.BooleanVar(value=False)
        self.cycle_text_var = tk.StringVar(value="")
        self.path_var = tk.StringVar()
        self.mass_var = tk.StringVar(value="0")

        # Advanced / plot settings (axis limits + export)
        self.xmin_var = tk.StringVar(value="")
        self.xmax_var = tk.StringVar(value="")
        self.ymin_var = tk.StringVar(value="")
        self.ymax_var = tk.StringVar(value="")
        self.fig_w_var = tk.StringVar(value="8")
        self.fig_h_var = tk.StringVar(value="6")
        self.dpi_var = tk.StringVar(value="300")
        self.fmt_var = tk.StringVar(value="png")
        self._settings_open = False

        self._build()

    # ---- layout -----------------------------------------------------------
    def _build(self):
        controls_card, outer = theme.card(self, "Data loading - controls", width=theme.CONTROL_W)
        controls_card.pack(side="left", fill="y", padx=(0, theme.GAP))
        controls_card.pack_propagate(False)
        # #6 - a little inset so controls don't span the full card width.
        body = AutoHideScrollableFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=(2, 12))

        # #7 - section labels: bigger, bold, dark (easily readable).
        def slabel(text, pady=(0, 2)):
            ctk.CTkLabel(body, text=text, font=theme.font_sans(13, "bold"),
                         text_color=theme.TEXT, anchor="w").pack(fill="x", pady=pady)

        slabel("Data file")
        self.path_entry = ctk.CTkEntry(body, textvariable=self.path_var,
                                       font=theme.font_sans(12), corner_radius=theme.RADIUS_INPUT)
        self.path_entry.pack(fill="x", pady=(2, 6))
        row = ctk.CTkFrame(body, fg_color="transparent")
        row.pack(fill="x")
        # #4 - Browse and Add file equal width.
        ctk.CTkButton(row, text="Browse…", command=self._browse,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT,
                      font=theme.font_sans(13), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ctk.CTkButton(row, text="Add file", command=self._add_file,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(13, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", fill="x", expand=True, padx=(3, 0))

        slabel("Loaded files", pady=(10, 2))
        self.files_list = ctk.CTkScrollableFrame(body, height=110, fg_color=theme.BG,
                                                 corner_radius=theme.RADIUS_INPUT)
        self.files_list.pack(fill="x")
        self._refresh_files_list()
        # #3 - clear everything and return to the first-open state.
        ctk.CTkButton(body, text="Clear all", command=self._clear_all,
                      fg_color=theme.SURFACE, text_color=theme.MUTED, border_color=theme.BORDER,
                      border_width=1, hover_color="#f3d4d4", font=theme.font_sans(12),
                      corner_radius=theme.RADIUS_INPUT).pack(fill="x", pady=(6, 0))

        ctk.CTkCheckBox(body, text="Overlay all files", variable=self.overlay_var,
                        command=self._apply_and_plot, font=theme.font_sans(13), text_color=theme.TEXT,
                        fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER
                        ).pack(anchor="w", pady=(8, 0))

        # #5 - View selector: bordered (contour), white text + white arrow on teal.
        slabel("View", pady=(10, 2))
        ctk.CTkComboBox(body, variable=self.view_var, values=[VIEW_TIME, VIEW_CAPACITY],
                        state="readonly", command=lambda _c: self._apply_and_plot(),
                        fg_color=theme.ACCENT, text_color="#ffffff",
                        border_color=theme.ACCENT_HOVER, border_width=1,
                        button_color=theme.ACCENT_HOVER, button_hover_color=theme.ACCENT,
                        font=theme.font_sans(13), dropdown_font=theme.font_sans(13),
                        dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
                        dropdown_hover_color=theme.ACCENT_TINT).pack(fill="x")

        slabel("Cycles", pady=(10, 2))
        self.cycle_entry = ctk.CTkEntry(body, textvariable=self.cycle_text_var,
                                        placeholder_text="blank = all,  e.g. 1,3,5 or 1-5",
                                        font=theme.font_sans(13), corner_radius=theme.RADIUS_INPUT)
        self.cycle_entry.pack(fill="x")
        self.cycle_entry.bind("<Return>", lambda e: self._apply_and_plot())
        self.cycle_hint = ctk.CTkLabel(body, text="", font=theme.font_sans(12),
                                       text_color=theme.MUTED, anchor="w")
        self.cycle_hint.pack(fill="x")

        slabel("Mass (mg)", pady=(10, 2))
        ctk.CTkLabel(body, text="0 = capacity  ·  >0 = specific", font=theme.font_sans(12),
                     text_color=theme.MUTED, anchor="w").pack(fill="x")
        self.mass_entry = ctk.CTkEntry(body, textvariable=self.mass_var, font=theme.font_mono(13),
                                       corner_radius=theme.RADIUS_INPUT)
        self.mass_entry.pack(fill="x", pady=(2, 0))
        self.mass_entry.bind("<Return>", lambda e: self._apply_and_plot())

        ctk.CTkCheckBox(body, text="Show current (time view)", variable=self.show_current_var,
                        command=self._apply_and_plot, font=theme.font_sans(13), text_color=theme.TEXT,
                        fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER
                        ).pack(anchor="w", pady=(10, 0))
        ctk.CTkButton(body, text="Plot", command=self._apply_and_plot,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(13, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(fill="x", pady=(12, 0))

        # Collapsible "Plot settings" panel (axis limits + export)
        self.adv_toggle = ctk.CTkButton(
            body, text="⚙  Plot settings   +", anchor="w", height=30,
            command=self._toggle_settings, fg_color=theme.BG, text_color=theme.MUTED,
            hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
            corner_radius=theme.RADIUS_INPUT)
        self.adv_toggle.pack(fill="x", pady=(10, 0))
        self.settings_frame = ctk.CTkFrame(body, fg_color=theme.BG,
                                           corner_radius=theme.RADIUS_INPUT)
        self._build_settings(self.settings_frame)   # built once; shown on toggle

        # CSV export of the capacity / specific-capacity data (capacity view only)
        ctk.CTkButton(body, text="Export capacity CSV", command=self._export_capacity_csv,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT, font=theme.font_sans(13),
                      corner_radius=theme.RADIUS_INPUT).pack(fill="x", pady=(8, 0))

        plot_card, plot_body = theme.card(self, "Data loading - plots")
        plot_card.pack(side="left", fill="both", expand=True)
        self.panel = PlotPanel(plot_body, figsize=(8, 6))
        self.panel.pack(fill="both", expand=True)

    # ---- advanced / plot settings panel -----------------------------------
    def _build_settings(self, parent):
        pad = 8
        ctk.CTkLabel(parent, text="Axis limits  (blank = auto)",
                     font=theme.font_sans(12, "bold"), text_color=theme.TEXT,
                     anchor="w").pack(fill="x", padx=pad, pady=(pad, 2))

        def _lim_row(label, lo_var, hi_var):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", padx=pad, pady=1)
            ctk.CTkLabel(r, text=label, font=theme.font_sans(12), text_color=theme.MUTED,
                         width=16).pack(side="left")
            ctk.CTkEntry(r, textvariable=lo_var, placeholder_text="min", width=74,
                         font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT
                         ).pack(side="left", padx=(4, 4))
            ctk.CTkEntry(r, textvariable=hi_var, placeholder_text="max", width=74,
                         font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT
                         ).pack(side="left")

        _lim_row("X", self.xmin_var, self.xmax_var)
        _lim_row("Y", self.ymin_var, self.ymax_var)

        btn_row = ctk.CTkFrame(parent, fg_color="transparent")
        btn_row.pack(fill="x", padx=pad, pady=(4, pad))
        ctk.CTkButton(btn_row, text="Apply", command=self._plot, width=74,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left")
        ctk.CTkButton(btn_row, text="Auto", command=self._reset_axes, width=74,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT,
                      border_color=theme.ACCENT, border_width=1,
                      hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
                      corner_radius=theme.RADIUS_INPUT).pack(side="left", padx=(6, 0))

        ctk.CTkFrame(parent, fg_color=theme.BORDER, height=1).pack(fill="x", padx=pad, pady=2)

        ctk.CTkLabel(parent, text="Export", font=theme.font_sans(12, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(fill="x", padx=pad, pady=(6, 2))

        size_row = ctk.CTkFrame(parent, fg_color="transparent")
        size_row.pack(fill="x", padx=pad, pady=1)
        ctk.CTkLabel(size_row, text="Size (in)", font=theme.font_sans(12),
                     text_color=theme.MUTED, width=62, anchor="w").pack(side="left")
        ctk.CTkEntry(size_row, textvariable=self.fig_w_var, width=58, font=theme.font_mono(12),
                     corner_radius=theme.RADIUS_INPUT).pack(side="left")
        ctk.CTkLabel(size_row, text="×", font=theme.font_sans(12),
                     text_color=theme.MUTED, width=16).pack(side="left")
        ctk.CTkEntry(size_row, textvariable=self.fig_h_var, width=58, font=theme.font_mono(12),
                     corner_radius=theme.RADIUS_INPUT).pack(side="left")

        dpi_row = ctk.CTkFrame(parent, fg_color="transparent")
        dpi_row.pack(fill="x", padx=pad, pady=1)
        ctk.CTkLabel(dpi_row, text="DPI", font=theme.font_sans(12),
                     text_color=theme.MUTED, width=62, anchor="w").pack(side="left")
        ctk.CTkEntry(dpi_row, textvariable=self.dpi_var, width=58, font=theme.font_mono(12),
                     corner_radius=theme.RADIUS_INPUT).pack(side="left")
        ctk.CTkLabel(dpi_row, text="Format", font=theme.font_sans(12),
                     text_color=theme.MUTED, anchor="e").pack(side="left", padx=(12, 4))
        ctk.CTkOptionMenu(dpi_row, variable=self.fmt_var, values=["png", "pdf", "svg", "tiff"],
                          width=78, fg_color=theme.SURFACE, text_color=theme.TEXT,
                          button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                          font=theme.font_sans(12), dropdown_font=theme.font_sans(12)
                          ).pack(side="left")

        ctk.CTkButton(parent, text="Export figure", command=self._export,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(13, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(fill="x", padx=pad, pady=(6, pad))

    def _toggle_settings(self):
        self._settings_open = not self._settings_open
        if self._settings_open:
            self.settings_frame.pack(fill="x", pady=(6, 0))
            self.adv_toggle.configure(text="⚙  Plot settings   –")
        else:
            self.settings_frame.pack_forget()
            self.adv_toggle.configure(text="⚙  Plot settings   +")

    def _apply_axis_limits(self, ax):
        """Apply any user-set axis limits to ``ax``; blank fields stay auto.

        Called at the end of each plot so a redraw keeps the chosen limits.
        With a shared-x current subplot, the x-limit propagates via sharex.
        """
        def _val(var):
            s = var.get().strip()
            if not s:
                return None
            try:
                return float(s)
            except ValueError:
                return None

        xlo, xhi = _val(self.xmin_var), _val(self.xmax_var)
        ylo, yhi = _val(self.ymin_var), _val(self.ymax_var)
        if xlo is not None or xhi is not None:
            ax.set_xlim(left=xlo, right=xhi)
        if ylo is not None or yhi is not None:
            ax.set_ylim(bottom=ylo, top=yhi)

    def _reset_axes(self):
        for v in (self.xmin_var, self.xmax_var, self.ymin_var, self.ymax_var):
            v.set("")
        self._plot()

    def _export(self):
        if not self.files:
            self._status("Nothing to export - load a file first")
            return
        try:
            w = float(self.fig_w_var.get())
            h = float(self.fig_h_var.get())
            dpi = int(float(self.dpi_var.get()))
        except ValueError:
            self._status("Figure size and DPI must be numbers")
            return
        if w <= 0 or h <= 0 or dpi <= 0:
            self._status("Figure size and DPI must be positive")
            return
        fmt = self.fmt_var.get()
        stem = os.path.splitext(self.active_name)[0] if self.active_name else "pyICI_plot"
        path = filedialog.asksaveasfilename(
            title="Export figure", defaultextension=f".{fmt}",
            initialfile=f"{stem}.{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")])
        if not path:
            return
        try:
            export_figure(self.panel.figure, path, width_in=w, height_in=h, dpi=dpi)
        except Exception as exc:
            self._status(f"Export failed: {exc}")
            return
        self._status(f"Exported → {os.path.basename(path)}  "
                     f"({w:g}×{h:g} in, {dpi} dpi)")

    # ---- file management --------------------------------------------------
    def _status(self, msg):
        try:
            self.app.set_status(msg)
        except Exception:
            pass

    def _browse(self):
        path = filedialog.askopenfilename(
            title="Select ICI data file",
            filetypes=[("Data files", "*.txt *.csv *.dat"), ("All files", "*.*")])
        if path:
            self.path_var.set(path)

    def _add_file(self):
        path = self.path_var.get().strip()
        if not path or not os.path.exists(path):
            self._status("Pick a valid data file first")
            return
        folder, name = os.path.split(path)
        self._status(f"Loading {name}…")
        result = data_loader.run_data_analysis(folder, name)
        if result is None:
            # Unrecognised layout -> let the user map the columns, then retry.
            result = self._load_with_column_map(folder, name, path)
            if result is None:
                return

        self.files[name] = {
            "path": path,
            "df_raw": result.df_raw,
            "plot_data": result.plot_data if result.plot_data is not None else result.df_raw,
            "cycle_list": list(result.cycle_list),
            "ici_starts": result.ici_starts if result.ici_starts else {},
            "mass": 0.0,
        }
        self.active_name = name
        self.mass_var.set("0")
        self._refresh_files_list()
        self._update_cycle_hint()
        self._status(f"Loaded {name}: {len(result.cycle_list)} cycles, "
                     f"{len(self.files[name]['ici_starts'])} ICI starts  ({len(self.files)} file(s))")
        self._plot()

    def _load_with_column_map(self, folder, name, path):
        """Pop the column-mapping dialog for an unrecognised layout and retry the
        load with the chosen mapping. Returns the DataLoadResult or None."""
        from gui.sections.column_map import ColumnMapDialog
        columns = data_loader.peek_columns(path)
        if not columns:
            self._status(f"Could not read columns from {name}")
            return None
        dlg = ColumnMapDialog(self, columns, filename=name)
        self.wait_window(dlg)
        if dlg.result is None:
            self._status("Load cancelled")
            return None
        result = data_loader.run_data_analysis(folder, name, column_map=dlg.result)
        if result is None:
            self._status(f"Could not load {name} with that column mapping")
        return result

    def _refresh_files_list(self):
        for w in self.files_list.winfo_children():
            w.destroy()
        if not self.files:
            ctk.CTkLabel(self.files_list, text="No files loaded", font=theme.font_sans(12),
                         text_color=theme.FAINT).pack(anchor="w", padx=4, pady=4)
            return
        for i, name in enumerate(self.files):
            is_active = (name == self.active_name)
            rowf = ctk.CTkFrame(self.files_list, fg_color="transparent")
            rowf.pack(fill="x", pady=1)
            ctk.CTkLabel(rowf, text="●", text_color=FILE_PALETTE[i % len(FILE_PALETTE)],
                         font=theme.font_sans(12), width=14).pack(side="left")
            ctk.CTkButton(
                rowf, text=name, anchor="w", height=26,
                command=lambda n=name: self._set_active(n),
                fg_color=(theme.ACCENT_TINT if is_active else "transparent"),
                text_color=(theme.ACCENT if is_active else theme.TEXT),
                hover_color=theme.ACCENT_TINT, corner_radius=theme.RADIUS_INPUT,
                font=theme.font_sans(12, "bold" if is_active else "normal")
            ).pack(side="left", fill="x", expand=True)
            ctk.CTkButton(rowf, text="✕", width=26, height=26,
                          command=lambda n=name: self._remove(n),
                          fg_color="transparent", text_color=theme.MUTED,
                          hover_color="#f3d4d4", corner_radius=theme.RADIUS_INPUT,
                          font=theme.font_sans(12)).pack(side="left", padx=(4, 0))

    def _set_active(self, name):
        if name in self.files:
            self.active_name = name
            self.mass_var.set(str(self.files[name].get("mass", 0.0)))
            self._refresh_files_list()
            self._update_cycle_hint()
            if not self.overlay_var.get():
                self._plot()

    def _remove(self, name):
        self.files.pop(name, None)
        if self.active_name == name:
            self.active_name = next(iter(self.files), None)
            if self.active_name:
                self.mass_var.set(str(self.files[self.active_name].get("mass", 0.0)))
        self._refresh_files_list()
        self._update_cycle_hint()
        self._status(f"Removed {name}")
        self._plot()

    def _clear_all(self):
        """Remove every loaded file, clear the plot, reset to the first-open state."""
        self.files = {}
        self.active_name = None
        self._capacity_export_df = None
        self.path_var.set("")
        self.cycle_text_var.set("")
        self.mass_var.set("0")
        self.overlay_var.set(False)
        self.show_current_var.set(False)
        self.view_var.set(VIEW_TIME)
        for v in (self.xmin_var, self.xmax_var, self.ymin_var, self.ymax_var):
            v.set("")
        self._refresh_files_list()
        self._update_cycle_hint()
        self.panel.figure.clear()
        self.panel.refresh()
        self._status("Cleared all files")

    def _update_cycle_hint(self):
        if self.active_name and self.active_name in self.files:
            cl = self.files[self.active_name]["cycle_list"]
            if cl:
                self.cycle_hint.configure(
                    text=f"Available: {min(cl)}\u2013{max(cl)}  ({len(cl)} cycles)")
                return
        self.cycle_hint.configure(text="")

    def _apply_and_plot(self):
        if self.active_name:
            try:
                self.files[self.active_name]["mass"] = float(self.mass_var.get())
            except ValueError:
                self._status("Mass must be a number")
        self._plot()

    def _selected_cycles(self, rec):
        cycles = ka.parse_cycle_input(self.cycle_text_var.get(), rec["cycle_list"])
        return cycles if cycles else rec["cycle_list"]

    # ---- plotting dispatch ------------------------------------------------
    def _plot(self):
        if not self.files:
            self._status("Load a file first")
            return
        if self.view_var.get() == VIEW_CAPACITY:
            self._plot_capacity()
        else:
            self._capacity_export_df = None     # CSV export is capacity-only
            self._plot_time()

    # ---- capacity CSV export ----------------------------------------------
    def _cap_export_cols(self, cap, file_name=None):
        """One capacity frame with the old GUI's column names (File optional)."""
        df = cap[["cycle", "cycle_phase", "t/s", "E/V",
                  "capacity_mAh", "specific_capacity"]].copy()
        df.columns = ["Cycle", "Phase", "Time (s)", "Voltage (V)",
                      "Capacity (mAh)", "Specific Capacity (mAh/g)"]
        if file_name is not None:
            df.insert(0, "File", file_name)
        return df

    def _stash_capacity_export(self, cap):
        self._capacity_export_df = self._cap_export_cols(cap)

    def _export_capacity_csv(self):
        if self.view_var.get() != VIEW_CAPACITY or self._capacity_export_df is None:
            self._status("Switch to the Capacity vs voltage view and plot first")
            return
        stem = os.path.splitext(self.active_name or "pyICI")[0] if self.active_name else "pyICI"
        if self.overlay_var.get() and len(self.files) > 1:
            stem = "pyICI_overlay"
        path = filedialog.asksaveasfilename(
            title="Export capacity data", defaultextension=".csv",
            initialfile=f"{stem}_capacity.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            self._capacity_export_df.to_csv(path, index=False)
        except Exception as exc:
            self._status(f"CSV export failed: {exc}")
            return
        self._status(f"Exported {len(self._capacity_export_df)} rows → "
                     f"{os.path.basename(path)}")

    # ---- time view (ported from data_tab) ---------------------------------
    def _plot_time(self):
        fig = self.panel.figure
        fig.clear()
        if self.show_current_var.get():
            ax_v = fig.add_subplot(211)
            ax_i = fig.add_subplot(212, sharex=ax_v)
        else:
            ax_v = fig.add_subplot(111)
            ax_i = None

        if self.overlay_var.get() and len(self.files) > 1:
            self._plot_time_overlay(fig, ax_v, ax_i)
        else:
            self._plot_time_single(fig, ax_v, ax_i)

        ax_v.set_ylabel("Voltage (V)")
        ax_v.grid(True, alpha=0.3)
        if ax_i is not None:
            ax_i.axhline(0, color="black", linestyle="--", alpha=0.5)
            ax_i.set_ylabel("Current (mA)")
            ax_i.set_xlabel("Time (s)")
            ax_i.grid(True, alpha=0.3)
        else:
            ax_v.set_xlabel("Time (s)")
        self._apply_axis_limits(ax_v)
        self.panel.refresh()

    def _mark_ici(self, ax, cycle_data, ici_starts, cycle_num, color, ycol):
        if cycle_num in ici_starts:
            start_idx = ici_starts[cycle_num]
            if start_idx in cycle_data.index:
                sp = cycle_data.loc[start_idx]
                ax.scatter(sp["t/s"], sp[ycol], color=color, s=30, marker="o",
                           edgecolor="black", linewidth=1, zorder=5)

    def _plot_time_single(self, fig, ax_v, ax_i):
        rec = self.files[self.active_name]
        plot_data = rec["plot_data"]
        ici = rec["ici_starts"]
        cycles = self._selected_cycles(rec)

        n = len(cycles)
        use_colorbar = n > 10
        if use_colorbar:
            cmap = plt.colormaps["viridis"]
            span = (max(cycles) - min(cycles)) or 1
        else:
            cmap = plt.cm.tab10
            colors = cmap(np.linspace(0, 1, max(n, 1)))

        for i, cyc in enumerate(cycles):
            cd = plot_data[plot_data["cycle"] == cyc]
            if len(cd) == 0:
                continue
            if use_colorbar:
                color = cmap((cyc - min(cycles)) / span)
                ax_v.plot(cd["t/s"], cd["E/V"], color=color, alpha=0.7, linewidth=1.5)
            else:
                color = colors[i]
                ax_v.plot(cd["t/s"], cd["E/V"], color=color, alpha=0.7, linewidth=1.5,
                          label=f"Cycle {cyc}")
            if ax_i is not None:
                ax_i.plot(cd["t/s"], cd["I/mA"], color=color, alpha=0.7, linewidth=1.5)
            self._mark_ici(ax_v, cd, ici, cyc, color, "E/V")
            if ax_i is not None:
                self._mark_ici(ax_i, cd, ici, cyc, color, "I/mA")

        if use_colorbar:
            from matplotlib.cm import ScalarMappable
            from matplotlib.colors import Normalize
            sm = ScalarMappable(cmap=cmap, norm=Normalize(vmin=min(cycles), vmax=max(cycles)))
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=ax_v, pad=0.02, fraction=0.046)
            cbar.set_label("Cycle number", rotation=270, labelpad=15)
            if len(ici) > 0:
                ax_v.text(0.02, 0.98, f"ICI start points ({len(ici)})",
                          transform=ax_v.transAxes, va="top", fontsize=9, zorder=100,
                          bbox=dict(boxstyle="round", facecolor="white", alpha=0.9, edgecolor="black"))
        else:
            if len(ici) > 0:
                ax_v.scatter([], [], color="gray", s=60, marker="o", edgecolor="black",
                             linewidth=1.5, label=f"ICI start ({len(ici)})")
            leg = ax_v.legend(loc="best", fontsize=8)
            if leg is not None:
                leg.set_draggable(True)
        self._status(f"Plotted {self.active_name}")

    def _plot_time_overlay(self, fig, ax_v, ax_i):
        for i, (name, rec) in enumerate(self.files.items()):
            color = FILE_PALETTE[i % len(FILE_PALETTE)]
            plot_data = rec["plot_data"]
            ici = rec["ici_starts"]
            for j, cyc in enumerate(rec["cycle_list"]):
                cd = plot_data[plot_data["cycle"] == cyc]
                if len(cd) == 0:
                    continue
                label = name if j == 0 else "_nolegend_"
                ax_v.plot(cd["t/s"], cd["E/V"], color=color, alpha=0.7, linewidth=1.5, label=label)
                if ax_i is not None:
                    ax_i.plot(cd["t/s"], cd["I/mA"], color=color, alpha=0.7, linewidth=1.5)
                self._mark_ici(ax_v, cd, ici, cyc, color, "E/V")
                if ax_i is not None:
                    self._mark_ici(ax_i, cd, ici, cyc, color, "I/mA")
        leg = ax_v.legend(loc="best", fontsize=8)
        if leg is not None:
            leg.set_draggable(True)
        self._status(f"Overlay: {len(self.files)} files")

    # ---- capacity view (ported from classification_tab) -------------------
    def _plot_capacity(self):
        fig = self.panel.figure
        fig.clear()
        ax = fig.add_subplot(111)

        if self.overlay_var.get() and len(self.files) > 1:
            self._plot_capacity_overlay(fig, ax)
        else:
            self._plot_capacity_single(fig, ax)

        ax.set_ylabel("Voltage (V)")
        ax.grid(True, alpha=0.3)
        self._apply_axis_limits(ax)
        self.panel.refresh()

    def _plot_capacity_single(self, fig, ax):
        rec = self.files[self.active_name]
        mass = rec.get("mass", 0.0)
        cycles = self._selected_cycles(rec)
        full = rec["cycle_list"]

        sub = rec["df_raw"][rec["df_raw"]["cycle"].isin(cycles)].copy()
        if len(sub) == 0:
            self._status("No data for selected cycles")
            return
        cap = phase_classifier.calculate_capacity(sub, mass)
        x_col = "specific_capacity" if mass > 0 else "capacity_mAh"
        self._stash_capacity_export(cap)

        # Blue for charge / red for discharge, darker as the cycle number rises.
        cmap_c = plt.colormaps["Blues"]
        cmap_d = plt.colormaps["Reds"]
        lo, hi = (min(full), max(full)) if full else (0, 0)
        span = (hi - lo) or 1

        def shade(cmap, cyc):
            return cmap(0.4 + 0.6 * (cyc - lo) / span)

        drawn = []
        for cyc in cycles:
            cd = cap[cap["cycle"] == cyc]
            if len(cd) == 0:
                continue
            charge = cd[cd["cycle_phase"] == "charge"]
            discharge = cd[cd["cycle_phase"] == "discharge"]
            if not charge.empty:
                ax.plot(charge[x_col], charge["E/V"], "-o", color=shade(cmap_c, cyc),
                        linewidth=1.5, alpha=0.85, markersize=2)
            if not discharge.empty:
                ax.plot(discharge[x_col], discharge["E/V"], "-o", color=shade(cmap_d, cyc),
                        linewidth=1.5, alpha=0.85, markersize=2)
            drawn.append(cyc)

        ax.set_xlabel("Specific capacity (mAh/g)" if mass > 0 else "Capacity (mAh)")
        if len(drawn) > 10:
            # Many cycles: two colormap legends (Blues = charge, Reds = discharge),
            # each reading the cycle number.
            from matplotlib.cm import ScalarMappable
            from matplotlib.colors import Normalize
            norm = Normalize(vmin=lo, vmax=hi)
            sm_c = ScalarMappable(cmap=_truncate_cmap(cmap_c), norm=norm)
            sm_c.set_array([])
            sm_d = ScalarMappable(cmap=_truncate_cmap(cmap_d), norm=norm)
            sm_d.set_array([])
            cb_c = fig.colorbar(sm_c, ax=ax, pad=0.02, fraction=0.05)
            cb_c.set_label("Charge – cycle", rotation=270, labelpad=14)
            cb_d = fig.colorbar(sm_d, ax=ax, pad=0.10, fraction=0.05)
            cb_d.set_label("Discharge – cycle", rotation=270, labelpad=14)
        elif drawn:
            # <= 10 cycles: a normal legend, one row per cycle showing its
            # charge (blue) + discharge (red) swatches side by side.
            from matplotlib.legend_handler import HandlerTuple
            handles = [(Line2D([0], [0], color=shade(cmap_c, c), marker="o", linewidth=1.5, markersize=4),
                        Line2D([0], [0], color=shade(cmap_d, c), marker="o", linewidth=1.5, markersize=4))
                       for c in drawn]
            labels = [f"Cycle {c}" for c in drawn]
            leg = ax.legend(handles, labels, handler_map={tuple: HandlerTuple(ndivide=None)},
                            loc="best", fontsize=9)
            if leg is not None:
                leg.set_draggable(True)
        ctype = "specific capacity" if mass > 0 else "capacity"
        self._status(f"Capacity ({ctype}) - {self.active_name}")

    def _plot_capacity_overlay(self, fig, ax):
        any_specific = False
        export_frames = []
        for i, (name, rec) in enumerate(self.files.items()):
            color = FILE_PALETTE[i % len(FILE_PALETTE)]
            mass = rec.get("mass", 0.0)
            any_specific = any_specific or (mass > 0)
            cap = phase_classifier.calculate_capacity(rec["df_raw"].copy(), mass)
            export_frames.append(self._cap_export_cols(cap, file_name=name))
            x_col = "specific_capacity" if mass > 0 else "capacity_mAh"
            for j, cyc in enumerate(rec["cycle_list"]):
                cd = cap[cap["cycle"] == cyc]
                if len(cd) == 0:
                    continue
                charge = cd[cd["cycle_phase"] == "charge"]
                discharge = cd[cd["cycle_phase"] == "discharge"]
                label = name if j == 0 else "_nolegend_"
                if not charge.empty:
                    ax.plot(charge[x_col], charge["E/V"], "-", color=color, label=label,
                            linewidth=1.2, alpha=0.7)
                    label = "_nolegend_"
                if not discharge.empty:
                    ax.plot(discharge[x_col], discharge["E/V"], "-", color=color, label=label,
                            linewidth=1.2, alpha=0.7)
        ax.set_xlabel("Specific capacity (mAh/g)" if any_specific else "Capacity (mAh)")
        self._capacity_export_df = pd.concat(export_frames, ignore_index=True) if export_frames else None
        leg = ax.legend(loc="best", fontsize=8)
        if leg is not None:
            leg.set_draggable(True)
        self._status(f"Capacity overlay: {len(self.files)} files")
