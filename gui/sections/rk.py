#!/usr/bin/env python3
"""R & k analysis section for the new pyICI GUI.

Adapted from the original Tab 5 (Resistance Analysis). For the selected cycles and
phase it plots internal resistance R and diffusion resistance k against voltage
(or capacity / specific capacity), with 1σ error bars, coloured by cycle.

Reuses the analysis layer unchanged: analysis.rk_analyzer.compute_R_k_for_cycles
runs the full ICI pipeline. The per-pulse regression windows you Saved in the
Regression section are bridged in here as `saved_params` (pulse > cycle > all-cycles
precedence), so hand-tuned fits drive R and k; untuned pulses use the default window.
"""
import os
import tkinter as tk
from tkinter import filedialog

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import customtkinter as ctk

from gui import theme
from gui.components.plot_panel import PlotPanel
from gui.components.export_helper import export_figure
from gui.components.scroll import AutoHideScrollableFrame
import analysis.regression_analyzer as ra
import analysis.rk_analyzer as ka

CHARGE = "charge"
DISCHARGE = "discharge"
C_CHARGE = "#1f77b4"
C_DISCHARGE = "#d62728"

# One colour per file for the overlay comparison view.
FILE_PALETTE = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e",
                "#17becf", "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22"]

TIME_START, TIME_END = ra.DEFAULT_TIME_START, ra.DEFAULT_TIME_END   # 0.1, 1.0 s

# X-axis label -> (result key, axis label)
XAXES = {
    "Voltage (V)": ("voltages", "Voltage (V)"),
    "Capacity (mAh)": ("capacity", "Capacity (mAh)"),
    "Specific capacity (mAh/g)": ("specific_capacity", "Specific capacity (mAh/g)"),
}


