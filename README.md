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
  - Fit parameters (slope, intercept) evaluated with R<sup>2</sup>, using the covariance matrix for error propagation
  - The regression fit and an R<sup>2</sup>-across-pulses plot shown together, with axis-limit controls; an "Overall check" of R<sup>2</sup> across every cycle
  - *R* and *k* shown on the fit plot, and a secondary time axis on the ΔV-vs-√time plot

- **Kinetic analysis**: *R* and *k* calculation from the regression parameters.
  - $R = - \frac{intercept}{I}$ and $k = - \frac{slope}{I}$, with *I* the current before the interruption
  - *R* and *k* vs voltage, capacity, or specific capacity — coloured by cycle, with axis-limit controls and multi-file overlay
  - Covariance-based error bars
  - CSV export (per phase, and per file when overlaid) of *V*, *R*, *R_errors*, *k*, *k_errors* and *R*<sup>2</sup>, plus figure export (*R*, *k*, or both)

## Installation

- Compatible with Python 3.9 - 3.13

### Step 1: **Install Python:**
**Windows:**
Download the installer from [python.org](https://www.python.org/downloads/) and run it. Make sure to check "Add Python to PATH" during installation.

**macOS:**
Download the installer from [python.org](https://www.python.org/downloads/), or install via Homebrew:
```bash
brew install python
```

**Linux:**
Python is usually pre-installed. Verify with:
```bash
python3 --version
```
If not installed, use your package manager:
```bash
# Ubuntu/Debian
sudo apt install python3 python3-pip
```

> **Note on tkinter**: pyICI uses `tkinter` for its GUI. Installation varies by platform:
> - **Windows**: included with the standard Python installer, no action needed
> - **macOS**: included with Python from python.org. If using Homebrew: `brew install python-tk`
> - **Ubuntu/Debian**: `sudo apt install python3-tk`
> - **Fedora**: `sudo dnf install python3-tkinter`
> - **CentOS/RHEL**: `sudo yum install python3-tkinter`

---

 ### Step 2: **Download the project:**
 Open a terminal (Command prompt on Windows, Terminal on macOS/Linux) and run:
```bash
# Clone the repository
git clone https://github.com/Joe-Arroyo/pyICI.git
cd pyICI
```
Or download the ZIP file and extract it.

---

### Step 3: Create a virtual environment (recommended)

Using a virtual environment keeps pyICI's dependencies isolated from other Python projects on your system.

**Windows (Command Prompt):**
```cmd
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

You should see `(venv)` in your terminal prompt. To deactivate later, run `deactivate`.

--- 

### Step4:. **Install Python dependencies:**
```bash
pip install -e .     # installs pyICI; the `pyici` command then launches the GUI
pyici                # GUI launches
python main_gui.py   # also works
```

### Step 5: Run pyICI

**Windows:**
```bash
python main_gui.py
```

**macOS / Linux:**
```bash
python3 main_gui.py
```

---

### Step 6: Get started

See the [Tutorial](Tutorial.md) for a quick guide through pyICI's features.

---

## Use as a library

Beyond the GUI, pyICI can be scripted — useful for batch-processing many files or
feeding *R* / *k* into your own analysis. Import everything from the top-level
`pyici` package (no GUI / tkinter needed):

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
