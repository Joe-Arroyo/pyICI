"""Shared visual theme for the pyICI GUI.

Single source of truth for the interface's colors, fonts, radii and spacing,
derived from the modernized-GUI mockup (teal accent, IBM Plex type, white cards
on a grey-blue ground). The GUI tabs import these tokens so the look stays
consistent, and ``apply_theme()`` is called once at startup from ``main_gui``.

This is the foundation of the customtkinter restyle: it does not itself change
any widget — tabs opt in by using the tokens below and customtkinter widgets.
Kept import-safe (no Tk root required at import time); the font helpers query
available families lazily, when first called while building the UI.
"""
import customtkinter as ctk

# ---- Palette (hex, from the mockup) ---------------------------------------
ACCENT       = "#0f766e"   # teal — primary buttons, active step, fit line, R/k values, links
ACCENT_HOVER = "#0b5a53"   # teal, hover/pressed
ACCENT_TINT  = "#d6efec"   # teal wash — active-step chip background
BG           = "#eef1f3"   # app background (grey-blue)
SURFACE      = "#ffffff"   # cards, header, footer, inputs
BORDER       = "#dde3e7"   # card / input borders, dividers
TEXT         = "#182226"   # primary text, data points
MUTED        = "#5b6a72"   # labels, secondary text, status bar
FAINT        = "#9aa7ae"   # disabled steps, axis ticks, uncertainty

# Fit-quality signalling (used from stage 5c onward). Distinct in LIGHTNESS,
# not hue alone, so they read for colour-vision-deficient users.
GOOD         = "#15803d"   # green
GOOD_BG      = "#dcefe1"
GOOD_BORDER  = "#bfe0cb"
MARGINAL     = "#b45309"   # amber
POOR         = "#b91c1c"   # red

# ---- Shape & spacing (px) --------------------------------------------------
RADIUS_CARD  = 12
RADIUS_INPUT = 8
RADIUS_PILL  = 999
PAD_CARD     = 16
GAP          = 14

# ---- Fonts -----------------------------------------------------------------
# IBM Plex if installed, else a graceful per-platform fallback. Matching the
# look exactly across machines (bundling the OFL font files) is a later option.
_SANS_PREFS = ("IBM Plex Sans", "Segoe UI", "Helvetica Neue", "Cantarell",
               "DejaVu Sans", "sans-serif")
_MONO_PREFS = ("IBM Plex Mono", "Cascadia Mono", "Consolas",
               "DejaVu Sans Mono", "monospace")

_sans_family = None
_mono_family = None


def _first_available(preferred):
    """Return the first installed family in ``preferred`` (else its first name).

    Needs a Tk root to query the font database; callers run it lazily while
    building the UI, by which point the root exists. Falls back safely if the
    query is unavailable for any reason.
    """
    try:
        import tkinter.font as tkfont
        available = set(tkfont.families())
        for name in preferred:
            if name in available:
                return name
    except Exception:
        pass
    return preferred[0]


def font_sans(size=13, weight="normal"):
    """A CTkFont in the UI sans family (IBM Plex Sans or fallback)."""
    global _sans_family
    if _sans_family is None:
        _sans_family = _first_available(_SANS_PREFS)
    return ctk.CTkFont(family=_sans_family, size=size, weight=weight)


def font_mono(size=13, weight="normal"):
    """A CTkFont in the monospace family (IBM Plex Mono or fallback).

    Used for numeric readouts, R/k values, axis ticks and the status bar.
    """
    global _mono_family
    if _mono_family is None:
        _mono_family = _first_available(_MONO_PREFS)
    return ctk.CTkFont(family=_mono_family, size=size, weight=weight)


def apply_theme():
    """Initialise customtkinter's appearance for pyICI. Call once at startup.

    Sets light appearance and a base colour theme; exact accent colours are
    applied per widget via the tokens above as tabs are restyled.
    """
    ctk.set_appearance_mode("light")
    ctk.set_default_color_theme("green")
