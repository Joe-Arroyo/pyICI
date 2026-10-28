#!/usr/bin/env python3
"""Regression section for the new pyICI GUI.

Adapted from the original Tab 4 (Regression), re-laid out as controls-left /
plots-right.

For the selected cycle / phase / pulse it shows the per-pulse linear fit of
ΔV vs √t (with a secondary Time axis on top) with the chosen regression window
shaded and the fit line drawn over it; the lower plot tracks R² across the pulses
of the current cycle. "Overall check" shows R² of every pulse across every cycle
(the multicycle view: charge in Blues, discharge in Reds).

Regression windows are chosen per scope:
  * Apply -> pulse / cycle / all cycles  : PREVIEW the typed window at that scope.
    A preview is transient - moving to another cycle/pulse/phase clears it.
  * Save (beside each)                   : PERSIST that scope's window, so it
    survives navigation and feeds the R²/overall plots.
Resolution is most-specific-wins: pulse > cycle > all > the live entry values.

Reuses the analysis layer unchanged (analysis.regression_analyzer): resolve_window()
and compute_single_pulse_regression() are the SAME code the exported R/k use.
"""
import os
import tkinter as tk
from tkinter import filedialog

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import customtkinter as ctk

from gui import theme
from gui.components.plot_panel import PlotPanel
from gui.components.export_helper import export_figure
from gui.components.scroll import AutoHideScrollableFrame
import analysis.regression_analyzer as ra
import analysis.rk_analyzer as ka

CHARGE = "charge"
DISCHARGE = "discharge"

C_CHARGE = "#1f77b4"      # blue
C_DISCHARGE = "#d62728"   # red
C_FIT = "#15803d"         # green fit line
C_WINDOW = "#9aa7ae"      # grey window shading
C_REGPTS = "#e8820c"      # orange regression points

TIME_START, TIME_END = ra.DEFAULT_TIME_START, ra.DEFAULT_TIME_END      # 0.1, 1.0 s
INDEX_START, INDEX_END = ra.DEFAULT_INDEX_START, ra.DEFAULT_INDEX_END   # 2, 10 (1-based)

# Regression-window modes. The label shown in the dropdown IS the mode string
# passed to ra.resolve_window.
MODE_TIME, MODE_INDEX = "time", "index"
MODE_VALUES = [MODE_TIME, MODE_INDEX]


def _mode_defaults(mode):
    """(start, end) default bounds for a window mode."""
    if mode == MODE_TIME:
        return TIME_START, TIME_END
    return INDEX_START, INDEX_END