class RkSection(ctk.CTkFrame):
    """Left controls + right R/k plots."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self.df_raw = None
        self.cycle_list = []
        self.mass = 0.0
        self.phase = CHARGE
        self.sel_file = None          # the file this tab analyzes (independent per tab)
        self._results = None          # list of per-cycle R/k dicts
        self._results_other = None    # the other phase, when "Include ..." is checked

        self.file_var = tk.StringVar(value="")
        self.phase_var = tk.StringVar(value="Charge")
        self.include_other_var = tk.BooleanVar(value=False)
        self.cycle_text_var = tk.StringVar(value="")
        self.xaxis_var = tk.StringVar(value="Voltage (V)")
        self.overlay_var = tk.BooleanVar(value=False)
        self._overlay = None          # {fname: results_list} when overlay is on

        self.xmin_var = tk.StringVar(value="")
        self.xmax_var = tk.StringVar(value="")
        self.rmin_var = tk.StringVar(value="")
        self.rmax_var = tk.StringVar(value="")
        self.kmin_var = tk.StringVar(value="")
        self.kmax_var = tk.StringVar(value="")

        self.fig_w_var = tk.StringVar(value="8")
        self.fig_h_var = tk.StringVar(value="9")
        self.dpi_var = tk.StringVar(value="300")
        self.fmt_var = tk.StringVar(value="png")
        self.export_what_var = tk.StringVar(value="Both")
        self._settings_open = False

        self._build()

    # ---- layout -----------------------------------------------------------
    def _build(self):
        card, outer = theme.card(self, "R & k analysis - controls", width=theme.CONTROL_W)
        card.pack(side="left", fill="y", padx=(0, theme.GAP))
        card.pack_propagate(False)
        body = AutoHideScrollableFrame(outer, fg_color="transparent")    # auto-hide bar
        body.pack(fill="both", expand=True, padx=(2, 12))                # breathing room

        def slabel(text, pady=(0, 2)):                                   # #1 bold/dark labels
            ctk.CTkLabel(body, text=text, font=theme.font_sans(13, "bold"),
                         text_color=theme.TEXT, anchor="w").pack(fill="x", pady=pady)

        def teal_combo(variable, values, command):                      # #1 shared dropdown style
            return ctk.CTkComboBox(
                body, variable=variable, values=values, state="readonly", command=command,
                fg_color=theme.ACCENT, text_color="#ffffff",
                border_color=theme.ACCENT_HOVER, border_width=1,
                button_color=theme.ACCENT_HOVER, button_hover_color=theme.ACCENT,
                font=theme.font_sans(13), dropdown_font=theme.font_sans(13),
                dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
                dropdown_hover_color=theme.ACCENT_TINT)

        # File selector (teal dropdown, same as Data loading / Pulse check)
        slabel("File")
        self.file_menu = teal_combo(self.file_var, ["(no files)"], self._on_file_change)
        self.file_menu.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(body, text="(files are loaded in Data loading)",
                     font=theme.font_sans(12), text_color=theme.MUTED,   # #2 darker, readable
                     anchor="w").pack(fill="x", pady=(0, 2))

        # Phase toggle
        slabel("Phase", pady=(10, 2))
        self.phase_seg = ctk.CTkSegmentedButton(
            body, values=["Charge", "Discharge"], variable=self.phase_var,
            command=self._on_phase, font=theme.font_sans(13, "bold"),
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.MUTED, unselected_hover_color=theme.TEXT,
            text_color="#ffffff")       # #1 white text, legible on both segments
        self.phase_seg.pack(fill="x")
        self.include_chk = ctk.CTkCheckBox(
            body, text="Include discharge", variable=self.include_other_var,
            command=self._compute_and_plot, font=theme.font_sans(12),
            checkbox_width=18, checkbox_height=18,
            fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER)
        self.include_chk.pack(fill="x", pady=(4, 0))

        # Cycles
        slabel("Cycles", pady=(12, 2))
        ctk.CTkLabel(body, text="blank = all,  e.g. 1,3,5  or  1-5",
                     font=theme.font_sans(12), text_color=theme.MUTED,   # #2 bigger + darker
                     anchor="w").pack(fill="x", pady=(0, 2))
        self.cycle_entry = ctk.CTkEntry(body, textvariable=self.cycle_text_var,
                                        font=theme.font_sans(13), corner_radius=theme.RADIUS_INPUT)
        self.cycle_entry.pack(fill="x")
        self.cycle_entry.bind("<Return>", lambda e: self._compute_and_plot())
        self.cycle_hint = ctk.CTkLabel(body, text="", font=theme.font_sans(12),
                                       text_color=theme.MUTED, anchor="w")   # #2
        self.cycle_hint.pack(fill="x")

        # X-axis
        slabel("X-axis", pady=(10, 2))
        self.xaxis_menu = teal_combo(self.xaxis_var, list(XAXES.keys()),
                                     lambda _c: self._plot())
        self.xaxis_menu.pack(fill="x")

        ctk.CTkCheckBox(body, text="Overlay all files (compare)", variable=self.overlay_var,
                        command=self._compute_and_plot, font=theme.font_sans(13),
                        text_color=theme.TEXT, fg_color=theme.ACCENT,
                        hover_color=theme.ACCENT_HOVER).pack(anchor="w", pady=(10, 0))

        ctk.CTkButton(body, text="Plot R & k", command=self._compute_and_plot,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(13, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(fill="x", pady=(10, 0))

        # Axis limits
        ctk.CTkLabel(body, text="Axis limits  (blank = auto)", font=theme.font_sans(12, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(fill="x", pady=(14, 2))
        self._limit_row(body, "X", self.xmin_var, self.xmax_var)
        self._limit_row(body, "R", self.rmin_var, self.rmax_var)
        self._limit_row(body, "k", self.kmin_var, self.kmax_var)
        lim_btns = ctk.CTkFrame(body, fg_color="transparent")
        lim_btns.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(lim_btns, text="Apply", command=self._plot, height=30,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ctk.CTkButton(lim_btns, text="Auto", command=self._auto_limits, height=30,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
                      corner_radius=theme.RADIUS_INPUT).pack(side="left", fill="x", expand=True,
                                                             padx=(3, 0))

        self.info = ctk.CTkLabel(body, text="", font=theme.font_mono(12), text_color=theme.MUTED,
                                 anchor="w", justify="left", wraplength=320)
        self.info.pack(fill="x", pady=(10, 0))

        # Collapsible export panel
        self.adv_toggle = ctk.CTkButton(
            body, text="⚙  Export settings   +", anchor="w", height=30,
            command=self._toggle_settings, fg_color=theme.BG, text_color=theme.MUTED,
            hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
            corner_radius=theme.RADIUS_INPUT)
        self.adv_toggle.pack(fill="x", pady=(12, 0))
        self.settings_frame = ctk.CTkFrame(body, fg_color=theme.BG, corner_radius=theme.RADIUS_INPUT)
        self._build_settings(self.settings_frame)

        # CSV data export (of the displayed phase)
        self.csv_btn = ctk.CTkButton(body, text="Export charge CSV", command=self._export_csv,
                                     fg_color=theme.SURFACE, text_color=theme.ACCENT,
                                     border_color=theme.ACCENT, border_width=1,
                                     hover_color=theme.ACCENT_TINT, font=theme.font_sans(13),
                                     corner_radius=theme.RADIUS_INPUT)
        self.csv_btn.pack(fill="x", pady=(8, 0))
        self._update_csv_button()

        # Plots
        plot_card, plot_body = theme.card(self, "R & k analysis - plots")
        plot_card.pack(side="left", fill="both", expand=True)
        self.panel = PlotPanel(plot_body, figsize=(8, 9))
        self.panel.pack(fill="both", expand=True)

    def _limit_row(self, parent, label, lo_var, hi_var):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=1)
        ctk.CTkLabel(r, text=label, font=theme.font_sans(12), text_color=theme.MUTED,
                     width=16).pack(side="left")
        ctk.CTkEntry(r, textvariable=lo_var, placeholder_text="min", width=80,
                     font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT
                     ).pack(side="left", padx=(4, 6))
        ctk.CTkEntry(r, textvariable=hi_var, placeholder_text="max", width=80,
                     font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT).pack(side="left")

    def _build_settings(self, parent):
        pad = 8
        size_row = ctk.CTkFrame(parent, fg_color="transparent")
        size_row.pack(fill="x", padx=pad, pady=(pad, 1))
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

        what_row = ctk.CTkFrame(parent, fg_color="transparent")
        what_row.pack(fill="x", padx=pad, pady=1)
        ctk.CTkLabel(what_row, text="Plots", font=theme.font_sans(12),
                     text_color=theme.MUTED, width=62, anchor="w").pack(side="left")
        ctk.CTkOptionMenu(what_row, variable=self.export_what_var,
                          values=["Both", "R only", "k only"], width=140,
                          fg_color=theme.SURFACE, text_color=theme.TEXT, button_color=theme.ACCENT,
                          button_hover_color=theme.ACCENT_HOVER, font=theme.font_sans(12),
                          dropdown_font=theme.font_sans(12)).pack(side="left")

        ctk.CTkButton(parent, text="Export figure", command=self._export,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(13, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(fill="x", padx=pad, pady=(6, pad))

    def _toggle_settings(self):
        self._settings_open = not self._settings_open
        if self._settings_open:
            self.settings_frame.pack(fill="x", pady=(6, 0))
            self.adv_toggle.configure(text="⚙  Export settings   –")
        else:
            self.settings_frame.pack_forget()
            self.adv_toggle.configure(text="⚙  Export settings   +")

    # ---- shared-data access ----------------------------------------------
    def _status(self, msg):
        try:
            self.app.set_status(msg)
        except Exception:
            pass

    def on_show(self):
        self._refresh_from_data()

    def _files(self):
        return getattr(self.app.section_frames.get("data"), "files", {})

    def _refresh_from_data(self):
        ds = self.app.section_frames.get("data")
        files = self._files()
        names = list(files.keys())
        self.file_menu.configure(values=names or ["(no files)"])
        if not names:
            self.df_raw = None
            self.cycle_list = []
            self._results = None
            self.sel_file = None
            self.file_var.set("")
            self.cycle_hint.configure(text="")
            self.info.configure(text="Load a file in the Data loading section first.")
            self._clear_plot()
            return
        if self.sel_file not in files:
            self.sel_file = getattr(ds, "active_name", None) or names[0]
        self.file_var.set(self.sel_file)
        rec = files[self.sel_file]
        self.df_raw = rec["df_raw"]
        self.cycle_list = list(rec["cycle_list"])
        self.mass = float(rec.get("mass", 0.0) or 0.0)
        self.cycle_hint.configure(
            text=f"available: {min(self.cycle_list)}–{max(self.cycle_list)} "
                 f"({len(self.cycle_list)})" if self.cycle_list else "")
        self._compute_and_plot()

    def _on_file_change(self, name):
        if name not in self._files():
            return
        self.sel_file = name
        self._refresh_from_data()

    def _on_phase(self, _value=None):
        self.phase = CHARGE if self.phase_var.get() == "Charge" else DISCHARGE
        self._update_csv_button()
        self.include_chk.configure(
            text="Include charge" if self.phase == DISCHARGE else "Include discharge")
        self._compute_and_plot()

    def _update_csv_button(self):
        self.csv_btn.configure(text=f"Export {self.phase} CSV")

    def _auto_limits(self):
        for v in (self.xmin_var, self.xmax_var, self.rmin_var, self.rmax_var,
                  self.kmin_var, self.kmax_var):
            v.set("")
        self._plot()

    def _selected_cycles(self):
        cycles = ka.parse_cycle_input(self.cycle_text_var.get(), self.cycle_list)
        return cycles if cycles else self.cycle_list

    # ---- regression-window bridge ----------------------------------------
    def _regression_windows(self, df_raw, cycles, phase, fname):
        """Build (default_window, saved_params) from file ``fname``'s saved
        regression windows, honouring pulse > cycle > all-cycles precedence.
        all-cycles maps to the default window; cycle-scope expands to that cycle's
        pulses; pulse-scope overrides. Untuned pulses fall back to time 0.1-1.0 s."""
        reg = self.app.section_frames.get("regression")
        if reg is not None and hasattr(reg, "saved_windows_for"):
            saved = reg.saved_windows_for(fname)
        else:
            saved = {}
        default = ("time", TIME_START, TIME_END)
        if (phase,) in saved:
            default = saved[(phase,)]

        sel = set(cycles)
        saved_params = {}

        def spec_dict(spec):
            return {"mode": spec[0], "start": spec[1], "end": spec[2]}

        for key, spec in saved.items():            # cycle-scope -> expand to pulses
            if len(key) == 2 and key[1] == phase and key[0] in sel:
                cyc = key[0]
                reg_cyc = ra.load_cycle_for_regression(df_raw, cyc)
                if reg_cyc is None:
                    continue
                pulses = reg_cyc.charge_pulses if phase == CHARGE else reg_cyc.discharge_pulses
                for p in pulses:
                    saved_params[f"{cyc}_{phase}_{p}"] = spec_dict(spec)
        for key, spec in saved.items():            # pulse-scope -> overrides
            if len(key) == 3 and key[1] == phase and key[0] in sel:
                cyc, _, p = key
                saved_params[f"{cyc}_{phase}_{p}"] = spec_dict(spec)

        return default, saved_params

    def _rk_for_file(self, fname, rec, phase):
        """Compute the per-cycle R/k list for one file, with its own cycles/mass/windows."""
        df = rec["df_raw"]
        mass = float(rec.get("mass", 0.0) or 0.0)
        cyc_list = list(rec["cycle_list"])
        cycles = ka.parse_cycle_input(self.cycle_text_var.get(), cyc_list) or cyc_list
        default, sp = self._regression_windows(df, cycles, phase, fname)
        return ka.compute_R_k_for_cycles(df, cycles, phase, default[0], default[1],
                                         default[2], sp, mass)

    # ---- compute + plot ---------------------------------------------------
    def _compute_and_plot(self):
        files = self._files()
        if not files:
            self._status("Load a file first")
            return

        if self.overlay_var.get() and len(files) > 1:
            self._status(f"Computing R & k ({self.phase}) for {len(files)} files…")
            self._overlay = {}
            for fname, rec in files.items():
                self._overlay[fname] = self._rk_for_file(fname, rec, self.phase)
            self._results = None
            self._results_other = None
            npts = sum(sum(len(r["pulse_nums"]) for r in res)
                       for res in self._overlay.values())
            self.info.configure(text=f"Overlay: {len(files)} files, {npts} pulses")
            self._status(f"R & k overlay: {len(files)} files")
            self._plot()
            return

        self._overlay = None
        if self.df_raw is None or not self.cycle_list:
            self._status("Load a file first")
            return
        cycles = self._selected_cycles()
        x_key, _ = XAXES[self.xaxis_var.get()]
        if x_key == "specific_capacity" and self.mass <= 0:
            self._status("Set a mass (>0) in Data loading for specific capacity")
        self._status(f"Computing R & k ({self.phase}) for {len(cycles)} cycle(s)…")
        default, saved_params = self._regression_windows(self.df_raw, cycles, self.phase,
                                                         self.sel_file)
        self._results = ka.compute_R_k_for_cycles(
            self.df_raw, cycles, self.phase, default[0], default[1], default[2],
            saved_params, self.mass)
        if self.include_other_var.get():
            other = DISCHARGE if self.phase == CHARGE else CHARGE
            d2, sp2 = self._regression_windows(self.df_raw, cycles, other, self.sel_file)
            self._results_other = ka.compute_R_k_for_cycles(
                self.df_raw, cycles, other, d2[0], d2[1], d2[2], sp2, self.mass)
        else:
            self._results_other = None
        n_pulses = sum(len(r["pulse_nums"]) for r in self._results) if self._results else 0
        n_tuned = len(saved_params)
        self.info.configure(
            text=f"{len(self._results or [])} cycle(s), {n_pulses} pulses"
                 + (f"\n{n_tuned} pulse(s) use saved windows" if n_tuned else
                    "\nall pulses use the default window"))
        self._status(f"R & k ready: {len(self._results or [])} cycle(s), {n_pulses} pulses")
        self._plot()

    def _clear_plot(self):
        self.panel.figure.clear()
        self.panel.refresh()

    def _phase_cmap(self):
        return plt.colormaps["Blues" if self.phase == CHARGE else "Reds"]

    def _cycle_span(self):
        """Min/max cycle used to normalise the colour gradient - the FULL cycle
        list of the file, so a given cycle is the same shade here as in the
        Capacity and Regression plots regardless of which cycles are plotted."""
        full = self.cycle_list or []
        return (min(full), max(full)) if full else (0, 0)

    def _colors_for(self, cycles, phase):
        """Blue (charge) / red (discharge), darkening with cycle number."""
        cmap = plt.colormaps["Blues" if phase == CHARGE else "Reds"]
        lo, hi = self._cycle_span()
        span = (hi - lo) or 1
        return {c: cmap(0.4 + 0.6 * (c - lo) / span) for c in cycles}

    def _cycle_colors(self, cycles):
        return self._colors_for(cycles, self.phase), len(cycles) > 10

    def _draw_rk(self, ax_R, ax_k, results, phase, x_key, label_mode):
        """Draw one phase's R and k (label_mode: 'none' | 'cycle' | 'phase')."""
        colors = self._colors_for([r["cycle"] for r in results], phase)
        for r in results:
            cyc = r["cycle"]
            x = np.asarray(r[x_key], dtype=float)
            if label_mode == "cycle":
                label = f"Cycle {cyc}"
            elif label_mode == "phase":
                label = f"{phase} cyc {cyc}"
            else:
                label = None
            ax_R.errorbar(x, r["R"], yerr=r["R_err"], fmt="o-", color=colors[cyc], markersize=4,
                          linewidth=1.2, capsize=2, alpha=0.85, label=label)
            ax_k.errorbar(x, r["k"], yerr=r["k_err"], fmt="o-", color=colors[cyc], markersize=4,
                          linewidth=1.2, capsize=2, alpha=0.85)

    def _apply_limits(self, ax_R, ax_k):
        def _val(var):
            s = var.get().strip()
            try:
                return float(s) if s else None
            except ValueError:
                return None
        xlo, xhi = _val(self.xmin_var), _val(self.xmax_var)
        rlo, rhi = _val(self.rmin_var), _val(self.rmax_var)
        klo, khi = _val(self.kmin_var), _val(self.kmax_var)
        if xlo is not None or xhi is not None:
            ax_R.set_xlim(left=xlo, right=xhi)
            ax_k.set_xlim(left=xlo, right=xhi)
        if rlo is not None or rhi is not None:
            ax_R.set_ylim(bottom=rlo, top=rhi)
        if klo is not None or khi is not None:
            ax_k.set_ylim(bottom=klo, top=khi)

    def _plot(self):
        fig = self.panel.figure
        fig.clear()
        if self._overlay is not None:
            self._plot_overlay(fig)
            return
        if not self._results:
            if self.df_raw is not None:
                ax = fig.add_subplot(111)
                ax.text(0.5, 0.5, f"No {self.phase} R/k for the selected cycles",
                        ha="center", va="center", transform=ax.transAxes, color=theme.MUTED)
                ax.set_xticks([])
                ax.set_yticks([])
            self.panel.refresh()
            return

        ax_R = fig.add_subplot(211)
        ax_k = fig.add_subplot(212, sharex=ax_R)
        x_key, x_label = XAXES[self.xaxis_var.get()]
        both = self._results_other is not None
        cycles = [r["cycle"] for r in self._results]
        use_cbar = (not both) and len(cycles) > 10

        if both:
            other = DISCHARGE if self.phase == CHARGE else CHARGE
            self._draw_rk(ax_R, ax_k, self._results, self.phase, x_key, "phase")
            self._draw_rk(ax_R, ax_k, self._results_other, other, x_key, "phase")
        else:
            self._draw_rk(ax_R, ax_k, self._results, self.phase, x_key,
                          "none" if use_cbar else "cycle")

        title = "charge & discharge" if both else self.phase
        ax_R.set_ylabel("R (Ω)", fontsize=12)
        ax_R.set_xlabel(x_label, fontsize=12)
        ax_R.tick_params(labelbottom=True)     # keep x tick labels on the top plot too
        ax_R.set_title(f"{title.capitalize()} — internal resistance R",
                       fontsize=11, fontweight="bold")
        ax_R.grid(True, alpha=0.3)
        ax_k.set_ylabel("k (Ω·s$^{-1/2}$)", fontsize=12)
        ax_k.set_xlabel(x_label, fontsize=12)
        ax_k.set_title(f"{title.capitalize()} — diffusion resistance k",
                       fontsize=11, fontweight="bold")
        ax_k.grid(True, alpha=0.3)

        self._apply_limits(ax_R, ax_k)

        if use_cbar:
            from matplotlib.cm import ScalarMappable
            from matplotlib.colors import Normalize
            sm = ScalarMappable(cmap=self._phase_cmap(),
                                norm=Normalize(vmin=self._cycle_span()[0], vmax=self._cycle_span()[1]))
            sm.set_array([])
            cbar = fig.colorbar(sm, ax=[ax_R, ax_k], pad=0.02, fraction=0.046)
            cbar.set_label("Cycle number", rotation=270, labelpad=15)
        else:
            _h, _labels = ax_R.get_legend_handles_labels()
            if _labels:
                leg = ax_R.legend(loc="best", fontsize=8, ncol=2 if both else 1)
                if leg is not None:
                    leg.set_draggable(True)
        self.panel.refresh()

    def _plot_overlay(self, fig):
        """One color per file, all cycles' R/k pooled - for comparing files."""
        ax_R = fig.add_subplot(211)
        ax_k = fig.add_subplot(212, sharex=ax_R)
        x_key, x_label = XAXES[self.xaxis_var.get()]
        for i, (fname, results) in enumerate(self._overlay.items()):
            color = FILE_PALETTE[i % len(FILE_PALETTE)]
            first = True
            for r in results:                        # one clean line per cycle, file's colour
                x = np.asarray(r[x_key], dtype=float)
                if len(x) == 0:
                    continue
                ax_R.errorbar(x, r["R"], yerr=r["R_err"], fmt="o-", color=color, markersize=4,
                              linewidth=1.2, capsize=2, alpha=0.8,
                              label=fname if first else "_nolegend_")
                ax_k.errorbar(x, r["k"], yerr=r["k_err"], fmt="o-", color=color, markersize=4,
                              linewidth=1.2, capsize=2, alpha=0.8)
                first = False
        ax_R.set_ylabel("R (Ω)", fontsize=12)
        ax_R.set_xlabel(x_label, fontsize=12)
        ax_R.tick_params(labelbottom=True)
        ax_R.set_title(f"{self.phase.capitalize()} — R (file overlay)",
                       fontsize=11, fontweight="bold")
        ax_R.grid(True, alpha=0.3)
        ax_k.set_ylabel("k (Ω·s$^{-1/2}$)", fontsize=12)
        ax_k.set_xlabel(x_label, fontsize=12)
        ax_k.set_title(f"{self.phase.capitalize()} — k (file overlay)",
                       fontsize=11, fontweight="bold")
        ax_k.grid(True, alpha=0.3)
        self._apply_limits(ax_R, ax_k)
        leg = ax_R.legend(loc="best", fontsize=8)
        if leg is not None:
            leg.set_draggable(True)
        self.panel.refresh()

    # ---- export -----------------------------------------------------------
    def _export(self):
        if not self._results and not self._overlay:
            self._status("Nothing to export - plot R & k first")
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
        what = self.export_what_var.get()           # "Both" | "R only" | "k only"
        suffix = {"Both": "Rk", "R only": "R", "k only": "k"}[what]
        stem = "pyICI_overlay" if self._overlay else os.path.splitext(self.sel_file or "pyICI_rk")[0]
        path = filedialog.asksaveasfilename(
            title="Export R & k figure", defaultextension=f".{fmt}",
            initialfile=f"{stem}_{self.phase}_{suffix}.{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")])
        if not path:
            return
        try:
            if what == "Both":
                export_figure(self.panel.figure, path, width_in=w, height_in=h, dpi=dpi)
            else:
                self._export_single("R" if what == "R only" else "k", path, w, h, dpi)
        except Exception as exc:
            self._status(f"Export failed: {exc}")
            return
        self._status(f"Exported {what} → {os.path.basename(path)}  "
                     f"({w:g}×{h:g} in, {dpi} dpi)")

    def _export_csv(self):
        """Write the displayed phase's R/k results to a CSV with the same columns
        as the old GUI's per-phase export (shared schema: ka.rk_result_rows). In
        overlay mode every file is written, with a leading File column."""
        rows = []
        if self._overlay:
            for fname, results in self._overlay.items():
                for res in results:
                    for row in ka.rk_result_rows(res, res["cycle"]):
                        rows.append({"File": fname, **row})
            stem = "pyICI_overlay"
        elif self._results:
            for res in self._results:
                rows.extend(ka.rk_result_rows(res, res["cycle"]))
            stem = os.path.splitext(self.sel_file or "pyICI")[0]
        else:
            self._status("Nothing to export - plot R & k first")
            return
        if not rows:
            self._status("No pulses to export")
            return
        path = filedialog.asksaveasfilename(
            title=f"Export {self.phase} R/k data", defaultextension=".csv",
            initialfile=f"{stem}_R_k_results_{self.phase}.csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")])
        if not path:
            return
        try:
            pd.DataFrame(rows).to_csv(path, index=False)
        except Exception as exc:
            self._status(f"CSV export failed: {exc}")
            return
        self._status(f"Exported {len(rows)} rows → {os.path.basename(path)}")

    def _export_single(self, which, path, w, h, dpi):
        """Render just the R or the k plot (error bars included) to a standalone
        figure and save it, honouring the x and R/k axis limits."""
        x_key, x_label = XAXES[self.xaxis_var.get()]
        fig, ax = plt.subplots(figsize=(w, h))
        use_cbar = False
        try:
            if self._overlay:
                for i, (fname, results) in enumerate(self._overlay.items()):
                    color = FILE_PALETTE[i % len(FILE_PALETTE)]
                    first = True
                    for r in results:
                        x = np.asarray(r[x_key], dtype=float)
                        if len(x) == 0:
                            continue
                        ax.errorbar(x, r[which], yerr=r[which + "_err"], fmt="o-",
                                    color=color, markersize=4, linewidth=1.2, capsize=2,
                                    alpha=0.8, label=fname if first else "_nolegend_")
                        first = False
            else:
                cycles = [r["cycle"] for r in self._results]
                colors, use_cbar = self._cycle_colors(cycles)
                for r in self._results:
                    x = np.asarray(r[x_key], dtype=float)
                    ax.errorbar(x, r[which], yerr=r[which + "_err"], fmt="o-",
                                color=colors[r["cycle"]], markersize=4, linewidth=1.2,
                                capsize=2, alpha=0.85,
                                label=None if use_cbar else f"Cycle {r['cycle']}")
            ax.set_xlabel(x_label, fontsize=12)
            ax.set_ylabel("R (Ω)" if which == "R" else "k (Ω·s$^{-1/2}$)",
                          fontsize=12)
            ax.grid(True, alpha=0.3)

            def _val(var):
                s = var.get().strip()
                try:
                    return float(s) if s else None
                except ValueError:
                    return None
            xlo, xhi = _val(self.xmin_var), _val(self.xmax_var)
            if xlo is not None or xhi is not None:
                ax.set_xlim(left=xlo, right=xhi)
            ylo_var, yhi_var = ((self.rmin_var, self.rmax_var) if which == "R"
                                else (self.kmin_var, self.kmax_var))
            ylo, yhi = _val(ylo_var), _val(yhi_var)
            if ylo is not None or yhi is not None:
                ax.set_ylim(bottom=ylo, top=yhi)

            if use_cbar:
                from matplotlib.cm import ScalarMappable
                from matplotlib.colors import Normalize
                sm = ScalarMappable(cmap=self._phase_cmap(),
                                    norm=Normalize(vmin=self._cycle_span()[0], vmax=self._cycle_span()[1]))
                sm.set_array([])
                cbar = fig.colorbar(sm, ax=ax, pad=0.02, fraction=0.046)
                cbar.set_label("Cycle number", rotation=270, labelpad=15)
            else:
                ax.legend(loc="best", fontsize=8)
            fig.tight_layout()
            fig.savefig(path, dpi=dpi, bbox_inches="tight", facecolor="white")
        finally:
            plt.close(fig)
