#!/usr/bin/env python3
"""Column-mapping dialog for the new pyICI GUI.

A small modal shown when a data file has an unrecognised column layout (not the
standard 3- or 4-column form). The user assigns which column is Time, Voltage,
Current and (optionally) Cycle; the choice feeds analysis.data_loader through its
``column_map`` argument. No analysis-layer code lives here - the loader already
does the real work (peek_columns / build_df_from_map / run_data_analysis).

Usage:
    dlg = ColumnMapDialog(parent, columns, filename="file.txt")
    parent.wait_window(dlg)
    col_map = dlg.result        # {'time','voltage','current','cycle'} or None
"""
import tkinter as tk

import customtkinter as ctk

from gui import theme

NONE_LABEL = "(none)"


def _guess(columns, keywords):
    """First column whose (lower-cased) name contains any of the keywords."""
    low = [str(c).lower() for c in columns]
    for kw in keywords:
        for i, name in enumerate(low):
            if kw in name:
                return columns[i]
    return None


class ColumnMapDialog(ctk.CTkToplevel):
    """Modal column picker. ``result`` is the column_map dict
    (``{'time','voltage','current','cycle'}``, cycle may be None) or None if
    the user cancelled."""

    def __init__(self, parent, columns, filename=""):
        super().__init__(parent)
        self.result = None
        columns = list(columns)

        self.title("Map columns")
        self.configure(fg_color=theme.BG)
        self.resizable(False, False)
        self.transient(parent)

        card, body = theme.card(self, None)
        card.pack(fill="both", expand=True, padx=14, pady=14)

        ctk.CTkLabel(body, text="Assign columns", font=theme.font_sans(15, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(fill="x")
        msg = ((f"{filename}\n" if filename else "") +
               "This file's column layout wasn't recognised. Choose which column is "
               "which - the rest are ignored.")
        ctk.CTkLabel(body, text=msg, font=theme.font_sans(12), text_color=theme.MUTED,
                     anchor="w", justify="left", wraplength=380).pack(fill="x", pady=(2, 10))

        g_time = _guess(columns, ["time", "t/s", "/s", "test_time"])
        g_volt = _guess(columns, ["ewe", "e/v", "volt", "potential", "voltage"])
        g_curr = _guess(columns, ["i/ma", "current", "<i>", "i /", "amp"])
        g_cyc = _guess(columns, ["cycle"])

        def pick(default, idx):
            return default or (columns[idx] if idx < len(columns) else columns[-1])

        self.time_var = tk.StringVar(value=pick(g_time, 0))
        self.volt_var = tk.StringVar(value=pick(g_volt, 1))
        self.curr_var = tk.StringVar(value=pick(g_curr, 2))
        self.cyc_var = tk.StringVar(value=g_cyc or NONE_LABEL)

        self._row(body, "Time *", self.time_var, columns)
        self._row(body, "Voltage *", self.volt_var, columns)
        self._row(body, "Current *", self.curr_var, columns)
        self._row(body, "Cycle", self.cyc_var, [NONE_LABEL] + columns)

        ctk.CTkLabel(body, text="*  required.  Cycle optional - if left (none), "
                     "cycles are detected from the current.", font=theme.font_sans(11),
                     text_color=theme.FAINT, anchor="w", justify="left",
                     wraplength=380).pack(fill="x", pady=(4, 0))

        self.err = ctk.CTkLabel(body, text="", font=theme.font_sans(11), text_color=theme.POOR,
                                anchor="w", justify="left", wraplength=380)
        self.err.pack(fill="x", pady=(6, 0))

        btns = ctk.CTkFrame(body, fg_color="transparent")
        btns.pack(fill="x", pady=(10, 0))
        ctk.CTkButton(btns, text="Cancel", command=self._cancel, fg_color=theme.SURFACE,
                      text_color=theme.MUTED, border_color=theme.BORDER, border_width=1,
                      hover_color=theme.BG, font=theme.font_sans(13), corner_radius=theme.RADIUS_INPUT
                      ).pack(side="left", fill="x", expand=True, padx=(0, 4))
        ctk.CTkButton(btns, text="Load", command=self._ok, fg_color=theme.ACCENT,
                      hover_color=theme.ACCENT_HOVER, font=theme.font_sans(13, "bold"),
                      corner_radius=theme.RADIUS_INPUT).pack(side="left", fill="x", expand=True,
                                                             padx=(4, 0))

        self.update_idletasks()
        try:
            self.geometry(f"+{parent.winfo_rootx() + 140}+{parent.winfo_rooty() + 120}")
        except Exception:
            pass
        self.protocol("WM_DELETE_WINDOW", self._cancel)
        self.bind("<Escape>", lambda e: self._cancel())
        self.after(50, self._grab)

    def _grab(self):
        try:
            self.lift()
            self.focus_force()
            self.grab_set()
        except Exception:
            pass

    def _row(self, parent, label, var, values):
        r = ctk.CTkFrame(parent, fg_color="transparent")
        r.pack(fill="x", pady=3)
        ctk.CTkLabel(r, text=label, font=theme.font_sans(13), text_color=theme.TEXT,
                     width=90, anchor="w").pack(side="left")
        ctk.CTkComboBox(r, variable=var, values=list(values), state="readonly",
                        fg_color=theme.SURFACE, text_color=theme.TEXT,
                        border_color=theme.BORDER, border_width=1,
                        button_color=theme.ACCENT, button_hover_color=theme.ACCENT_HOVER,
                        font=theme.font_sans(12), dropdown_font=theme.font_sans(12),
                        dropdown_fg_color=theme.SURFACE, dropdown_text_color=theme.TEXT,
                        dropdown_hover_color=theme.ACCENT_TINT, width=260
                        ).pack(side="left", fill="x", expand=True)

    def _ok(self):
        t, v, c = self.time_var.get(), self.volt_var.get(), self.curr_var.get()
        cyc = self.cyc_var.get()
        cycle = None if cyc == NONE_LABEL else cyc
        chosen = [t, v, c] + ([cycle] if cycle else [])
        if len(set(chosen)) != len(chosen):
            self.err.configure(text="Time, Voltage, Current (and Cycle if set) must be "
                                    "different columns.")
            return
        self.result = {"time": t, "voltage": v, "current": c, "cycle": cycle}
        self.grab_release()
        self.destroy()

    def _cancel(self):
        self.result = None
        self.grab_release()
        self.destroy()
