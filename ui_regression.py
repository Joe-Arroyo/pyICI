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
import analysis.regression_analyzer as ra
import analysis.kinetic_analyzer as ka

CHARGE = "charge"
DISCHARGE = "discharge"

C_CHARGE = "#1f77b4"      # blue
C_DISCHARGE = "#d62728"   # red
C_FIT = "#15803d"         # green fit line
C_WINDOW = "#9aa7ae"      # grey window shading
C_REGPTS = "#e8820c"      # orange regression points

TIME_START, TIME_END = ra.DEFAULT_TIME_START, ra.DEFAULT_TIME_END      # 0.1, 1.0 s
INDEX_START, INDEX_END = ra.DEFAULT_INDEX_START, ra.DEFAULT_INDEX_END   # 2, 10 (1-based)


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

        self.fig_w_var = tk.StringVar(value="10")
        self.fig_h_var = tk.StringVar(value="8")
        self.dpi_var = tk.StringVar(value="300")
        self.fmt_var = tk.StringVar(value="png")
        self._settings_open = False

        self._build()

    # ---- layout -----------------------------------------------------------
    def _build(self):
        card, outer = theme.card(self, "Regression - controls", width=theme.CONTROL_W)
        card.pack(side="left", fill="y", padx=(0, theme.GAP))
        card.pack_propagate(False)
        body = ctk.CTkScrollableFrame(outer, fg_color="transparent")
        body.pack(fill="both", expand=True)

        ctk.CTkLabel(body, text="File", font=theme.font_sans(12), text_color=theme.MUTED,
                     anchor="w").pack(fill="x")
        self.file_menu = ctk.CTkOptionMenu(
            body, variable=self.file_var, values=["(no files)"], command=self._on_file_change,
            fg_color=theme.SURFACE, text_color=theme.TEXT, button_color=theme.ACCENT,
            button_hover_color=theme.ACCENT_HOVER, font=theme.font_sans(13),
            dropdown_font=theme.font_sans(13))
        self.file_menu.pack(fill="x", pady=(2, 0))
        ctk.CTkLabel(body, text="(files are loaded in Data loading)",
                     font=theme.font_sans(11), text_color=theme.FAINT,
                     anchor="w").pack(fill="x", pady=(0, 2))

        # Cycle entry
        ctk.CTkLabel(body, text="Cycle", font=theme.font_sans(12), text_color=theme.MUTED,
                     anchor="w").pack(fill="x", pady=(10, 2))
        cyc_row = ctk.CTkFrame(body, fg_color="transparent")
        cyc_row.pack(fill="x")
        self._arrow(cyc_row, "◀", self._prev_cycle).pack(side="left")
        self.cycle_entry = ctk.CTkEntry(cyc_row, textvariable=self.cycle_entry_var, width=56,
                                        font=theme.font_mono(13), corner_radius=theme.RADIUS_INPUT,
                                        justify="center")
        self.cycle_entry.pack(side="left", padx=4)
        self.cycle_entry.bind("<Return>", lambda e: self._go_cycle())
        self._arrow(cyc_row, "▶", self._next_cycle).pack(side="left")
        ctk.CTkButton(cyc_row, text="Go", command=self._go_cycle, width=48,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", padx=(6, 0))
        self.cycle_hint = ctk.CTkLabel(body, text="", font=theme.font_sans(11),
                                       text_color=theme.FAINT, anchor="w", justify="left",
                                       wraplength=320)
        self.cycle_hint.pack(fill="x")

        # Phase toggle
        ctk.CTkLabel(body, text="Phase", font=theme.font_sans(12), text_color=theme.MUTED,
                     anchor="w").pack(fill="x", pady=(10, 2))
        self.phase_seg = ctk.CTkSegmentedButton(
            body, values=["Charge", "Discharge"], variable=self.phase_var,
            command=self._on_phase, font=theme.font_sans(13),
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.BG, unselected_hover_color=theme.ACCENT_TINT,
            text_color=theme.TEXT)
        self.phase_seg.pack(fill="x")

        # Pulse entry
        ctk.CTkLabel(body, text="Pulse", font=theme.font_sans(12), text_color=theme.MUTED,
                     anchor="w").pack(fill="x", pady=(10, 2))
        pl_row = ctk.CTkFrame(body, fg_color="transparent")
        pl_row.pack(fill="x")
        self._arrow(pl_row, "◀", self._prev_pulse).pack(side="left")
        self.pulse_entry = ctk.CTkEntry(pl_row, textvariable=self.pulse_entry_var, width=56,
                                        font=theme.font_mono(13), corner_radius=theme.RADIUS_INPUT,
                                        justify="center")
        self.pulse_entry.pack(side="left", padx=4)
        self.pulse_entry.bind("<Return>", lambda e: self._go_pulse())
        self._arrow(pl_row, "▶", self._next_pulse).pack(side="left")
        ctk.CTkButton(pl_row, text="Go", command=self._go_pulse, width=48,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", padx=(6, 0))
        self.pulse_hint = ctk.CTkLabel(body, text="", font=theme.font_sans(11),
                                       text_color=theme.FAINT, anchor="w", justify="left",
                                       wraplength=320)
        self.pulse_hint.pack(fill="x")

        # Regression window (live values you type, then Apply/Save at a scope)
        ctk.CTkLabel(body, text="Regression window", font=theme.font_sans(12),
                     text_color=theme.MUTED, anchor="w").pack(fill="x", pady=(12, 2))
        ctk.CTkOptionMenu(body, variable=self.mode_var, values=["time", "index"],
                          command=self._on_mode, fg_color=theme.SURFACE, text_color=theme.TEXT,
                          button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                          font=theme.font_sans(13), dropdown_font=theme.font_sans(13)
                          ).pack(fill="x")
        win_row = ctk.CTkFrame(body, fg_color="transparent")
        win_row.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(win_row, text="start", font=theme.font_sans(11), text_color=theme.FAINT,
                     width=36, anchor="w").pack(side="left")
        self.start_entry = ctk.CTkEntry(win_row, textvariable=self.start_var, width=70,
                                        font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT)
        self.start_entry.pack(side="left", padx=(0, 8))
        ctk.CTkLabel(win_row, text="end", font=theme.font_sans(11), text_color=theme.FAINT,
                     width=28, anchor="w").pack(side="left")
        self.end_entry = ctk.CTkEntry(win_row, textvariable=self.end_var, width=70,
                                      font=theme.font_mono(12), corner_radius=theme.RADIUS_INPUT)
        self.end_entry.pack(side="left")
        self.start_entry.bind("<Return>", lambda e: self._apply_pulse())
        self.end_entry.bind("<Return>", lambda e: self._apply_pulse())
        ctk.CTkLabel(body, text="time: seconds  |  index: 1-based points",
                     font=theme.font_sans(11), text_color=theme.FAINT, anchor="w").pack(fill="x")

        # Apply / Save rows (pulse, cycle, all cycles)
        self._apply_save_row(body, "Apply → pulse", self._apply_pulse, self._save_pulse)
        self._apply_save_row(body, "Apply → cycle", self._apply_cycle, self._save_cycle)
        self._apply_save_row(body, "Apply → all cycles", self._apply_all, self._save_all)

        ctk.CTkButton(body, text="Restore defaults", command=self._restore_defaults,
                      fg_color=theme.SURFACE, text_color=theme.MUTED, border_color=theme.BORDER,
                      border_width=1, hover_color=theme.BG, font=theme.font_sans(12),
                      corner_radius=theme.RADIUS_INPUT).pack(fill="x", pady=(4, 0))

        ctk.CTkButton(body, text="Overall check (R² all cycles)", command=self._overall_check,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT, font=theme.font_sans(13),
                      corner_radius=theme.RADIUS_INPUT).pack(fill="x", pady=(10, 0))

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

        # Plots
        plot_card, plot_body = theme.card(self, "Regression - plots")
        plot_card.pack(side="left", fill="both", expand=True)
        self.panel = PlotPanel(plot_body, figsize=(10, 8))
        self.panel.pack(fill="both", expand=True)

    def _arrow(self, parent, text, command):
        return ctk.CTkButton(parent, text=text, width=40, height=30, command=command,
                             fg_color=theme.SURFACE, text_color=theme.ACCENT,
                             border_color=theme.ACCENT, border_width=1,
                             hover_color=theme.ACCENT_TINT, font=theme.font_sans(13, "bold"),
                             corner_radius=theme.RADIUS_INPUT)

    def _apply_save_row(self, parent, label, apply_cmd, save_cmd):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=2)
        ctk.CTkButton(r, text=label, command=apply_cmd, height=30, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, font=theme.font_sans(12, "bold"),
                      corner_radius=theme.RADIUS_INPUT).pack(side="left", fill="x", expand=True,
                                                             padx=(0, 3))
        ctk.CTkButton(r, text="Save", command=save_cmd, height=30,
                      fg_color=theme.SURFACE, text_color=theme.ACCENT, border_color=theme.ACCENT,
                      border_width=1, hover_color=theme.ACCENT_TINT, font=theme.font_sans(12),
                      corner_radius=theme.RADIUS_INPUT).pack(side="left", fill="x", expand=True,
                                                             padx=(3, 0))

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

    def saved_windows_for(self, fname):
        """The saved (not preview) windows for a file - used by the Kinetics bridge."""
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
        """Reflect the current pulse's effective SAVED window in the entry fields,
        or reset to the default parameters when the pulse has no saved window.
        (Previews are cleared on navigation, so only saved windows carry over.)"""
        if not self.pulse_list:
            return
        spec, src = self._win_lookup(self._current_cycle(), self.phase,
                                     self.pulse_list[self.pulse_idx])
        if src.endswith("saved"):
            mode, s, e = spec
            self.mode_var.set(mode)
            self.start_var.set(f"{s:g}")
            self.end_var.set(f"{e:g}")
        elif self.mode_var.get() == "time":
            self.start_var.set(str(TIME_START))
            self.end_var.set(str(TIME_END))
        else:
            self.start_var.set(str(INDEX_START))
            self.end_var.set(str(INDEX_END))

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
        if self.mode_var.get() == "time":
            self.start_var.set(str(TIME_START))
            self.end_var.set(str(TIME_END))
        else:
            self.start_var.set(str(INDEX_START))
            self.end_var.set(str(INDEX_END))

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

    def _restore_defaults(self):
        """Clear every applied/saved window so all pulses revert to the default."""
        self.saved.clear()
        self.preview.clear()
        self._overall = None
        if self._mode() == "time":
            self.start_var.set(str(TIME_START))
            self.end_var.set(str(TIME_END))
        else:
            self.start_var.set(str(INDEX_START))
            self.end_var.set(str(INDEX_END))
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
            s, e = (TIME_START, TIME_END) if self._mode() == "time" else (INDEX_START, INDEX_END)
        return (self._mode(), s, e)

    def _default_spec(self):
        """The default window for the current mode - the stable fallback used by
        every pulse that has no applied/saved window of its own."""
        if self._mode() == "time":
            return ("time", TIME_START, TIME_END)
        return ("index", INDEX_START, INDEX_END)

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
            if key in self.saved:
                return self.saved[key], f"{scope}·saved"
        return self._default_spec(), "default"

    def _win_spec(self, cyc, phase, pulse):
        return self._win_lookup(cyc, phase, pulse)[0]

    @staticmethod
    def _fmt_window(spec):
        mode, s, e = spec
        return f"{s:g}–{e:g} s" if mode == "time" else f"{int(round(s))}–{int(round(e))} pt"

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
        fig.tight_layout(pad=2.2)
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
        ax.set_title(title, fontsize=11, fontweight="bold", pad=26)

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
        ax.plot(xs, r2s, color="black", marker="o", linestyle="-", linewidth=1,
                markersize=4, label="R²")
        sel_r2 = r2s[self.pulse_idx] if self.pulse_idx < len(r2s) else np.nan
        ax.plot(self.pulse_idx + 1, sel_r2, "o", color=color, markersize=9, label="selected")
        ax.set_xlabel("Pulse #", fontsize=12)
        ax.set_ylabel("R²", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.set_title(f"{self.phase.capitalize()} R² across pulses "
                     f"(cycle {self._current_cycle()})", fontsize=11)
        leg = ax.legend(loc="best", fontsize=9)
        if leg is not None:
            leg.set_draggable(True)

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
