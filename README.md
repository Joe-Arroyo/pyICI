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

- **Regression Analysis**: Perform linear regression and adjust the coefficient of determiaation (*R$^2$*)
  - User-defined regression analysis window (within the current interruption period)
  - Linear least-squares regression on the selected data window
  - Fit parameters: Slope, Intercept, and R$^2$*
  - Covariance matrix uses for error propagation analysis
  - Independ adjust for charge and discharge
  - Capability of adjusting one pules, all pulses within one cycle or all cycles at once
  - Side-by-side visualizaion for charge and discharge analysis
     
- **Kinetic Analysis**: *R* and *k* calculation from the regression analysis
  - R = -intercept / I, with I being the current before the interruption 
  - k = -slope / I, with I being the current before the interruption 
  - Error bars using the data from the covariance matrix
  - Cycle selection
  - Side-by-side visualizaion for charge and discharge
  - Data export of all values with uncertainties for external analysis. These values include, V, R, R errors, k, k errors, and R$^2$


