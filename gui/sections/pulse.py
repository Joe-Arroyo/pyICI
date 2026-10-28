#!/usr/bin/env python3
"""Pulse check section for the new pyICI GUI.

Adapted from the original Tab 3 (Pulse Analysis), re-laid out as controls-left /
plots-right and made navigable instead of button-driven.

Workflow: the active file comes from the Data-loading section. Step through a
cycle's pulses (charge or discharge); the top plot is the whole-cycle overview
(voltage vs time, phase-coloured, with every V0 marked) and the currently
selected pulse is highlighted on it ("current position"); the bottom plot is that
pulse's detail - voltage + current vs time, with the V0/t0 point marked.

Reuses the analysis layer unchanged: analysis.pulse_analyzer.analyze_cycle_pulses
performs the SAME canonical pulse segmentation the R/k pipeline uses, so what you
see here matches the exported results.
"""
import os
import tkinter as tk
from tkinter import filedialog

import numpy as np
import pandas as pd
import customtkinter as ctk

from gui import theme
from gui.components.plot_panel import PlotPanel
from gui.components.export_helper import export_figure
from gui.components.scroll import AutoHideScrollableFrame
from analysis import pulse_analyzer

CHARGE = "charge"
DISCHARGE = "discharge"

C_CHARGE = "#1f77b4"      # blue
C_DISCHARGE = "#d62728"   # red
C_REST = theme.FAINT      # grey
C_V0 = "#15803d"          # green
C_CURRENT = "#e8820c"     # orange (current trace in the detail plot)


