# Changelog

All notable changes to pyICI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [2.2.0] - 2026-10-28

### Added
- **Automatic fit-window detection in the Regression section.** Switching the
  fit mode to **Auto** fits, in one step, the optimal ΔV-vs-√t regression window
  for every pulse of every cycle (both phases). For each pulse it scans candidate
  windows and keeps the one with the smallest relative error on *R* and *k* that
  still passes two physical gates — statistical linearity (adjusted R²) and an
  edge-curvature check that rejects windows reaching past the √t-linear region —
  and flags any pulse it cannot fit cleanly (`low_confidence`, `edge_curvature`,
  `poor_fit`, `too_few_points`, non-physical *R*/*k*). Results appear as a
  reviewable suggestion; **Save** commits them per file, and flagged pulses are
  listed in the status bar and marked on each pulse. The thresholds (skip-first,
  min points, min adjusted R², edge points) are adjustable in a collapsible
  "Auto fit options" panel. The window scan is vectorised and numerically
  identical to the canonical single-pulse fit, so it changes no results (the full
  auto-fit over the 10-cycle example runs in well under a second). The feature is
  inspired by the "Estimate optimal window" tool in
  [ICI Studio](https://github.com/mjlacey/ici_studio) (Matthew J. Lacey), adapting
  its idea of scoring candidate ΔV-vs-√t windows by linearity (adjusted R²) and
  edge-curvature diagnostics; pyICI estimates a window per pulse rather than one
  global window.
- **R & k analysis — include the other phase.** A checkbox overlays the opposite
  phase (charge with discharge, or vice versa) on the R and k plots for direct
  comparison; its label follows the selected phase.

### Changed
- Renamed the **Kinetic analysis** section to **R & k analysis** throughout the
  application — the section label, its plot titles, and the analysis module
  (`analysis.rk_analyzer`, formerly `analysis.kinetic_analyzer`). The ICI outputs
  are an internal resistance *R* and a diffusion resistance coefficient *k* (a
  resistance and a mass-transport term), so "kinetics" — which denotes
  reaction-rate behaviour — did not accurately describe them. No change to any
  computed values or exported columns, and the public `pyici` API is unchanged
  (`import pyici` still exposes `compute_rk` and the other entry points).
- **Regression controls reworked.** The Start/End boxes now always show the
  window actually in effect for the current pulse (saved, auto-suggested, or
  default), not only the last-saved one; the fit readout (window / slope /
  intercept / R² / flags) sits directly under the window entry so it updates
  where you type; the R²-plot axis-limit controls moved into a collapsible panel;
  and the Manual and (collapsed) Auto controls share the same height so switching
  between them doesn't shift the layout.
- Controls columns now show a scrollbar only when their content doesn't fit,
  consistently across all four sections.

### Fixed
- A saved or auto-suggested regression window is no longer lost when switching
  the window units between index and time, and auto-fit now works in time mode
  as well as index.

## [2.1.0] - 2026-10-19

### Added
- **Public `pyici` API for scripting.** The analysis can now be used as a library:
  `import pyici` exposes the stable entry points (loading, pulse segmentation,
  per-pulse regression, R/k) under clean names, with friendly aliases
  (`load_data`, `segment_pulses`, `compute_rk`) and `pyici.__version__`. No GUI /
  tkinter is imported, so it works headless. See the "Use as a library" section of
  the README. (The computation lives unchanged in the `analysis` modules; this is a
  thin, documented front door, covered by a public-API contract test.)
- **Published on PyPI** as `ici-analysis` — install with `pip install ici-analysis`
  (then `import pyici`, or launch the `pyici` GUI). First PyPI release of pyICI.

## [2.0.0] - 2026-10-16

### Added
- **New customtkinter interface — now the application** (`python main_gui.py`, or
  the `pyici` command). It replaces the previous tkinter tab GUI; the sections now
  live in `gui/sections/` and call the same pure analysis layer, so R/k results
  are identical. Four sections (Data loading, Pulse verification, Regression,
  Kinetic analysis) in a controls-left / plots-right layout.
  - **Multiple files**: load several datasets, choose the file per section
    independently, and overlay files for comparison (R & k in Kinetic analysis;
    voltage / capacity in Data loading).
  - **Data loading**: voltage-vs-time and capacity / specific-capacity views
    (all cycles, a subset, or a single cycle, with an optional current subplot),
    with a CSV export matching the previous Classification export.
  - **Pulse verification**: step through a cycle's pulses (charge or discharge)
    with a whole-cycle overview that highlights the selected pulse, the pulse's
    voltage + current detail, and a zoom on its rest-period relaxation with V0
    marked — to check that the ICI pulses are segmented correctly.
  - **Regression**: apply a fit window to a single pulse, a whole cycle, or all
    cycles (preview), and Save to persist it per file; an "Overall check" of R²
    across all cycles; R and k shown on the fit plot; a secondary time axis; and
    axis-limit controls for the R² plot.
  - **Kinetic analysis**: R and k vs voltage / capacity / specific capacity,
    using the per-pulse windows carried over from Regression; axis-limit
    controls; CSV export per phase (and per file when overlaid) in the
    established column layout; export the R plot, the k plot, or both.
  - Consistent blue (charge) / red (discharge) colour scheme that darkens with
    cycle number across the capacity, regression and kinetic plots.
  - A shared visual theme (teal accent, bold section labels, consistent
    dropdowns and controls, and controls columns whose scrollbar appears only
    when needed), so the four sections look and behave the same.

### Fixed
- Data files saved in non-UTF-8 text encodings (e.g. Windows-1252 / Latin-1, as
  exported by some cyclers) now load correctly instead of failing with a decoding
  error — the loader detects the file's encoding automatically.
- Exporting a plot no longer strips the titles from the on-screen figure. (The
  Classification tab's figure export previously blanked the plot titles without
  restoring them.)
- Embedded plots now lay out correctly on first render. Previously titles, axis
  labels and the legend could overlap until you navigated, because the figure was
  laid out before it had been sized to the panel; the shared plot panel now uses
  matplotlib's constrained layout, which re-fits on every draw (and handles the
  kinetic colorbar natively).

### Removed
- Removed the non-functional "Max Rest (s)" field from the Data tab. It was shown
  and validated but never actually applied; the maximum valid rest duration
  stays fixed at 1800 s.
- The legacy tkinter tab GUI (the five `*_tab.py` modules and the old
  `main_gui.py`) has been removed. The customtkinter interface above is now the
  sole GUI and entry point.

### Changed
- Internal: the maximum-rest-duration constant now has a single definition shared
  across the analysis modules (previously duplicated in four files). No change to
  results.
- Internal: one shared helper (`kinetic_analyzer.rk_result_rows`) now builds the
  R/k CSV rows for both the batch export and the new GUI, so the exported column
  layout has a single definition. No change to the exported values.
- Internal (no change to results or exported values): began the GUI modernization.
  The matplotlib plumbing and figure-export code that had been copy-pasted across
  all five tabs were consolidated into two shared components
  (`gui/components/plot_panel.py` and `gui/components/export_helper.py`), and the
  status bar now refreshes when the data changes (event-driven) instead of polling
  on a 1-second timer. `customtkinter` was added as a dependency as groundwork for
  the forthcoming interface restyle.
- Internal (no change to results): the GUI sections moved from top-level modules
  into the `gui/sections/` package, and `main_gui.py` is now the customtkinter
  entry point. Dropped the now-unused per-subplot export helper
  (`export_single_axis`) and a few unused imports left over from the old tabs.
- **Performance (no change to results):** the pulse-segmentation hot path was
  vectorized — `assign_valid_pulses` (element-by-element → run-based numpy),
  `compute_V0_t0` and `get_pre_pulse_currents` (per-pulse frame re-filtering →
  single pass + mapped broadcast). The full R/k pipeline over the 10-cycle example
  is ~2.9× faster (≈1.93 s → ≈0.67 s), with byte-for-byte identical output verified
  against the originals and pinned by new known-answer tests.

## [1.4.0] - 2026-10-07

### Added
- Selectable regression window in the Regression tab: a "Use time window for
  regression" checkbox switches the Start/End controls between **index** (sample
  points, 1-based) and **time** (seconds). The default is index points 2–10, and
  the chosen window is applied consistently to the interactive fits and the batch
  R/k export.
- The selected regression window is now highlighted (grey band) on the
  ΔV-vs-√t plot and updates live as the Start/End values change.
- R/k exports now record the window used for each pulse: new columns
  `Window_Mode`, `Window_Start`, `Window_End`, and `N_points` (the number of
  samples actually fit).
- Automated tests that run the complete analysis on the example files in `data/`
  and check that the computed R and k values stay the same, so any change that
  accidentally alters the results is caught automatically (locally and in CI).
  These complement the existing tests that verify the math on hand-checkable inputs.
- API documentation (docstrings) for the R/k extraction functions in
  `analysis/kinetic_analyzer`.

### Changed
- The default regression window is now the same everywhere — index points 2–10
  (1-based, inclusive) — for both the Regression tab and the batch R/k export.
  Previously the tab defaulted to a 0.1–1.0 s time window while the export used a
  slightly different index window, so the on-screen fit could differ from the
  exported value for a pulse that had not been hand-tuned. **As a result, R and k
  for un-tuned pulses change slightly compared with 1.3.x.** The fitting method is
  unchanged (ΔV vs √t, R = −intercept/I, k = −slope/I, covariance-based error
  propagation) — only *which* samples are fit by default. Hand-tuned pulses are
  unaffected.
- Internal refactor (no change to results): the three duplicated algorithm
  implementations (`assign_valid_pulses`, `compute_V0_t0`,
  `classify_charge_discharge`) were consolidated to one implementation each,
  imported where needed, so the Pulse-visualization tab and the R/k pipeline can
  no longer drift apart.

### Fixed
- Regression on a rest-period window with fewer than 3 points (or with zero √t
  spread) now returns NaN instead of silently producing `inf`/`nan` error bars on
  R and k. The residual variance `s2 = Σr²/(n−2)` divided by zero at n = 2; the fit
  is now guarded so degenerate windows can't yield meaningless error bars.

## [1.3.0] - 2026-09-29

### Added
- The analysis package (`analysis/`) can now be used as a library, independently
  of the GUI: each module takes its inputs as arguments and returns results
  (e.g. `run_data_analysis`, `load_cycle_for_regression`, `analyze_cycle_pulses`,
  `compute_R_k_for_cycle`), so ICI processing can be scripted and unit-tested
  without launching tkinter. The analysis core is now covered by an automated
  headless test suite.

### Changed
- Internal refactor (no change to application behaviour): `regression_analyzer` no
  longer holds analysis data in module-level globals. `load_cycle_for_regression`
  now takes the data as arguments and returns a result object, so the regression
  analysis can be run and tested independently of the GUI.
- Internal refactor (no change to application behaviour): `kinetic_analyzer` no
  longer holds analysis data in module-level globals. `compute_R_k_for_cycle`,
  `compute_R_k_for_cycles`, and `export_R_k_results` now take the data as an
  argument, so R / k extraction can be run and tested independently of the GUI.
- Internal refactor (no change to application behaviour): `pulse_analyzer` no
  longer holds analysis data in module-level globals. `analyze_cycle_pulses` now
  takes the data as an argument and returns a result object, so pulse analysis
  can be run and tested independently of the GUI. Removed dead notebook-era
  plotting helpers (`plot_pulse`, `plot_rest_period`, `plot_cycle_pulse_overview`,
  `plot_individual_pulse_detailed`) that the GUI never called.
- Internal refactor (no change to application behaviour): `data_loader` no longer
  holds analysis data in module-level globals. `run_data_analysis` now takes its
  parameters as arguments and returns a result object (df_raw, plot_data,
  ici_starts, cycle_list, data_format) instead of setting module globals. Removed
  dead notebook/console helpers (`select_data_file`, `get_analysis_parameters`,
  `list_available_files`, `console_cycle_explorer`) and standalone plotting helpers
  (`create_overview_plot`, `plot_cycle`). This completes the de-globalization of
  the analysis core — every analysis module is now usable and testable without the GUI.

### Removed
- Internal cleanup: removed leftover Jupyter/CLI code from the `analysis` modules
  — the `run_cell1`/`run_cell2`/`run_cell3` wrappers, the interactive `console_*`
  interfaces, and the standalone `run_*` launchers (`run_phase_classification`,
  `run_pulse_analysis`, `run_regression_analysis`, `run_kinetic_analysis`), plus
  the `__main__` blocks. Also dropped the now-unused module-level globals in
  `phase_classifier` and `regression_analyzer`. No change to application behaviour.
- Internal cleanup: removed unused plotting/export helpers
  (`plot_all_cycles_r2_overview`, `export_regression_results`) from
  `regression_analyzer`.

## [1.2.0] - 2026-09-23

### Added
- `pyproject.toml`: pyICI is now installable with `pip install .` and provides a
  `pyici` command-line entry point to launch the GUI.
- Automated test suite (`pytest`) covering the analysis core — known-answer tests
  for the ΔV vs. √t regression and for R / k extraction with error propagation.
- `CITATION.cff` so the repository can be cited directly.
- `CODE_OF_CONDUCT.md` (Contributor Covenant).
- Issue templates for bug reports and feature requests.
- "Running the tests" section in `CONTRIBUTING.md`.

### Changed
- Installation now uses `pip install .` (dependencies declared in
  `pyproject.toml`); README updated accordingly.

### Removed
- Unused `ipywidgets` and `IPython` dependencies (leftovers from the notebook
  origin) removed from the code and `requirements.txt`.

## [1.1.0] - 2026-09-19

### Added
- **Automatic cycle detection from the current signal** for files that do not
  contain a cycle-number column. Cycles are identified from the charge /
  discharge pattern of the current: each point is classified as charge
  (`I > threshold`), discharge (`I < -threshold`) or rest (`|I| <= threshold`),
  current interruptions and constant-voltage tails are absorbed into the
  surrounding half-cycle, and a full cycle is defined as two consecutive
  half-cycles. The method is start-agnostic (works whether cycling begins on
  charge or discharge).
- **"Cycles" mode selector** in the Data tab (Analysis Parameters):
  - `auto` — detect cycles from the current signal when the file has no cycle
    column;
  - `file` — treat a file without a cycle column as a single cycle (previous
    behaviour).
- **Column-mapping dialog** for files with more than three columns. After
  loading such a file, a pop-up lets you assign each role (Time, Voltage,
  Current, Cycle number) to a column; columns left unassigned are ignored, and
  choosing "None" for the cycle role triggers automatic detection. The dialog is
  pre-filled from the column headers for a one-click confirmation on standard
  files.
- New helper functions in `analysis/data_loader.py`: `detect_cycles_from_current`,
  `peek_columns`, and `build_df_from_map`.

### Changed
- Cycle-structure processing (`detect_and_fix_cycle_structure`) now accepts a
  detection mode and data format, and derives cycles from the current signal
  when no cycle column is present.

### Notes
- With the default `Cycles = auto`, a three-column file containing several cycles
  is now split into them (1.0.0 reported it as one). Files with a cycle-number
  column are unaffected.

## [1.0.0]

### Added
- Initial release of pyICI: GUI-based analysis of Intermittent Current
  Interruption (ICI) data — data loading and visualisation, charge/discharge
  classification, current-interruption (pulse) detection, interactive
  ΔV vs. √t regression, and R / k resistance analysis with covariance-based
  error propagation. Supports single-cycle (3-column) and multi-cycle
  (4-column) input files.

[Unreleased]: https://github.com/Joe-Arroyo/pyICI/compare/v2.1.0...HEAD
[2.1.0]: https://github.com/Joe-Arroyo/pyICI/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.4.0...v2.0.0
[1.4.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.3.0...v1.4.0
[1.3.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Joe-Arroyo/pyICI/releases/tag/v1.0.0