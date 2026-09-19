# Changelog

All notable changes to pyICI are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.1.0]: https://github.com/Joe-Arroyo/pyICI/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/Joe-Arroyo/pyICI/releases/tag/v1.0.0