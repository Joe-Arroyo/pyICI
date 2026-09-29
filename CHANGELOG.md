# Changelog

All notable changes to pyICI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Joe-Arroyo/pyICI/compare/v1.3.0...HEAD
[1.3.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Joe-Arroyo/pyICI/releases/tag/v1.0.0