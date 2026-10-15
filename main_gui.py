#!/usr/bin/env python3
"""pyICI — application entry point (customtkinter GUI).

The app shell: a header, a top navigation (the four analysis sections), a content
area split into a left controls column and a right plot area, and a status bar.
Each section lives in ``gui/sections/`` and is thin presentation that calls the
pure ``analysis`` layer.

Sections:
  1. Data loading       — load data, see cycles, capacity / specific-capacity plots
  2. Pulse verification — cycle overview + pulse detail + rest-period zoom
  3. Regression         — charge/discharge ΔV-vs-√t regression + R² across cycles
  4. Kinetic analysis   — R and k vs voltage / capacity for charge / discharge

Run with:
    python main_gui.py
"""
import os
import sys

# Make the project importable when launched from anywhere.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

import customtkinter as ctk

from gui import theme
from gui.sections.data_loading import DataLoadingSection
from gui.sections.pulse import PulseCheckSection
from gui.sections.regression import RegressionSection
from gui.sections.kinetics import KineticsSection

# (key, display label) for each analysis section, in order.
SECTIONS = [
    ("data",       "Data loading"),
    ("pulse",      "Pulse verification"),
    ("regression", "Regression"),
    ("kinetics",   "Kinetic analysis"),
]

APP_VERSION = "2.0.0-dev"


class PyICIApp(ctk.CTk):
    """The new pyICI application window (shell)."""

    def __init__(self):
        super().__init__()
        self.title("pyICI")
        self.geometry("1400x900")
        self.minsize(1100, 700)
        self.configure(fg_color=theme.BG)

        self.active_section = SECTIONS[0][0]
        self.section_frames = {}
        self.nav_buttons = {}

        self._build_header()
        self._build_nav()
        self._build_status()      # packed to the bottom before the content fills the middle
        self._build_content()
        self._show_section(self.active_section)

    # ---- header -----------------------------------------------------------
    def _build_header(self):
        header = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=0, height=78)
        header.pack(side="top", fill="x")
        header.pack_propagate(False)

        titles = ctk.CTkFrame(header, fg_color="transparent")
        titles.pack(side="left", padx=18, pady=8)
        ctk.CTkLabel(titles, text="pyICI", font=theme.font_sans(16, "bold"),
                     text_color=theme.TEXT, anchor="w").pack(anchor="w")
        ctk.CTkLabel(titles, text="Intermittent Current Interruption Analysis",
                     font=theme.font_sans(11), text_color=theme.MUTED, anchor="w").pack(anchor="w")

        ctk.CTkLabel(header, text=f"v{APP_VERSION}", font=theme.font_mono(11),
                     text_color=theme.MUTED, fg_color=theme.BG, corner_radius=theme.RADIUS_PILL,
                     width=104, height=28).pack(side="right", padx=18)

    # ---- top navigation (section switcher) --------------------------------
    def _build_nav(self):
        nav = ctk.CTkFrame(self, fg_color=theme.SURFACE, corner_radius=0, height=60)
        nav.pack(side="top", fill="x")
        nav.pack_propagate(False)

        inner = ctk.CTkFrame(nav, fg_color="transparent")
        inner.pack(side="left", padx=12, pady=8)
        for i, (key, label) in enumerate(SECTIONS):
            btn = ctk.CTkButton(
                inner, text=f"{i + 1}   {label}", height=44, width=210,
                corner_radius=22, font=theme.font_sans(15, "bold"),   # #2 bigger + bold
                fg_color=theme.BG, text_color=theme.MUTED,
                hover_color=theme.ACCENT_TINT, border_width=0,
                command=lambda k=key: self._show_section(k))
            btn.pack(side="left", padx=4)
            self.nav_buttons[key] = btn

    # ---- content area (one frame per section, shown on demand) -------------
    def _build_content(self):
        self.content = ctk.CTkFrame(self, fg_color="transparent")
        self.content.pack(side="top", fill="both", expand=True, padx=theme.GAP, pady=theme.GAP)
        for key, label in SECTIONS:
            self.section_frames[key] = self._make_section(key, label)

    def _make_section(self, key, label):
        """Build a section frame. 'data' is the real Data-loading section; the
        others are placeholders (left controls card + right plot card) for now."""
        if key == "data":
            return DataLoadingSection(self.content, self)
        if key == "pulse":
            return PulseCheckSection(self.content, self)
        if key == "regression":
            return RegressionSection(self.content, self)
        if key == "kinetics":
            return KineticsSection(self.content, self)

        frame = ctk.CTkFrame(self.content, fg_color="transparent")
        controls_card, controls_body = theme.card(frame, f"{label} - controls", width=320)
        controls_card.pack(side="left", fill="y", padx=(0, theme.GAP))
        controls_card.pack_propagate(False)
        ctk.CTkLabel(controls_body, text="Controls will go here",
                     font=theme.font_sans(13), text_color=theme.MUTED,
                     anchor="w", justify="left").pack(anchor="w", pady=6)

        plot_card, plot_body = theme.card(frame, f"{label} - plots")
        plot_card.pack(side="left", fill="both", expand=True)
        ctk.CTkLabel(plot_body, text="Plot area", font=theme.font_sans(14),
                     text_color=theme.FAINT).pack(expand=True)
        return frame

    # ---- status bar -------------------------------------------------------
    def _build_status(self):
        self.status = ctk.CTkLabel(self, text="Ready", font=theme.font_mono(11),
                                   text_color=theme.MUTED, anchor="w")
        self.status.pack(side="bottom", fill="x", padx=theme.GAP, pady=(0, 4))

    def set_status(self, message):
        self.status.configure(text=message)

    # ---- section switching ------------------------------------------------
    def _show_section(self, key):
        for frame in self.section_frames.values():
            frame.pack_forget()
        frame = self.section_frames[key]
        frame.pack(fill="both", expand=True)
        self.active_section = key
        self._refresh_nav()
        on_show = getattr(frame, "on_show", None)
        if callable(on_show):
            on_show()

    def _refresh_nav(self):
        for key, btn in self.nav_buttons.items():
            if key == self.active_section:
                btn.configure(fg_color=theme.ACCENT, hover_color=theme.ACCENT_HOVER,
                              text_color="#ffffff")
            else:
                btn.configure(fg_color=theme.BG, hover_color=theme.ACCENT_TINT,
                              text_color=theme.MUTED)


def main():
    theme.apply_theme()           # light appearance + base colour theme
    app = PyICIApp()
    app.mainloop()


if __name__ == "__main__":
    main()
