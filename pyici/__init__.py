"""pyICI — public API for Intermittent Current Interruption (ICI) analysis.

This is the library front door. Import what you need straight from ``pyici``::

    import pyici

    data = pyici.run_data_analysis("folder", "cell01.txt")   # or pyici.load_data(...)
    rk   = pyici.compute_R_k_for_cycles(                      # or pyici.compute_rk(...)
        data.df_raw, data.cycle_list, "charge",
    )

The computation lives in the ``analysis`` modules (unchanged); this namespace
just re-exports the stable, documented entry points under clean names, so you
never have to import ``analysis.*`` directly. The GUI is a separate layer and is
not imported here, so ``import pyici`` works headless (no tkinter needed).

Friendly aliases are provided for the three most common operations:
``load_data`` (= ``run_data_analysis``), ``segment_pulses``
(= ``analyze_cycle_pulses``) and ``compute_rk`` (= ``compute_R_k_for_cycles``).
"""
from importlib.metadata import PackageNotFoundError, version as _version

try:
    __version__ = _version("pyici")
except PackageNotFoundError:          # running from a source tree without install
    __version__ = "0.0.0+unknown"

# ---- loading --------------------------------------------------------------
from analysis.data_loader import run_data_analysis, peek_columns

# ---- classification / capacity -------------------------------------------
from analysis.phase_classifier import classify_charge_discharge, calculate_capacity

# ---- pulse segmentation ---------------------------------------------------
from analysis.pulse_analyzer import analyze_cycle_pulses

# ---- per-pulse regression (ΔV vs √t) -------------------------------------
from analysis.regression_analyzer import (
    load_cycle_for_regression,
    compute_single_pulse_regression,
    resolve_window,
    DEFAULT_TIME_START,
    DEFAULT_TIME_END,
    DEFAULT_INDEX_START,
    DEFAULT_INDEX_END,
)

# ---- resistances R and k --------------------------------------------------
from analysis.kinetic_analyzer import (
    compute_R_k_for_cycle,
    compute_R_k_for_cycles,
    export_R_k_results,
)

# ---- friendly aliases -----------------------------------------------------
load_data = run_data_analysis
segment_pulses = analyze_cycle_pulses
compute_rk = compute_R_k_for_cycles

__all__ = [
    "__version__",
    # loading
    "run_data_analysis", "load_data", "peek_columns",
    # classification / capacity
    "classify_charge_discharge", "calculate_capacity",
    # pulse segmentation
    "analyze_cycle_pulses", "segment_pulses",
    # regression
    "load_cycle_for_regression", "compute_single_pulse_regression", "resolve_window",
    "DEFAULT_TIME_START", "DEFAULT_TIME_END",
    "DEFAULT_INDEX_START", "DEFAULT_INDEX_END",
    # resistances
    "compute_R_k_for_cycle", "compute_R_k_for_cycles", "compute_rk",
    "export_R_k_results",
]
