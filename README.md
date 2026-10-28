# pyICI

**Python-based Interactive Interface for Intermittent Current Interruption (ICI) data analysis for Battery Research**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

![tests](https://github.com/Joe-Arroyo/pyICI/actions/workflows/tests.yml/badge.svg)

## Overview

Intermittent current interruption (ICI) is an electrochemical technique used for the diagnostic analysis of battery systems. It involves introducing brief interruptions or pauses (1–10 seconds) into a constant current charge–discharge cycle and analyzing the voltage response during each interruption. The technique characterizes cell resistance using two parameters: the internal resistance (*R*, Ω), which captures Ohmic contributions, and the diffusion resistance coefficient (*k*, Ω s<sup>−1/2</sup>), which captures solid-state mass transport effects. Because ICI assumes a diffusion-controlled system, cycling must be performed at a comparatively slow rate of C/5 or lower. 

pyICI is a GUI-based analysis tool designed for researchers working with electrochemical ICI data. The tool facilitates the calculation of *R* and *k* from datasets with one or more cycles. 

Technical details of the ICI technique and associated literature can be found on the website of Dr. Matthew J. Lacey ([link here](https://lacey.se/projects/ici)), who developed the technique for routine battery analysis.

## Features

The GUI is organized into four sections:

- **Data loading & visualization**: Import and view cycling data — several files at once, with an optional overlay to compare them.
  - Automatic ICI cycle detection for three-column files; a column-mapping dialog for files with more columns
  - Charge / discharge classification, coloured by cycle
  - Plots: voltage vs time (all cycles, a subset, or a single cycle, with an optional current subplot) and voltage vs capacity / specific capacity
  - CSV export of the capacity data

- **Pulse verification**: Step through a cycle's current-interruption pulses to check they are segmented correctly.
  - Whole-cycle overview with the selected pulse highlighted
  - Per-pulse detail (voltage + current) and a zoom on the rest-period relaxation with *V₀* marked

- **Regression**: Interactively perform linear regression of the voltage vs $\sqrt{time}$ data during each ICI step.
  - User-defined fit window (time or index), applied to a single pulse, a whole cycle, or all cycles, and saved per file
  - Optional **automatic fit-window detection** that suggests the optimal window per pulse (both phases, every cycle at once) with quality flags — adapted from the "Estimate optimal window" feature of [ICI Studio](https://github.com/mjlacey/ici_studio)
  - Fit parameters (slope, intercept) evaluated with R<sup>2</sup>, using the covariance matrix for error propagation
  - The regression fit and an R<sup>2</sup>-across-pulses plot shown together, with axis-limit controls; an "Overall check" of R<sup>2</sup> across every cycle
  - *R* and *k* shown on the fit plot, and a secondary time axis on the ΔV-vs-√time plot

- **R & k analysis**: *R* and *k* calculation from the regression parameters.
  - $R = - \frac{intercept}{I}$ and $k = - \frac{slope}{I}$, with *I* the current before the interruption
  - *R* and *k* vs voltage, capacity, or specific capacity — coloured by cycle, with axis-limit controls and multi-file overlay
  - Covariance-based error bars
  - CSV export (per phase, and per file when overlaid) of *V*, *R*, *R_errors*, *k*, *k_errors* and *R*<sup>2</sup>, plus figure export (*R*, *k*, or both)

## Installation

pyICI requires **Python 3.9–3.13**. There are two ways to install it:

- **From PyPI** (recommended for most users) — one command, always the latest release.
- **From source** — clone the repository, for development or the latest unreleased code.

Both use Python's `tkinter` GUI toolkit; on some Linux distributions you install it
separately — see [A note on tkinter](#a-note-on-tkinter) below.

### Install from PyPI (recommended)

We recommend installing into a **virtual environment**, which keeps pyICI's
dependencies isolated from your other Python projects. You create it once; after
that you just reactivate it whenever you want to use pyICI.

**Windows (PowerShell):**
```powershell
python -m venv ici-env            # create the environment (once)
.\ici-env\Scripts\Activate.ps1   # activate it  ->  prompt shows (ici-env)
pip install ici-analysis          # install pyICI and its dependencies
pyici                             # launch the GUI
```
> If activation fails with *"running scripts is disabled"*, run
> `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` once in that window,
> then activate again.

**macOS / Linux:**
```bash
python3 -m venv ici-env           # create the environment (once)
source ici-env/bin/activate       # activate it  ->  prompt shows (ici-env)
pip install ici-analysis          # install pyICI and its dependencies
pyici                             # launch the GUI
```

To use pyICI again later, reopen a terminal, reactivate the same environment
(`.\ici-env\Scripts\Activate.ps1` on Windows, `source ici-env/bin/activate` on
macOS/Linux) and run `pyici`. Type `deactivate` to leave the environment; the
installation stays until you delete the `ici-env` folder.

> **If the `pyici` command isn't found** — this usually means pyICI was installed
> *outside* a virtual environment (for example with the Microsoft Store Python) and
> Python's scripts folder isn't on your `PATH`. Either install inside a virtual
> environment as shown above, or launch it directly with:
> ```bash
> python -m main_gui
> ```

> **Note on the name:** the PyPI distribution is called **`ici-analysis`** (so you
> `pip install ici-analysis`), but it still imports as `import pyici` and runs with
> the `pyici` command.

### Install from source

Use this for development, or to run the latest unreleased code.

```bash
# 1. clone the repository
git clone https://github.com/Joe-Arroyo/pyICI.git
cd pyICI

# 2. (recommended) create and activate a virtual environment
python -m venv venv
# Windows (PowerShell):  .\venv\Scripts\Activate.ps1
# macOS / Linux:         source venv/bin/activate

# 3. install in editable mode, then run
pip install -e .
pyici                  # or:  python main_gui.py
```

### A note on tkinter

pyICI's GUI is built on `tkinter`, which ships with Python on most systems. Some
platforms package it separately:
- **Windows**: included with the [python.org](https://www.python.org/downloads/) installer — no action needed.
- **macOS**: included with python.org Python. With Homebrew: `brew install python-tk`.
- **Ubuntu/Debian**: `sudo apt install python3-tk`
- **Fedora**: `sudo dnf install python3-tkinter`
- **CentOS/RHEL**: `sudo yum install python3-tkinter`

### Get started

See the [Tutorial](Tutorial.md) for a quick guide through pyICI's features.

---

## Use as a library

Beyond the GUI, pyICI can be scripted — useful for batch-processing many files or
feeding *R* / *k* into your own analysis. Install it from PyPI as **`ici-analysis`**
(the distribution name — it still imports as `pyici`), then import everything from
the top-level `pyici` package (no GUI / tkinter needed):

```python
import pyici

# 1. Load a data file  ->  df_raw, cycle_list, data_format, ...
data = pyici.run_data_analysis("path/to/folder", "cell01.txt")   # or pyici.load_data(...)

# 2. Inspect a cycle's current-interruption pulses
pulses = pyici.analyze_cycle_pulses(data.df_raw, cycle_num=1)     # or pyici.segment_pulses(...)

# 3. Compute R (Ω) and k (Ω·s^-1/2) for some cycles, charge phase,
#    using the default 0.1-1.0 s fit window
rk = pyici.compute_R_k_for_cycles(                                # or pyici.compute_rk(...)
    data.df_raw, data.cycle_list, "charge",
    "time", pyici.DEFAULT_TIME_START, pyici.DEFAULT_TIME_END, {}, mass_mg=0.0,
)
for cyc in rk:
    print(cyc["cycle"], cyc["R"], cyc["k"])

# 4. Or write the R/k results to CSV (charge and discharge in separate files)
pyici.export_R_k_results(data.df_raw, data.cycle_list, output_folder="exports")
```

`pyici.load_data`, `pyici.segment_pulses` and `pyici.compute_rk` are friendly
aliases for the three most common calls. `print(pyici.__version__)` reports the
installed version.

---

## AI Assistance
This project was developed with the assistance of Claude (Anthropic). All code has been reviewed and tested by the authors.
