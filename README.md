# pyICI

**Python-based Interactive Interface for Intermitent Current Interruption (ICI) data analysis in battery research.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

## Overview
pyICI is a GUI-based analysis tool designed for researchers working with electrochemical ICI cycling data. The tool facilitates the calculation of the internal resistance (*R*) and the diffusion resistance coefficient (*k*) for large datasets with one or more cycles.

## Features

- **Data Loading & Visualization**: Import and view cycling raw data from multiple sources, as long as the formatting of the input datafile is respected
  - ICI starting point detection
  - Data visualization of individual and all cycles 
  - Plots available: Voltage vs time and current vs time (only in individual cycle visualization)
    
- **Classification**: Identify and classify cycles
  - Charge and discharge detection
  - Current interruption steps identification
  - Plots available: Voltage vs time and Voltage vs capacity 

- **Pulse Analysis**: Evaluate voltage during current interruption pulses

- **Regression Analysis**: Perform linear regression and adjust the coefficient of determiaation (*R<sup>2</sup>*)
  - User-defined regression analysis window (within the current interruption period)
  - Linear least-squares regression on the selected data window
  - Fit parameters: Slope, Intercept, and R<sup>2</sup>
  - Covariance matrix used for error propagation analysis
  - Independently adjust charge and discharge
  - Capability of adjusting one pulse, all pulses within one cycle, or all cycles at once
  - Side-by-side visualization for charge and discharge analysis
     
- **Kinetic Analysis**: *R* and *k* calculation from the regression analysis
  - R = -intercept / I, with I being the current before the interruption 
  - k = -slope / I, with I being the current before the interruption 
  - Error bars using the data from the covariance matrix
  - Cycle selection
  - Side-by-side visualization for charge and discharge
  - Data export of all values with uncertainties for external analysis. These values include *V*, *R*, *R_errors*, *k*, *k_errors*, and *R*<sup>2</sup>

## Installation

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
```bash
# Clone the repository
git clone https://github.com/Joe-Arroyo/pyICI.git
cd pyICI
```
Or download the ZIP archive from the [GitHub page](https://github.com/Joe-Arroyo/pyICI) and extract it.

---

### Step 3: Create a virtual environment (recommended)

Using a virtual environment keeps pyICI's dependencies isolated from other Python projects on your system. It is also required on modern Debian/Ubuntu and Fedora systems, which block system-wide pip installs by default.

**Windows:**
```bash
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
 # Install required packages
   pip install -r requirements.txt
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