class RegressionSection(ctk.CTkFrame):
    """Left controls + right plots for per-pulse ΔV-vs-√t regression."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        self.df_raw = None
        self.cycle_list = []
        self.cycle_idx = 0
        self.phase = CHARGE
        self.reg = None            # CycleRegression for the current cycle
        self.pulse_list = []
        self.pulse_idx = 0
        self.sel_file = None       # the file this tab analyzes (independent per tab)
        self._overall = None       # {"charge":[(cyc,idx,r2)...], "discharge":[...]} when active

        # Per-scope regression windows. Keys: (cyc,phase,pulse) | (cyc,phase) | (phase,)
        # self.saved holds the CURRENT file's windows; saved_by_file keeps one such
        # dict per file so each file's hand-tuned fits persist independently.
        self.saved = {}            # persistent across navigation (current file)
        self.preview = {}          # transient; cleared on any navigation
        self.saved_by_file = {}    # fname -> saved dict

        self.file_var = tk.StringVar(value="")
        self.phase_var = tk.StringVar(value="Charge")
        self.mode_var = tk.StringVar(value="time")
        self.start_var = tk.StringVar(value=str(TIME_START))
        self.end_var = tk.StringVar(value=str(TIME_END))
        self.cycle_entry_var = tk.StringVar(value="")
        self.pulse_entry_var = tk.StringVar(value="")

        # R² plot axis limits (blank = auto). X is pulse # (cycle view) or cycle
        # number (overall view); Y is R².
        self.r2_xmin_var = tk.StringVar(value="")
        self.r2_xmax_var = tk.StringVar(value="")
        self.r2_ymin_var = tk.StringVar(value="")
        self.r2_ymax_var = tk.StringVar(value="")

        self.fig_w_var = tk.StringVar(value="10")
        self.fig_h_var = tk.StringVar(value="8")
        self.dpi_var = tk.StringVar(value="300")
        self.fmt_var = tk.StringVar(value="png")
        self._settings_open = False
        self._r2lim_open = False
        self._autoopts_open = False

        # Auto fit-window: a holding area for suggested per-pulse windows that
        # survives navigation until you Save (or Restore defaults).
        self.auto_windows = {}     # {(cyc,phase,pulse): (mode,start,end)} pending
        self.auto_flags = {}       # {(cyc,phase,pulse): [flags]} from the last Auto run
        self.fit_mode_var = tk.StringVar(value="Manual")
        self.auto_skip_var = tk.StringVar(value=str(ra.AUTO_SKIP_INITIAL))
        self.auto_minpts_var = tk.StringVar(value=str(ra.AUTO_MIN_POINTS))
        self.auto_adjr2_var = tk.StringVar(value=str(ra.AUTO_ADJ_R2_MIN))
        self.auto_edge_var = tk.StringVar(value=str(ra.AUTO_EDGE_POINTS))

        self._build()

    # ---- layout -----------------------------------------------------------
    def _build(self):
        card, outer = theme.card(self, "Regression - controls", width=theme.CONTROL_W)
        card.pack(side="left", fill="y", padx=(0, theme.GAP))
        card.pack_propagate(False)
        body = AutoHideScrollableFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=(2, 12))        # breathing room

        def slabel(text, pady=(0, 2)):                            # #1 bold/dark labels
            ctk.CTkLabel(body, text=text, font=theme.font_sans(13, "bold"),
                         text_color=theme.TEXT, anchor="w").pack(fill="x", pady=pady)

        # File selector (teal dropdown, same as Data loading / Pulse check)  # #1
        slabel("File")
        self.file_menu = ctk.CTkComboBox(
            body, variable=self.file_var, values=["(no files)"], state="readonly",
            command=self._on_file_change,
            fg_color=theme.ACCENT, text_color="#ffffff",
            border_color=theme.ACCENT_HOVER, border_width=1,
            button_color=theme.ACCENT_HOVER, button_hover_color=theme.ACCENT,
            font=theme.font_sans(13), dropdown_font=theme.font_sans(13),
            dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
            dropdown_hover_color=theme.ACCENT_TINT)
        self.file_menu.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(body, text="(files are loaded in Data loading)",
                     font=theme.font_sans(12), text_color=theme.MUTED,
                     anchor="w").pack(fill="x", pady=(0, 2))

        # Phase selector - below the file, above cycle            # #2
        slabel("Phase", pady=(10, 2))
        self.phase_seg = ctk.CTkSegmentedButton(
            body, values=["Charge", "Discharge"], variable=self.phase_var,
            command=self._on_phase, font=theme.font_sans(13, "bold"),
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.MUTED, unselected_hover_color=theme.TEXT,
            text_color="#ffffff")       # #1 white text, legible on both segments
        self.phase_seg.pack(fill="x")

        # Cycle entry
        slabel("Cycle", pady=(10, 2))
        cyc_row = ctk.CTkFrame(body, fg_color="transparent")
        cyc_row.pack(fill="x")
        self._arrow(cyc_row, "◀", self._prev_cycle).pack(side="left")
        self.cycle_entry = ctk.CTkEntry(cyc_row, textvariable=self.cycle_entry_var, width=64,
                                        font=theme.font_mono(13), corner_radius=theme.RADIUS_INPUT,
                                        justify="center")
        self.cycle_entry.pack(side="left", padx=4)
        self.cycle_entry.bind("<Return>", lambda e: self._go_cycle())
        self._arrow(cyc_row, "▶", self._next_cycle).pack(side="left")
        ctk.CTkButton(cyc_row, text="Go", command=self._go_cycle, width=48,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", padx=(6, 0))
        self.cycle_hint = ctk.CTkLabel(body, text="", font=theme.font_sans(12),
                                       text_color=theme.MUTED, anchor="w", justify="left",
                                       wraplength=320)
        self.cycle_hint.pack(fill="x")

        # Pulse entry
        slabel("Pulse", pady=(10, 2))
        pl_row = ctk.CTkFrame(body, fg_color="transparent")
        pl_row.pack(fill="x")
        self._arrow(pl_row, "◀", self._prev_pulse).pack(side="left")
        self.pulse_entry = ctk.CTkEntry(pl_row, textvariable=self.pulse_entry_var, width=64,
                                        font=theme.font_mono(13), corner_radius=theme.RADIUS_INPUT,
                                        justify="center")
        self.pulse_entry.pack(side="left", padx=4)
        self.pulse_entry.bind("<Return>", lambda e: self._go_pulse())
        self._arrow(pl_row, "▶", self._next_pulse).pack(side="left")
        ctk.CTkButton(pl_row, text="Go", command=self._go_pulse, width=48,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", padx=(6, 0))
        self.pulse_hint = ctk.CTkLabel(body, text="", font=theme.font_sans(12),
                                       text_color=theme.MUTED, anchor="w", justify="left",
                                       wraplength=320)
        self.pulse_hint.pack(fill="x")

        # Regression window (live values you type, then Apply/Save at a scope)
        slabel("Regression window", pady=(12, 2))
        self.mode_menu = ctk.CTkComboBox(
            body, variable=self.mode_var, values=MODE_VALUES, state="readonly",
            command=self._on_mode,
            fg_color=theme.ACCENT, text_color="#ffffff",
            border_color=theme.ACCENT_HOVER, border_width=1,
            button_color=theme.ACCENT_HOVER, button_hover_color=theme.ACCENT,
            font=theme.font_sans(13), dropdown_font=theme.font_sans(13),
            dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
            dropdown_hover_color=theme.ACCENT_TINT)
        self.mode_menu.pack(fill="x")
        win_row = ctk.CTkFrame(body, fg_color="transparent")
        win_row.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(win_row, text="start", font=theme.font_sans(12), text_color=theme.MUTED,
                     width=36, anchor="w").pack(side="left")
        self.start_entry = ctk.CTkEntry(win_row, textvariable=self.start_var, width=70,
                                        font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT)
        self.start_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(win_row, text="end", font=theme.font_sans(12), text_color=theme.MUTED,
                     width=28, anchor="w").pack(side="left")
        self.end_entry = ctk.CTkEntry(win_row, textvariable=self.end_var, width=70,
                                      font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT)
        self.end_entry.pack(side="left")
        self.start_entry.bind("<Return>", lambda e: self._apply_pulse())
        self.end_entry.bind("<Return>", lambda e: self._apply_pulse())
        self.win_units = ctk.CTkLabel(
            body, text="", font=theme.font_sans(12), text_color=theme.MUTED, anchor="w")
        self.win_units.pack(fill="x")
        self._update_units_hint()

        # Fit readout for the current pulse (window / slope / intercept / R² /
        # flags) - sits right under the window entry so the numbers update where
        # you type them when you Apply or navigate.
        self.info = ctk.CTkLabel(body, text="", font=theme.font_mono(12), text_color=theme.MUTED,
                                 anchor="w", justify="left", wraplength=320)
        self.info.pack(fill="x", pady=(8, 0))

        # Manual <-> Auto fit-window mode switch (swaps the controls below)
        slabel("Fit window", pady=(12, 2))
        self.fit_mode_seg = ctk.CTkSegmentedButton(
            body, values=["Manual", "Auto"], variable=self.fit_mode_var,
            command=self._on_fit_mode, font=theme.font_sans(13, "bold"),
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.MUTED, unselected_hover_color=theme.TEXT,
            text_color="#ffffff")
        self.fit_mode_seg.pack(fill="x", pady=(0, 4))

        self.mode_controls = ctk.CTkFrame(body, fg_color="transparent")
        self.mode_controls.pack(fill="x")

        # Manual and the COLLAPSED Auto view are pinned to the same height so
        # switching Manual <-> Auto causes no vertical jump; the auto options
        # expand BELOW this fixed block (pushing the lower controls down, as a
        # dropdown should). 3 Apply/Save rows of height 30 + 2px pad each = 102.
        mode_h = 102

        # Manual: type a window, Apply (preview) / Save (persist) at each scope.
        self.manual_frame = ctk.CTkFrame(self.mode_controls, fg_color="transparent", height=mode_h)
        self._apply_save_row(self.manual_frame, "Apply → pulse", self._apply_pulse, self._save_pulse)
        self._apply_save_row(self.manual_frame, "Apply → cycle", self._apply_cycle, self._save_cycle)
        self._apply_save_row(self.manual_frame, "Apply → all cycles", self._apply_all, self._save_all)
        self.manual_frame.pack_propagate(False)

        # Auto: entering Auto mode immediately fits the optimal window for every
        # pulse of every cycle. Save keeps them; the parameters live in a
        # collapsible panel below so the collapsed view matches Manual's height.
        self.auto_frame = ctk.CTkFrame(self.mode_controls, fg_color="transparent", height=mode_h)
        ctk.CTkLabel(self.auto_frame,
                     text="Auto-fits every pulse of every cycle. Review, then Save.",
                     font=theme.font_sans(11), text_color=theme.MUTED,
                     anchor="w", justify="left").pack(fill="x", pady=(0, 4))
        ctk.CTkButton(self.auto_frame, text="Save auto fit", command=self._save_auto,
                      height=30, fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(13, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(fill="x", pady=(0, 2))
        self.autoopts_toggle = ctk.CTkButton(
            self.auto_frame, text="⚙  Auto fit options   +", anchor="w", height=30,
            command=self._toggle_autoopts, fg_color=theme.BG, text_color=theme.MUTED,
            hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
            corner_radius=theme.RADIUS_INPUT)
        self.autoopts_toggle.pack(fill="x", pady=(2, 0))
        self.auto_frame.pack_propagate(False)

        # Options panel is a sibling in mode_controls (below auto_frame), so it
        # grows the layout only when expanded.
        self.autoopts_frame = ctk.CTkFrame(self.mode_controls, fg_color=theme.BG,
                                           corner_radius=theme.RADIUS_INPUT)
        self._build_auto_settings(self.autoopts_frame)

        self.manual_frame.pack(fill="x")   # Manual by default

        ctk.CTkButton(body, text="Restore defaults", command=self._restore_defaults, height=30,
                      fg_color=theme.SURFACE, text_color=theme.MUTED, border_color=theme.BORDER,
                      border_width=1, hover_color=theme.BG, font=theme.font_sans(13),  # #4 larger
                      corner_radius=theme.RADIUS_INPUT).pack(fill="x", pady=(6, 0))

        ctk.CTkButton(body, text="Overall check (R² all cycles)", command=self._overall_check,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT, font=theme.font_sans(13),
                      corner_radius=theme.RADIUS_INPUT).pack(fill="x", pady=(10, 0))

        # R² plot axis limits (collapsible, like Export settings - rarely needed)
        self.r2lim_toggle = ctk.CTkButton(
            body, text="⚙  R² axis limits   +", anchor="w", height=30,
            command=self._toggle_r2lim, fg_color=theme.BG, text_color=theme.MUTED,
            hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
            corner_radius=theme.RADIUS_INPUT)
        self.r2lim_toggle.pack(fill="x", pady=(14, 0))
        self.r2lim_frame = ctk.CTkFrame(body, fg_color=theme.BG, corner_radius=theme.RADIUS_INPUT)
        self._build_r2lim(self.r2lim_frame)

        # Collapsible export panel
        self.adv_toggle = ctk.CTkButton(
            body, text="⚙  Export settings   +", anchor="w", height=30,
            command=self._toggle_settings, fg_color=theme.BG, text_color=theme.MUTED,
            hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
            corner_radius=theme.RADIUS_INPUT)
        self.adv_toggle.pack(fill="x", pady=(12, 0))
        self.settings_frame = ctk.CTkFrame(body, fg_color=theme.BG, corner_radius=theme.RADIUS_INPUT)
        self._build_settings(self.settings_frame)

        # Plots
        plot_card, plot_body = theme.card(self, "Regression - plots")
        plot_card.pack(side="left", fill="both", expand=True)
        self.panel = PlotPanel(plot_body, figsize=(10, 8))
        self.panel.pack(fill="both", expand=True)

    def _arrow(self, parent, text, command):
        return ctk.CTkButton(parent, text=text, width=44, height=30, command=command,
                             fg_color=theme.SURFACE, text_color=theme.ACCENT,
                             border_color=theme.ACCENT, border_width=1,
                             hover_color=theme.ACCENT_TINT, font=theme.font_sans(13, "bold"),
                             corner_radius=theme.RADIUS_INPUT)

    def _apply_save_row(self, parent, label, apply_cmd, save_cmd):
        # Grid with two equal, uniform columns so every Apply button is the same
        # width and every Save button is the same width across all three rows
        # (pack+expand let the longest label - "all cycles" - stretch its row). #6
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=2)
        r.grid_columnconfigure(0, weight=1, uniform="applysave")
        r.grid_columnconfigure(1, weight=1, uniform="applysave")
        ctk.CTkButton(r, text=label, command=apply_cmd, height=30, width=0, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, font=theme.font_sans(12, "bold"),
                      corner_radius=theme.RADIUS_INPUT).grid(row=0, column=0, sticky="ew",
                                                             padx=(0, 3))
        ctk.CTkButton(r, text="Save", command=save_cmd, height=30, width=0,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
                      corner_radius=theme.RADIUS_INPUT).grid(row=0, column=1, sticky="ew",
                                                             padx=(3, 0))

    def _limit_row(self, parent, label, lo_var, hi_var):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=1)
        ctk.CTkLabel(r, text=label, font=theme.font_sans(12), text_color=theme.MUTED,
                     width=22, anchor="w").pack(side="left")
        ctk.CTkEntry(r, textvariable=lo_var, placeholder_text="min", width=80,
                     font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT
                     ).pack(side="left", padx=(4, 6))
        ctk.CTkEntry(r, textvariable=hi_var, placeholder_text="max", width=80,
                     font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT).pack(side="left")

    def _apply_r2_limits(self, ax):
        """Apply any user-set R²-plot axis limits to ``ax``; blank fields stay auto.
        Called at the end of both R² views (per-cycle and overall)."""
        def _val(var):
            s = var.get().strip()
            try:
                return float(s) if s else None
            except ValueError:
                return None
        xlo, xhi = _val(self.r2_xmin_var), _val(self.r2_xmax_var)
        ylo, yhi = _val(self.r2_ymin_var), _val(self.r2_ymax_var)
        if xlo is not None or xhi is not None:
            ax.set_xlim(left=xlo, right=xhi)
        if ylo is not None or yhi is not None:
            ax.set_ylim(bottom=ylo, top=yhi)

    def _r2_auto_limits(self):
        for v in (self.r2_xmin_var, self.r2_xmax_var, self.r2_ymin_var, self.r2_ymax_var):
            v.set("")
        self._plot()

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

    def _build_r2lim(self, parent):
        pad = 8
        ctk.CTkLabel(parent, text="R² plot axis limits  (blank = auto)",
                     font=theme.font_sans(12, "bold"), text_color=theme.TEXT,
                     anchor="w").pack(fill="x", padx=pad, pady=(pad, 2))
        self._limit_row(parent, "X", self.r2_xmin_var, self.r2_xmax_var)
        self._limit_row(parent, "R²", self.r2_ymin_var, self.r2_ymax_var)
        btns = ctk.CTkFrame(parent, fg_color="transparent")
        btns.pack(fill="x", padx=pad, pady=(4, pad))
        ctk.CTkButton(btns, text="Apply", command=self._plot, height=30,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", fill="x", expand=True, padx=(0, 3))
        ctk.CTkButton(btns, text="Auto", command=self._r2_auto_limits, height=30,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
                      corner_radius=theme.RADIUS_INPUT).pack(side="left", fill="x", expand=True,
                                                             padx=(3, 0))

    def _toggle_r2lim(self):
        self._r2lim_open = not self._r2lim_open
        if self._r2lim_open:
            # anchor just under its own toggle (Export settings is packed after it)
            self.r2lim_frame.pack(fill="x", pady=(6, 0), before=self.adv_toggle)
            self.r2lim_toggle.configure(text="⚙  R² axis limits   –")
        else:
            self.r2lim_frame.pack_forget()
            self.r2lim_toggle.configure(text="⚙  R² axis limits   +")

    # ---- shared-data access ----------------------------------------------
    def _status(self, msg):
        try:
            self.app.set_status(msg)
        except Exception:
            pass

    def _data_section(self):
        return self.app.section_frames.get("data")

    def on_show(self):
        self._refresh_from_data()

    def _files(self):
        return getattr(self._data_section(), "files", {})

    def _sync_saved(self):
        """Snapshot the current file's windows into the per-file store."""
        if self.sel_file is not None:
            self.saved_by_file[self.sel_file] = self.saved

    def _switch_file(self, name):
        """Store the current file's windows, load the target file's."""
        self._sync_saved()
        self.sel_file = name
        self.saved = self.saved_by_file.setdefault(name, {})
        self.preview.clear()
        self.auto_windows = {}
        self.auto_flags = {}

    def saved_windows_for(self, fname):
        """The saved (not preview) windows for a file - used by the R & k bridge."""
        self._sync_saved()
        return dict(self.saved_by_file.get(fname, {}))

    def _refresh_from_data(self):
        ds = self._data_section()
        files = self._files()
        names = list(files.keys())
        self.file_menu.configure(values=names or ["(no files)"])
        if not names:
            self.df_raw = None
            self.cycle_list = []
            self.reg = None
            self.pulse_list = []
            self.sel_file = None
            self.file_var.set("")
            self.cycle_hint.configure(text="")
            self.pulse_hint.configure(text="")
            self.info.configure(text="Load a file in the Data loading section first.")
            self._clear_plot()
            return

        if self.sel_file not in files:
            self._switch_file(getattr(ds, "active_name", None) or names[0])
            self.cycle_idx = 0
        self.file_var.set(self.sel_file)
        rec = files[self.sel_file]
        self.df_raw = rec["df_raw"]
        self.cycle_list = list(rec["cycle_list"])
        if self.cycle_idx >= len(self.cycle_list):
            self.cycle_idx = 0
        self._load_current_cycle()

    def _on_file_change(self, name):
        if name not in self._files():
            return
        self._switch_file(name)
        self.cycle_idx = 0
        self.pulse_idx = 0
        self._refresh_from_data()

    # ---- readable "available" helpers ------------------------------------
    @staticmethod
    def _fmt_available(items):
        if not items:
            return "none"
        items = sorted(items)
        if items == list(range(items[0], items[-1] + 1)):
            return f"{items[0]}–{items[-1]}  ({len(items)})"
        shown = ", ".join(str(x) for x in items[:14])
        return shown + (", …" if len(items) > 14 else "")

    def _update_cycle_widgets(self):
        self.cycle_hint.configure(text=f"available: {self._fmt_available(self.cycle_list)}")
        self.cycle_entry_var.set(str(self._current_cycle()) if self.cycle_list else "")

    def _update_pulse_widgets(self):
        self.pulse_hint.configure(text=f"available: {self._fmt_available(self.pulse_list)}")
        self.pulse_entry_var.set(str(self.pulse_list[self.pulse_idx]) if self.pulse_list else "")

    def _sync_window_entries(self):
        """Reflect the window actually IN EFFECT for the current pulse in the entry
        fields - saved, auto-suggested, previewed, or the default - so the start/end
        boxes always show the real numbers, not only the plot."""
        if not self.pulse_list:
            return
        spec, _src = self._win_lookup(self._current_cycle(), self.phase,
                                      self.pulse_list[self.pulse_idx])
        mode, s, e = spec
        self.mode_var.set(mode)
        self.start_var.set(f"{s:g}")
        self.end_var.set(f"{e:g}")
        self._update_units_hint()

    # ---- navigation -------------------------------------------------------
    def _current_cycle(self):
        return self.cycle_list[self.cycle_idx] if self.cycle_list else None

    def _load_current_cycle(self):
        cyc = self._current_cycle()
        if cyc is None or self.df_raw is None:
            return
        self.preview.clear()
        self._overall = None
        self._status(f"Loading cycle {cyc}…")
        self.reg = ra.load_cycle_for_regression(self.df_raw, cyc)
        self._refresh_pulse_list(reset=True)
        self._update_cycle_widgets()
        self._update_pulse_widgets()
        self._sync_window_entries()
        self._update_labels()
        self._plot()

    def _refresh_pulse_list(self, reset=False):
        if self.reg is None:
            self.pulse_list = []
        elif self.phase == CHARGE:
            self.pulse_list = list(self.reg.charge_pulses)
        else:
            self.pulse_list = list(self.reg.discharge_pulses)
        if reset or self.pulse_idx >= len(self.pulse_list):
            self.pulse_idx = 0

    def _go_cycle(self):
        try:
            c = int(float(self.cycle_entry_var.get().strip()))
        except ValueError:
            self._status("Enter a cycle number")
            return
        if c not in self.cycle_list:
            self._status(f"Cycle {c} not available")
            return
        self.cycle_idx = self.cycle_list.index(c)
        self._load_current_cycle()

    def _prev_cycle(self):
        if self.cycle_list and self.cycle_idx > 0:
            self.cycle_idx -= 1
            self._load_current_cycle()

    def _next_cycle(self):
        if self.cycle_list and self.cycle_idx < len(self.cycle_list) - 1:
            self.cycle_idx += 1
            self._load_current_cycle()

    def _go_pulse(self):
        try:
            p = int(float(self.pulse_entry_var.get().strip()))
        except ValueError:
            self._status("Enter a pulse number")
            return
        if p not in self.pulse_list:
            self._status(f"Pulse {p} not available")
            return
        self.pulse_idx = self.pulse_list.index(p)
        self._on_pulse_change()

    def _prev_pulse(self):
        if self.pulse_list and self.pulse_idx > 0:
            self.pulse_idx -= 1
            self._on_pulse_change()

    def _next_pulse(self):
        if self.pulse_list and self.pulse_idx < len(self.pulse_list) - 1:
            self.pulse_idx += 1
            self._on_pulse_change()

    def _on_pulse_change(self):
        self.preview.clear()
        self._overall = None
        self._update_pulse_widgets()
        self._sync_window_entries()
        self._update_labels()
        self._plot()

    def _on_phase(self, _value=None):
        self.phase = CHARGE if self.phase_var.get() == "Charge" else DISCHARGE
        self.preview.clear()
        self._overall = None
        self._refresh_pulse_list(reset=True)
        self._update_pulse_widgets()
        self._sync_window_entries()
        self._update_labels()
        self._plot()

    def _on_mode(self, _value=None):
        """Switching mode shows the current pulse's window for THIS mode if it has
        a saved/resolved one in this mode, otherwise the mode's defaults - so a
        non-default saved window stays visible when you toggle index <-> time."""
        mode = self.mode_var.get()
        s = e = None
        if self.pulse_list:
            spec, _src = self._win_lookup(self._current_cycle(), self.phase,
                                          self.pulse_list[self.pulse_idx])
            if spec[0] == mode:
                _m, s, e = spec
        if s is None:
            s, e = _mode_defaults(mode)
        self.start_var.set(f"{s:g}")
        self.end_var.set(f"{e:g}")
        self._update_units_hint()

    def _update_units_hint(self):
        hints = {
            MODE_TIME: "time: seconds  ·  e.g. 0.1 – 1.0 s",
            MODE_INDEX: "index: 1-based sample points  ·  e.g. 2 – 10",
        }
        self.win_units.configure(text=hints.get(self.mode_var.get(), ""))

    # ---- apply (preview) / save (persist) --------------------------------
    def _cur_key_pulse(self):
        return (self._current_cycle(), self.phase, self.pulse_list[self.pulse_idx])

    def _apply_pulse(self):
        if not self.pulse_list:
            return
        self.preview[self._cur_key_pulse()] = self._live_spec()
        self._overall = None
        self._after_window_change("Applied window to this pulse (preview)")

    def _apply_cycle(self):
        self.preview[(self._current_cycle(), self.phase)] = self._live_spec()
        self._overall = None
        self._after_window_change("Applied window to this cycle (preview)")

    def _apply_all(self):
        self.preview[(self.phase,)] = self._live_spec()
        self._overall = None
        self._after_window_change("Applied window to all cycles (preview)")

    def _save_pulse(self):
        if not self.pulse_list:
            return
        key = self._cur_key_pulse()
        self.saved[key] = self._live_spec()
        self.preview.pop(key, None)
        self._overall = None
        self._after_window_change("Saved window for this pulse")

    def _save_cycle(self):
        key = (self._current_cycle(), self.phase)
        self.saved[key] = self._live_spec()
        self.preview.pop(key, None)
        self._overall = None
        self._after_window_change("Saved window for this cycle")

    def _save_all(self):
        key = (self.phase,)
        self.saved[key] = self._live_spec()
        self.preview.pop(key, None)
        self._overall = None
        self._after_window_change("Saved window for all cycles")

    def _after_window_change(self, msg):
        self._update_labels()
        self._plot()
        self._status(msg)

    # ---- auto fit-window estimation --------------------------------------
    def _on_fit_mode(self, _value=None):
        self.manual_frame.pack_forget()
        self.auto_frame.pack_forget()
        self.autoopts_frame.pack_forget()
        if self.fit_mode_var.get() == "Auto":
            self.auto_frame.pack(fill="x")
            if self._autoopts_open:                 # keep options open across toggles
                self.autoopts_frame.pack(fill="x", pady=(4, 0))
            self._auto_all_pulses()        # Auto is one step: run as soon as it's picked
        else:
            self.manual_frame.pack(fill="x")

    def _toggle_autoopts(self):
        self._autoopts_open = not self._autoopts_open
        if self._autoopts_open:
            self.autoopts_frame.pack(fill="x", pady=(4, 0))   # appends below auto_frame
            self.autoopts_toggle.configure(text="⚙  Auto fit options   –")
        else:
            self.autoopts_frame.pack_forget()
            self.autoopts_toggle.configure(text="⚙  Auto fit options   +")

    def _build_auto_settings(self, parent):
        pad = 8
        ctk.CTkLabel(parent, text="Auto fit settings", font=theme.font_sans(12, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(fill="x", padx=pad, pady=(pad, 2))

        def _row(label, var, hint):
            r = ctk.CTkFrame(parent, fg_color="transparent")
            r.pack(fill="x", padx=pad, pady=1)
            ctk.CTkLabel(r, text=label, font=theme.font_sans(12), text_color=theme.MUTED,
                         width=96, anchor="w").pack(side="left")
            ctk.CTkEntry(r, textvariable=var, width=64, font=theme.font_mono(12),
                         corner_radius=theme.RADIUS_INPUT).pack(side="left")
            ctk.CTkLabel(r, text=hint, font=theme.font_sans(11), text_color=theme.MUTED,
                         anchor="w").pack(side="left", padx=(6, 0))

        _row("skip first", self.auto_skip_var, "IR-drop pts")
        _row("min points", self.auto_minpts_var, "")
        _row("min adj R²", self.auto_adjr2_var, "linearity")
        _row("edge points", self.auto_edge_var, "curvature")
        ctk.CTkButton(parent, text="Re-run auto fit", command=self._auto_all_pulses, height=30,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
                      corner_radius=theme.RADIUS_INPUT).pack(fill="x", padx=pad, pady=(6, pad))

    def _auto_kwargs(self):
        def _num(var, default, cast):
            try:
                return cast(var.get())
            except (ValueError, tk.TclError):
                return default
        return dict(
            skip_initial=_num(self.auto_skip_var, ra.AUTO_SKIP_INITIAL, int),
            min_points=_num(self.auto_minpts_var, ra.AUTO_MIN_POINTS, int),
            adj_r2_min=_num(self.auto_adjr2_var, ra.AUTO_ADJ_R2_MIN, float),
            edge_points=_num(self.auto_edge_var, ra.AUTO_EDGE_POINTS, int),
        )

    def _pulse_current_ma(self, data, pulse):
        active = data[(data['pulse_number'] == pulse) & (data['I/mA'] != 0)]['I/mA']
        return float(np.median(active.values)) if len(active) else float('nan')

    def _physical_flags(self, out, data, pulse):
        """Current-dependent QC flags the pure estimator can't know on its own."""
        flags = list(out['flags'])
        i_ma = self._pulse_current_ma(data, pulse)
        if not np.isfinite(i_ma) or abs(i_ma) < 0.5:
            flags.append('degenerate_dI')
        else:
            i_a = i_ma / 1000.0
            if (-out['intercept'] / i_a) < 0 or (-out['slope'] / i_a) < 0:
                flags.append('non_physical')
        return flags

    def _flagged_summary(self, flags_map, limit=6):
        """Short 'cyc0 chg p1, ...' list of flagged pulses for the status line."""
        if not flags_map:
            return ""
        abbr = {CHARGE: "chg", DISCHARGE: "dis"}
        items = [f"cyc{c} {abbr[ph]} p{p}" for (c, ph, p) in sorted(flags_map)]
        shown = ", ".join(items[:limit])
        if len(items) > limit:
            shown += f", +{len(items) - limit} more"
        return ": " + shown

    def _auto_all_pulses(self):
        """Fit the optimal window for every pulse of every cycle (both phases) at
        once. Results show as a pending suggestion; Save commits them."""
        if self.df_raw is None or not self.cycle_list:
            self._status("Load a file first")
            return
        kw = self._auto_kwargs()
        mode = self._mode()
        pending, flags_map, n_set = {}, {}, 0
        cycles_done = set()
        for cyc in self.cycle_list:
            reg = ra.load_cycle_for_regression(self.df_raw, cyc)
            if reg is None:
                continue
            for phase, data, pulses in ((CHARGE, reg.charge_data, reg.charge_pulses),
                                        (DISCHARGE, reg.discharge_data, reg.discharge_pulses)):
                if not pulses or not len(data):
                    continue
                for p in pulses:
                    rest = ra.pulse_rest_data(data, p)
                    if rest is None:
                        continue
                    out = ra.estimate_optimal_window(rest, **kw)
                    if out is None:
                        continue
                    if mode == MODE_TIME:
                        pending[(cyc, phase, p)] = (MODE_TIME, out['time_start'], out['time_end'])
                    else:
                        pending[(cyc, phase, p)] = (MODE_INDEX, out['index_start'], out['index_end'])
                    n_set += 1
                    cycles_done.add(cyc)
                    fl = self._physical_flags(out, data, p)
                    if fl:
                        flags_map[(cyc, phase, p)] = fl
        if not pending:
            self._status("Auto: no pulses could be fit")
            return
        self.auto_windows = pending
        self.auto_flags = flags_map
        self.preview.clear()
        self._overall = None
        self._sync_window_entries()
        self._update_labels()
        self._plot()
        self._status(f"Auto: fit {n_set} pulse(s) in {len(cycles_done)} cycle(s), both "
                     f"phases — {len(flags_map)} flagged"
                     f"{self._flagged_summary(flags_map)}. Review, then Save.")

    def _save_auto(self):
        if not self.auto_windows:
            self._status("Nothing to save — click Auto first")
            return
        n = len(self.auto_windows)
        self.saved.update(self.auto_windows)
        self.auto_windows = {}
        self.auto_flags = {}
        self._sync_saved()
        self._overall = None
        self._sync_window_entries()
        self._update_labels()
        self._plot()
        self._status(f"Saved {n} auto windows.")

    def _restore_defaults(self):
        """Clear every applied/saved window so all pulses revert to the default."""
        self.saved.clear()
        self.preview.clear()
        self.auto_windows = {}
        self.auto_flags = {}
        self._overall = None
        s, e = _mode_defaults(self._mode())
        self.start_var.set(f"{s:g}")
        self.end_var.set(f"{e:g}")
        self._sync_window_entries()
        self._update_labels()
        self._plot()
        self._status("Restored default regression windows")

    # ---- window resolution ------------------------------------------------
    def _mode(self):
        return self.mode_var.get()

    def _bounds(self):
        try:
            return float(self.start_var.get()), float(self.end_var.get())
        except ValueError:
            return None, None

    def _live_spec(self):
        """The window currently TYPED in the entry boxes. Only Apply/Save read it;
        it never feeds the fits directly (that way typing/navigating never shifts
        other pulses' R²)."""
        s, e = self._bounds()
        if s is None:
            s, e = _mode_defaults(self._mode())
        return (self._mode(), s, e)

    def _default_spec(self):
        """The default window for the current mode - the stable fallback used by
        every pulse that has no applied/saved window of its own."""
        s, e = _mode_defaults(self._mode())
        return (self._mode(), s, e)

    def _win_lookup(self, cyc, phase, pulse):
        """(spec, source) for the most specific window that applies to a pulse:
        preview > saved (pulse > cycle > all) > the default. The live entry values
        are NOT a fallback - they take effect only when Applied or Saved - so
        moving between pulses leaves every other pulse's window (and R²) untouched."""
        for key, scope in (((cyc, phase, pulse), "pulse"),
                           ((cyc, phase), "cycle"),
                           ((phase,), "all")):
            if key in self.preview:
                return self.preview[key], f"{scope}·preview"
            if key in self.auto_windows:
                return self.auto_windows[key], f"{scope}·auto"
            if key in self.saved:
                return self.saved[key], f"{scope}·saved"
        return self._default_spec(), "default"

    def _win_spec(self, cyc, phase, pulse):
        return self._win_lookup(cyc, phase, pulse)[0]

    @staticmethod
    def _fmt_window(spec):
        mode, s, e = spec
        if mode == MODE_TIME:
            return f"{s:g}–{e:g} s"
        return f"{int(round(s))}–{int(round(e))} pt"

    def _phase_data(self):
        if self.reg is None:
            return None
        return self.reg.charge_data if self.phase == CHARGE else self.reg.discharge_data

    def _rest_of(self, data, pulse_num):
        rest = data[(data["pulse_number"] == pulse_num) & (data["I/mA"] == 0)].copy()
        if len(rest) == 0:
            return None
        v0 = ra.get_V0(data, pulse_num)
        if np.isnan(v0):
            return None
        rest["ΔV"] = rest["E/V"] - v0
        return rest

    def _window_for(self, rest, cyc, phase, pulse):
        mode, s, e = self._win_spec(cyc, phase, pulse)
        return ra.resolve_window(rest, mode, s, e)

    def _current_fit(self):
        data = self._phase_data()
        if data is None or len(data) == 0 or not self.pulse_list:
            return None
        pulse = self.pulse_list[self.pulse_idx]
        rest = self._rest_of(data, pulse)
        if rest is None:
            return None
        r1s, r1l = self._window_for(rest, self._current_cycle(), self.phase, pulse)
        res = ra.compute_single_pulse_regression(rest, r1s, r1l)
        res["_rest"] = rest
        res["_win"] = (r1s, r1l)
        # Pre-pulse current (amps) for R/k, from the canonical helper.
        cur, _ = ka.get_pre_pulse_currents(data, [pulse])
        res["_I"] = float(cur[0]) if len(cur) else np.nan
        return res

    def _r2_for(self, cyc, phase, data, pulse):
        rest = data[(data["pulse_number"] == pulse) & (data["I/mA"] == 0)]
        if len(rest) == 0:
            return np.nan
        r1s, r1l = self._window_for(rest, cyc, phase, pulse)
        return ra.compute_r2_for_pulse(data, pulse, r1s, r1l).get("r2", np.nan)

    def _cycle_r2s(self, cyc, phase, data, pulses):
        return [self._r2_for(cyc, phase, data, p) for p in pulses]

    def _update_labels(self):
        self._update_cycle_widgets()
        self._update_pulse_widgets()
        lines = []
        if self.pulse_list:
            spec, src = self._win_lookup(self._current_cycle(), self.phase,
                                         self.pulse_list[self.pulse_idx])
            lines.append(f"window: {self._fmt_window(spec)}  [{src}]")
            key = (self._current_cycle(), self.phase, self.pulse_list[self.pulse_idx])
            if key in self.auto_flags:
                lines.append("⚠ flagged: " + ", ".join(self.auto_flags[key]))
        fit = self._current_fit()
        if fit is not None and not np.isnan(fit["r2"]):
            lines.append(f"slope = {fit['slope']:.5g}")
            lines.append(f"intercept = {fit['intercept']:.5g}")
            lines.append(f"R² = {fit['r2']:.5f}")
        elif self.reg is not None and self.pulse_list:
            lines.append("No valid fit for this window.")
        self.info.configure(text="\n".join(lines))

    # ---- overall check ----------------------------------------------------
    def _overall_check(self):
        if self.df_raw is None or not self.cycle_list:
            self._status("Load a file first")
            return
        if self._overall is not None:            # toggle back to the current cycle's R²
            self._overall = None
            self._plot()
            self._status("Back to this cycle's R²")
            return
        self._status("Computing R² across all cycles…")
        charge_rows, discharge_rows = [], []
        for cyc in self.cycle_list:
            reg = ra.load_cycle_for_regression(self.df_raw, cyc)
            if reg is None:
                continue
            if reg.charge_pulses and len(reg.charge_data):
                for i, p in enumerate(reg.charge_pulses):
                    charge_rows.append((cyc, i, self._r2_for(cyc, CHARGE, reg.charge_data, p)))
            if reg.discharge_pulses and len(reg.discharge_data):
                for i, p in enumerate(reg.discharge_pulses):
                    discharge_rows.append((cyc, i, self._r2_for(cyc, DISCHARGE, reg.discharge_data, p)))
        self._overall = {"charge": charge_rows, "discharge": discharge_rows}
        allr2 = [r for _, _, r in charge_rows + discharge_rows if not np.isnan(r)]
        ncyc = len({c for c, _, _ in charge_rows + discharge_rows})
        if allr2:
            self._status(f"Overall R²: {ncyc} cycles, {len(allr2)} pulses, "
                         f"mean {np.mean(allr2):.4f}, min {np.min(allr2):.4f}")
        else:
            self._status("Overall check: no valid fits")
        self._plot()

    # ---- plotting ---------------------------------------------------------
    def _clear_plot(self):
        self.panel.figure.clear()
        self.panel.refresh()

    def _plot(self):
        fig = self.panel.figure
        fig.clear()
        if self.df_raw is None or self._current_cycle() is None:
            self.panel.refresh()
            return
        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)
        self._plot_regression(ax1)
        if self._overall is not None:
            self._plot_overall(ax2)
        else:
            self._plot_r2_cycle(ax2)
        self.panel.refresh()

    def _add_secondary_time_axis(self, ax):
        """Top x-axis in seconds, mapped onto the √t bottom axis."""
        xlim = ax.get_xlim()
        max_t = xlim[1] ** 2
        if max_t <= 0:
            return
        if max_t <= 10:
            tv = [0, 1, 4, 9, 16, 25, 36, 49, 64, 81, 100]
        elif max_t <= 25:
            tv = [0, 1, 4, 9, 16, 25]
        elif max_t <= 100:
            tv = [0, 4, 16, 36, 64, 100]
        else:
            tv = [0, 25, 100, 225, 400]
        tv = [t for t in tv if t <= max_t]
        ax_top = ax.twiny()
        ax_top.set_xlim(xlim)
        ax_top.set_xticks([np.sqrt(t) for t in tv])
        ax_top.set_xticklabels([str(int(t)) for t in tv])
        ax_top.set_xlabel("Time (s)", fontsize=10, color=theme.MUTED)
        ax_top.tick_params(axis="x", labelsize=9, colors=theme.MUTED)

    def _plot_regression(self, ax):
        color = C_CHARGE if self.phase == CHARGE else C_DISCHARGE
        fit = self._current_fit()
        if fit is None:
            ax.text(0.5, 0.5, f"No {self.phase} pulse / fit available",
                    ha="center", va="center", transform=ax.transAxes, color=theme.MUTED)
            ax.set_xticks([])
            ax.set_yticks([])
            return

        rest = fit["_rest"]
        r1s, r1l = fit["_win"]
        t_sqrt = np.sqrt(rest["t/s"].to_numpy() - rest["t/s"].to_numpy()[0])
        dv = rest["ΔV"].to_numpy()

        ax.plot(t_sqrt, dv, marker="o", linestyle="-", color=color, markersize=3,
                linewidth=1, label="ΔV")

        if r1l > 0 and r1s < len(t_sqrt):
            hi = min(r1s + r1l - 1, len(t_sqrt) - 1)
            if t_sqrt[hi] > t_sqrt[r1s]:
                ax.axvspan(t_sqrt[r1s], t_sqrt[hi], color=C_WINDOW, alpha=0.2,
                           zorder=0, label="_nolegend_")

        if not np.isnan(fit["r2"]) and len(rest) >= r1s + r1l:
            xf = t_sqrt[r1s:r1s + r1l]
            yf = fit["slope"] * xf + fit["intercept"]
            ax.plot(xf, yf, color=C_FIT, linewidth=3,
                    label=(f"slope {fit['slope']:.4g}\nint {fit['intercept']:.4g}"
                           f"\nR² {fit['r2']:.4f}"))
            ax.plot(xf, dv[r1s:r1s + r1l], "o", color=C_REGPTS, markersize=6,
                    alpha=0.6, label="fit points")

        ax.set_xlabel("√Time (√s)", fontsize=12)
        ax.set_ylabel("ΔV (V)", fontsize=12)
        ax.grid(True, alpha=0.3)

        pn = self.pulse_list[self.pulse_idx]
        title = f"{self.phase.capitalize()} pulse {pn} · cycle {self._current_cycle()}"
        I = fit.get("_I", np.nan)
        if not np.isnan(fit["r2"]) and not np.isnan(I) and I != 0:
            R = -fit["intercept"] / I           # R = -intercept / I   (I in amps)
            k = -fit["slope"] / I               # k = -slope / I
            title += f"\nR = {R:.4g} Ω    k = {k:.4g} Ω·s$^{{-1/2}}$"
        ax.set_title(title, fontsize=11, fontweight="bold", pad=8)

        leg = ax.legend(loc="best", fontsize="x-small", frameon=True)
        if leg is not None:
            leg.set_draggable(True)
        self._add_secondary_time_axis(ax)

    def _plot_r2_cycle(self, ax):
        data = self._phase_data()
        color = C_CHARGE if self.phase == CHARGE else C_DISCHARGE
        if data is None or not self.pulse_list:
            ax.text(0.5, 0.5, "No pulses in this cycle", ha="center", va="center",
                    transform=ax.transAxes, color=theme.MUTED)
            ax.set_xticks([])
            ax.set_yticks([])
            return
        r2s = self._cycle_r2s(self._current_cycle(), self.phase, data, self.pulse_list)
        xs = range(1, len(self.pulse_list) + 1)
        # Phase-coloured R² trace (blue = charge, red = discharge) to match the
        # single-pulse and overall plots. #3
        ax.plot(xs, r2s, color=color, marker="o", linestyle="-", linewidth=1,
                markersize=4, label="R²")
        sel_r2 = r2s[self.pulse_idx] if self.pulse_idx < len(r2s) else np.nan
        ax.plot(self.pulse_idx + 1, sel_r2, "o", color=color, markersize=10,
                markeredgecolor="black", markeredgewidth=1.3, zorder=5, label="selected")
        ax.set_xlabel("Pulse #", fontsize=12)
        ax.set_ylabel("R²", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.set_title(f"{self.phase.capitalize()} R² across pulses "
                     f"(cycle {self._current_cycle()})", fontsize=11)
        leg = ax.legend(loc="best", fontsize=9)
        if leg is not None:
            leg.set_draggable(True)
        self._apply_r2_limits(ax)

    def _plot_overall(self, ax):
        charge = self._overall["charge"]
        discharge = self._overall["discharge"]
        if not charge and not discharge:
            ax.text(0.5, 0.5, "No valid fits across cycles", ha="center", va="center",
                    transform=ax.transAxes, color=theme.MUTED)
            ax.set_xticks([])
            ax.set_yticks([])
            return

        all_cycles = sorted({c for c, _, _ in charge + discharge})
        cmin, cmax = all_cycles[0], all_cycles[-1]

        for i, c in enumerate(all_cycles):
            if i % 2 == 0:
                right = (all_cycles[i + 1] - 0.35) if i < len(all_cycles) - 1 else (c + 0.65)
                ax.axvspan(c - 0.35, right, color="lightgray", alpha=0.3, zorder=0)

        def shade(cmap, c):
            t = 0.0 if cmax == cmin else (c - cmin) / (cmax - cmin)
            return cmap(0.4 + 0.6 * t)

        blues, reds = plt.colormaps["Blues"], plt.colormaps["Reds"]
        for rows, cmap, marker in ((charge, blues, "o"), (discharge, reds, "s")):
            by_cycle = {}
            for c, idx, r2 in rows:
                by_cycle.setdefault(c, []).append((idx, r2))
            for c, pts in by_cycle.items():
                pts.sort()
                r2v = [r for _, r in pts]
                n = len(r2v)
                xs = [c] if n == 1 else np.linspace(c - 0.3, c + 0.3, n)
                ax.plot(xs, r2v, marker=marker, linestyle="-", color=shade(cmap, c),
                        markersize=5, alpha=0.85)

        ax.set_xlabel("Cycle number", fontsize=12)
        ax.set_ylabel("R²", fontsize=12)
        ax.grid(True, alpha=0.3)

        # One integer tick per cycle, at the LEFT edge of its pulse group (no
        # fractional 1.2/1.3 pulse labels). Thin the labels when there are many.
        ax.set_xticks([c - 0.35 for c in all_cycles])
        n = len(all_cycles)
        if n > 50:
            labels = [str(c) if c % 10 == 0 else "" for c in all_cycles]
        elif n > 20:
            labels = [str(c) if c % 5 == 0 else "" for c in all_cycles]
        else:
            labels = [str(c) for c in all_cycles]
        ax.set_xticklabels(labels)
        ax.set_xlim(all_cycles[0] - 0.45, all_cycles[-1] + 0.65)

        handles = [
            Line2D([0], [0], color=blues(0.7), marker="o", linestyle="-", markersize=6,
                   label="Charge"),
            Line2D([0], [0], color=reds(0.7), marker="s", linestyle="-", markersize=6,
                   label="Discharge"),
        ]
        leg = ax.legend(handles=handles, loc="best", fontsize=9)
        if leg is not None:
            leg.set_draggable(True)
        ax.set_title("R² across all cycles", fontsize=11, fontweight="bold")
        self._apply_r2_limits(ax)       # user limits override the auto x-range above

    # ---- export -----------------------------------------------------------
    def _export(self):
        if self.df_raw is None:
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
        cyc = self._current_cycle()
        stem = os.path.splitext(self.sel_file or "pyICI_regression")[0]
        path = filedialog.asksaveasfilename(
            title="Export regression figure", defaultextension=f".{fmt}",
            initialfile=f"{stem}_cycle{cyc}_{self.phase}.{fmt}",
            filetypes=[(fmt.upper(), f"*.{fmt}"), ("All files", "*.*")])
        if not path:
            return
        try:
            export_figure(self.panel.figure, path, width_in=w, height_in=h, dpi=dpi)
        except Exception as exc:
            self._status(f"Export failed: {exc}")
            return
        self._status(f"Exported → {os.path.basename(path)}  ({w:g}×{h:g} in, {dpi} dpi)")