class PulseCheckSection(ctk.CTkFrame):
    """Left controls + right plots for stepping through a cycle's pulses."""

    def __init__(self, parent, app):
        super().__init__(parent, fg_color="transparent")
        self.app = app

        # Data / navigation state
        self.df_raw = None
        self.cycle_list = []
        self.cycle_idx = 0
        self.phase = CHARGE
        self.analysis = None       # PulseAnalysis for the current cycle
        self.pulse_list = []       # valid pulse numbers for the current phase
        self.pulse_idx = 0
        self.sel_file = None       # the file this tab analyzes (independent per tab)

        self.file_var = tk.StringVar(value="")
        self.phase_var = tk.StringVar(value="Charge")
        self.cycle_entry_var = tk.StringVar(value="")
        self.pulse_entry_var = tk.StringVar(value="")

        # Export settings
        self.fig_w_var = tk.StringVar(value="10")
        self.fig_h_var = tk.StringVar(value="8")
        self.dpi_var = tk.StringVar(value="300")
        self.fmt_var = tk.StringVar(value="png")
        self._settings_open = False

        self._build()

    # ---- layout -----------------------------------------------------------
    def _build(self):
        card, outer = theme.card(self, "Pulse verification - controls", width=theme.CONTROL_W)
        card.pack(side="left", fill="y", padx=(0, theme.GAP))
        card.pack_propagate(False)
        body = AutoHideScrollableFrame(outer, fg_color="transparent")  # #2 breathing room
        body.pack(fill="both", expand=True, padx=(2, 12))

        def slabel(text, pady=(0, 2)):                            # #1 bold/dark labels
            ctk.CTkLabel(body, text=text, font=theme.font_sans(13, "bold"),
                         text_color=theme.TEXT, anchor="w").pack(fill="x", pady=pady)

        # File selector (teal dropdown, same as Data loading)     # #1
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

        # Phase selector - below the file, above cycle            # #3
        slabel("Phase", pady=(10, 2))
        self.phase_seg = ctk.CTkSegmentedButton(
            body, values=["Charge", "Discharge"], variable=self.phase_var,
            command=self._on_phase, font=theme.font_sans(13, "bold"),
            selected_color=theme.ACCENT, selected_hover_color=theme.ACCENT_HOVER,
            unselected_color=theme.MUTED, unselected_hover_color=theme.TEXT,
            text_color="#ffffff")       # #1 white text, legible on both segments
        self.phase_seg.pack(fill="x")

        # Cycle navigation - arrows + typed entry + Go            # #4
        slabel("Cycle", pady=(10, 2))
        cyc_row = ctk.CTkFrame(body, fg_color="transparent")
        cyc_row.pack(fill="x")
        self._nav_button(cyc_row, "◀", self._prev_cycle).pack(side="left")
        self.cycle_entry = ctk.CTkEntry(cyc_row, textvariable=self.cycle_entry_var, width=64,
                                        font=theme.font_mono(13), corner_radius=theme.RADIUS_INPUT,
                                        justify="center")
        self.cycle_entry.pack(side="left", padx=4)
        self.cycle_entry.bind("<Return>", lambda e: self._go_cycle())
        self._nav_button(cyc_row, "▶", self._next_cycle).pack(side="left")
        ctk.CTkButton(cyc_row, text="Go", command=self._go_cycle, width=48,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", padx=(6, 0))
        self.cycle_hint = ctk.CTkLabel(body, text="", font=theme.font_sans(12),
                                       text_color=theme.MUTED, anchor="w")
        self.cycle_hint.pack(fill="x")

        # Pulse navigation - arrows + typed entry + Go            # #4
        slabel("Pulse", pady=(10, 2))
        pl_row = ctk.CTkFrame(body, fg_color="transparent")
        pl_row.pack(fill="x")
        self._nav_button(pl_row, "◀", self._prev_pulse).pack(side="left")
        self.pulse_entry = ctk.CTkEntry(pl_row, textvariable=self.pulse_entry_var, width=64,
                                        font=theme.font_mono(13), corner_radius=theme.RADIUS_INPUT,
                                        justify="center")
        self.pulse_entry.pack(side="left", padx=4)
        self.pulse_entry.bind("<Return>", lambda e: self._go_pulse())
        self._nav_button(pl_row, "▶", self._next_pulse).pack(side="left")
        ctk.CTkButton(pl_row, text="Go", command=self._go_pulse, width=48,
                      fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                      font=theme.font_sans(12, "bold"), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", padx=(6, 0))
        self.pulse_hint = ctk.CTkLabel(body, text="", font=theme.font_sans(12),
                                       text_color=theme.MUTED, anchor="w")
        self.pulse_hint.pack(fill="x")

        # Results readout (titles are always shown on the plots - #5)
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
        self.settings_frame = ctk.CTkFrame(body, fg_color=theme.BG,
                                           corner_radius=theme.RADIUS_INPUT)
        self._build_settings(self.settings_frame)

        # Plots
        plot_card, plot_body = theme.card(self, "Pulse verification - plots")
        plot_card.pack(side="left", fill="both", expand=True)
        self.panel = PlotPanel(plot_body, figsize=(10, 8))
        self.panel.pack(fill="both", expand=True)

    def _nav_button(self, parent, text, command):
        return ctk.CTkButton(parent, text=text, width=44, height=30, command=command,
                             fg_color=theme.SURFACE, text_color=theme.ACCENT,
                             border_color=theme.ACCENT, border_width=1,
                             hover_color=theme.ACCENT_TINT, font=theme.font_sans(13, "bold"),
                             corner_radius=theme.RADIUS_INPUT)

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
        """Called by the app when this section becomes visible."""
        self._refresh_from_data()

    def _files(self):
        return getattr(self._data_section(), "files", {})

    def _refresh_from_data(self):
        ds = self._data_section()
        files = self._files()
        names = list(files.keys())
        self.file_menu.configure(values=names or ["(no files)"])
        if not names:
            self.df_raw = None
            self.cycle_list = []
            self.analysis = None
            self.pulse_list = []
            self.sel_file = None
            self.file_var.set("")
            self.cycle_entry_var.set("")
            self.pulse_entry_var.set("")
            self.cycle_hint.configure(text="")
            self.pulse_hint.configure(text="")
            self.info.configure(text="Load a file in the Data loading section first.")
            self._clear_plot()
            return

        if self.sel_file not in files:
            self.sel_file = getattr(ds, "active_name", None) or names[0]
            self.cycle_idx = 0
        self.file_var.set(self.sel_file)
        rec = files[self.sel_file]
        self.df_raw = rec["df_raw"]
        self.cycle_list = list(rec["cycle_list"])
        if self.cycle_idx >= len(self.cycle_list):
            self.cycle_idx = 0
        self._analyze_current_cycle()

    def _on_file_change(self, name):
        if name not in self._files():
            return
        self.sel_file = name
        self.cycle_idx = 0
        self.pulse_idx = 0
        self._refresh_from_data()

    # ---- navigation -------------------------------------------------------
    def _current_cycle(self):
        return self.cycle_list[self.cycle_idx] if self.cycle_list else None

    def _analyze_current_cycle(self):
        cyc = self._current_cycle()
        if cyc is None or self.df_raw is None:
            return
        self._status(f"Analyzing cycle {cyc}…")
        self.analysis = pulse_analyzer.analyze_cycle_pulses(self.df_raw, cyc)
        self._refresh_pulse_list(reset=True)
        self._update_labels()
        self._plot()

    def _refresh_pulse_list(self, reset=False):
        if self.analysis is None:
            self.pulse_list = []
        elif self.phase == CHARGE:
            self.pulse_list = list(self.analysis.charge_pulses)
        else:
            self.pulse_list = list(self.analysis.discharge_pulses)
        if reset or self.pulse_idx >= len(self.pulse_list):
            self.pulse_idx = 0

    def _prev_cycle(self):
        if self.cycle_list and self.cycle_idx > 0:
            self.cycle_idx -= 1
            self._analyze_current_cycle()

    def _next_cycle(self):
        if self.cycle_list and self.cycle_idx < len(self.cycle_list) - 1:
            self.cycle_idx += 1
            self._analyze_current_cycle()

    def _on_phase(self, _value=None):
        self.phase = CHARGE if self.phase_var.get() == "Charge" else DISCHARGE
        self._refresh_pulse_list(reset=True)
        self._update_labels()
        self._plot()

    def _prev_pulse(self):
        if self.pulse_list and self.pulse_idx > 0:
            self.pulse_idx -= 1
            self._update_labels()
            self._plot()

    def _next_pulse(self):
        if self.pulse_list and self.pulse_idx < len(self.pulse_list) - 1:
            self.pulse_idx += 1
            self._update_labels()
            self._plot()

    def _fmt_available(self, values):
        """Compact hint for the list of selectable cycle / pulse numbers."""
        vals = list(values)
        if not vals:
            return ""
        if len(vals) <= 12:
            return "available: " + ", ".join(str(v) for v in vals)
        return f"available: {vals[0]}…{vals[-1]}  ({len(vals)} total)"

    def _go_cycle(self):
        """Jump to the cycle number typed in the entry."""
        raw = self.cycle_entry_var.get().strip()
        try:
            target = int(float(raw))
        except (ValueError, TypeError):
            self._update_labels()
            return
        if target in self.cycle_list:
            self.cycle_idx = self.cycle_list.index(target)
            self.pulse_idx = 0
            self._analyze_current_cycle()
        else:
            self._update_labels()   # restore the valid value

    def _go_pulse(self):
        """Jump to the pulse number typed in the entry."""
        raw = self.pulse_entry_var.get().strip()
        try:
            target = int(float(raw))
        except (ValueError, TypeError):
            self._update_labels()
            return
        if target in self.pulse_list:
            self.pulse_idx = self.pulse_list.index(target)
            self._update_labels()
            self._plot()
        else:
            self._update_labels()   # restore the valid value

    def _update_labels(self):
        cyc = self._current_cycle()
        if cyc is not None:
            self.cycle_entry_var.set(str(cyc))
            self.cycle_hint.configure(
                text=f"{self.cycle_idx + 1} / {len(self.cycle_list)}   ·   "
                     + self._fmt_available(self.cycle_list))
        else:
            self.cycle_entry_var.set("")
            self.cycle_hint.configure(text="")
        if self.pulse_list:
            pn = self.pulse_list[self.pulse_idx]
            self.pulse_entry_var.set(str(pn))
            self.pulse_hint.configure(
                text=f"{self.pulse_idx + 1} / {len(self.pulse_list)}   ·   "
                     + self._fmt_available(self.pulse_list))
        else:
            self.pulse_entry_var.set("")
            self.pulse_hint.configure(text=f"no {self.phase} pulses")

        if self.analysis is not None:
            nc = len(self.analysis.charge_pulses)
            nd = len(self.analysis.discharge_pulses)
            txt = f"{nc} charge · {nd} discharge pulses"
            v0 = self._current_pulse_v0()
            if v0 is not None:
                txt += f"\nV0 = {v0:.4f} V"
            self.info.configure(text=txt)
        else:
            self.info.configure(text="")

    # ---- current-pulse helpers -------------------------------------------
    def _phase_data(self):
        if self.analysis is None:
            return None
        return self.analysis.charge_data if self.phase == CHARGE else self.analysis.discharge_data

    def _current_pulse_df(self):
        data = self._phase_data()
        if data is None or len(data) == 0 or not self.pulse_list:
            return None
        pn = self.pulse_list[self.pulse_idx]
        pdf = data[data["pulse_number"] == pn]
        return pdf if len(pdf) else None

    def _current_pulse_v0(self):
        pdf = self._current_pulse_df()
        if pdf is None or "V0" not in pdf.columns:
            return None
        s = pdf["V0"].dropna()
        return float(s.iloc[0]) if len(s) else None

    # ---- plotting ---------------------------------------------------------
    def _clear_plot(self):
        fig = self.panel.figure
        fig.clear()
        self.panel.refresh()

    def _plot(self):
        fig = self.panel.figure
        fig.clear()
        if self.df_raw is None or self._current_cycle() is None:
            self.panel.refresh()
            return
        # Top: whole-cycle overview (full width). Bottom: the selected pulse's
        # full detail (left) and a zoom on its rest-period relaxation (right).
        gs = fig.add_gridspec(2, 2)
        ax_over = fig.add_subplot(gs[0, :])
        ax_det = fig.add_subplot(gs[1, 0])
        ax_rest = fig.add_subplot(gs[1, 1])
        self._plot_overview(ax_over)
        self._plot_detail(ax_det)
        self._plot_rest(ax_rest)
        self.panel.refresh()

    def _plot_overview(self, ax):
        """Whole-cycle voltage profile: voltage vs time in HOURS (normalised to the
        cycle start), drawn as plain lines - blue for charge, red for discharge.
        V0 points are marked and the selected pulse is highlighted."""
        cyc = self._current_cycle()
        cd = self.df_raw[self.df_raw["cycle"] == cyc].copy()
        if len(cd) == 0:
            return

        # Normalise time to the cycle start (first non-zero current), in hours.
        nz = cd[cd["I/mA"] != 0]
        t_start = nz["t/s"].iloc[0] if len(nz) else cd["t/s"].min()

        def to_h(t):
            return (t - t_start) / 3600.0

        # Assign every sample - including the rests (I=0) - to the surrounding
        # half-cycle by forward/back-filling the current sign, then draw each
        # contiguous charge/discharge run as one continuous line (blue / red).
        cd = cd.reset_index(drop=True)
        th = to_h(cd["t/s"].to_numpy())
        volt = cd["E/V"].to_numpy()
        sign = pd.Series(np.sign(cd["I/mA"].to_numpy())).replace(0, np.nan).ffill().bfill()
        if sign.notna().any():
            ph = sign.to_numpy()
            bounds = np.concatenate(([0], np.where(np.diff(ph) != 0)[0] + 1, [len(ph)]))
            charge_lbl = discharge_lbl = False
            for a, b in zip(bounds[:-1], bounds[1:]):
                seg = slice(max(a - 1, 0), b)   # overlap one point so runs join seamlessly
                is_charge = ph[a] > 0
                label = None
                if is_charge and not charge_lbl:
                    label, charge_lbl = "Charge", True
                elif not is_charge and not discharge_lbl:
                    label, discharge_lbl = "Discharge", True
                ax.plot(th[seg], volt[seg],
                        color=(C_CHARGE if is_charge else C_DISCHARGE),
                        linewidth=1.5, label=label)
        else:
            ax.plot(th, volt, color=C_REST, linewidth=1.5, label="Rest")

        # Every V0 of the selected phase (t0 normalised the same way)
        data = self._phase_data()
        if data is not None and len(data) and "V0" in data.columns:
            v = data.dropna(subset=["V0", "t0"])
            if len(v):
                ax.scatter(to_h(v["t0"]), v["V0"], color=C_V0, s=20, edgecolor="black",
                           linewidth=0.5, zorder=5, label="V0")

        # Highlight the selected pulse ("current position")
        pdf = self._current_pulse_df()
        if pdf is not None:
            ax.axvspan(to_h(pdf["t/s"].min()), to_h(pdf["t/s"].max()),
                       color=theme.ACCENT, alpha=0.15, zorder=1)

        ax.set_xlabel("Time (h)", fontsize=12)
        ax.set_ylabel("Voltage (V)", fontsize=12)
        ax.grid(True, alpha=0.3)
        ax.set_title(f"Cycle {cyc} overview", fontsize=12, fontweight="bold")
        leg = ax.legend(loc="best", fontsize=9)
        if leg is not None:
            leg.set_draggable(True)
            leg.set_zorder(100)
            leg.get_frame().set_facecolor("white")
            leg.get_frame().set_alpha(0.9)
            leg.get_frame().set_edgecolor("black")
        self._status(f"Cycle {cyc}: {len(self.pulse_list)} {self.phase} pulse(s)")

    def _shade_zero_current(self, ax, pdf):
        """Light shading over the rest region(s) where I = 0, labelled once."""
        t = pdf["t/s"].to_numpy()
        cur = pdf["I/mA"].to_numpy()
        zero = (cur == 0)
        if not zero.any():
            return
        idx = np.where(zero)[0]
        groups = np.split(idx, np.where(np.diff(idx) != 1)[0] + 1)
        labelled = False
        for g in groups:
            lo, hi = t[g[0]], t[g[-1]]
            if hi <= lo:                      # single zero sample: extend to the next point
                nxt = g[-1] + 1
                if nxt >= len(t):
                    continue
                hi = t[nxt]
            ax.axvspan(lo, hi, color=theme.FAINT, alpha=0.18, zorder=0,
                       label=("Rest (I=0)" if not labelled else "_nolegend_"))
            labelled = True

    def _plot_detail(self, ax):
        pdf = self._current_pulse_df()
        color = C_CHARGE if self.phase == CHARGE else C_DISCHARGE
        if pdf is None:
            ax.text(0.5, 0.5, f"No {self.phase} pulse selected",
                    ha="center", va="center", transform=ax.transAxes, color=theme.MUTED)
            ax.set_xticks([])
            ax.set_yticks([])
            return

        self._shade_zero_current(ax, pdf)
        ax.plot(pdf["t/s"], pdf["E/V"], color=color, linewidth=1.8, label="Voltage")
        ax.set_xlabel("Time (s)")
        ax.set_ylabel("Voltage (V)", color=color)
        ax.tick_params(axis="y", labelcolor=color)

        ax2 = ax.twinx()
        ax2.plot(pdf["t/s"], pdf["I/mA"], color=C_CURRENT, linewidth=1.3, linestyle="--",
                 alpha=0.8, label="Current")
        ax2.set_ylabel("Current (mA)", color=C_CURRENT)
        ax2.tick_params(axis="y", labelcolor=C_CURRENT)

        if "V0" in pdf.columns and "t0" in pdf.columns:
            v = pdf.dropna(subset=["V0", "t0"])
            if len(v):
                ax.scatter(v["t0"].iloc[0], v["V0"].iloc[0], color=C_V0, s=55,
                           edgecolor="black", linewidth=0.8, zorder=10, label="V0")

        ax.grid(True, alpha=0.3)
        pn = self.pulse_list[self.pulse_idx]
        ax.set_title(f"{self.phase.capitalize()} pulse {pn}", fontweight="bold")

        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax2.get_legend_handles_labels()
        leg = ax.legend(h1 + h2, l1 + l2, loc="best", fontsize=8)
        if leg is not None:
            leg.set_draggable(True)

    def _plot_rest(self, ax):
        """Zoom on the selected pulse's rest-period relaxation: voltage vs time
        after the current switches off, with V0/t0 marked. This is the raw
        segment the ΔV-vs-√t regression (Regression section) is computed on."""
        pdf = self._current_pulse_df()
        color = C_CHARGE if self.phase == CHARGE else C_DISCHARGE
        if pdf is None:
            ax.text(0.5, 0.5, f"No {self.phase} pulse selected", ha="center",
                    va="center", transform=ax.transAxes, color=theme.MUTED)
            ax.set_xticks([])
            ax.set_yticks([])
            return

        rest = pdf[pdf["I/mA"] == 0]
        if len(rest) == 0:
            ax.text(0.5, 0.5, "No rest period", ha="center", va="center",
                    transform=ax.transAxes, color=theme.MUTED)
            ax.set_xticks([])
            ax.set_yticks([])
            return

        # Measure relaxation time from t0 (last active sample before the rest).
        t0 = v0 = None
        if "V0" in pdf.columns and "t0" in pdf.columns:
            vt = pdf.dropna(subset=["V0", "t0"])
            if len(vt):
                t0 = float(vt["t0"].iloc[0])
                v0 = float(vt["V0"].iloc[0])
        t = rest["t/s"].to_numpy()
        t_ref = t0 if t0 is not None else t[0]
        ax.plot(t - t_ref, rest["E/V"].to_numpy(), color=color, marker="o",
                markersize=3, linewidth=1.5, label="Rest voltage")
        if v0 is not None:
            ax.plot(0.0, v0, "o", color=C_V0, markersize=8, markeredgecolor="black",
                    markeredgewidth=0.8, zorder=10, label="V0")

        ax.set_xlabel("Time since interruption (s)")
        ax.set_ylabel("Voltage (V)", color=color)
        ax.tick_params(axis="y", labelcolor=color)
        ax.grid(True, alpha=0.3)
        dur = (t[-1] - t[0]) if len(t) > 1 else 0.0
        pn = self.pulse_list[self.pulse_idx]
        ax.set_title(f"{self.phase.capitalize()} pulse {pn} — rest ({dur:.1f} s)",
                     fontweight="bold", fontsize=11)
        leg = ax.legend(loc="best", fontsize=8)
        if leg is not None:
            leg.set_draggable(True)

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
        stem = os.path.splitext(self.sel_file or "pyICI_pulse")[0]
        path = filedialog.asksaveasfilename(
            title="Export pulse figure", defaultextension=f".{fmt}",
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
