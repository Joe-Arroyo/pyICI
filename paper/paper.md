---
title: 'pyICI: A Python tool for Intermittent Current Interruption analysis'
tags:
  - Python
  - electrochemistry
  - batteries
  - intermittent current interruption
  - internal resistance
  - diffusion
authors:
  - name: José J. Arroyo-Gómez
    orcid: 0000-0001-8214-0645
    affiliation: 1, 2, 3, 4
  - name: Israel Temprano
    orcid: 0000-0001-5610-8908
    affiliation: 5,6
  - name: Louis F.J. Piper
    orcid: 0000-0002-3421-3210
    affiliation: 3,4,7
  - name: Ashok. S. Menon
    orcid: 0000-0001-8148-8615
    affiliation: 3,4,7
affiliations:
  - name: 'Departamento de Almacenamiento de la Energía, Subgerencia Operativa de Energía y Movilidad, Instituto Nacional de Tecnología Industrial (INTI), Buenos Aires, Argentina'
    index: 1
  - name: 'Consejo Nacional de Investigaciones Científicas y Técnicas (CONICET), Buenos Aires, Argentina'
    index: 2
  - name: 'Warwick Manufacturing Group (WMG), University of Warwick, Coventry, UK'
    index: 3 
  - name: 'The Faraday Institution, Quad One, Harwell Science and Innovation Campus, Didcot, UK'
    index: 4
  - name: 'The Hartnoll Centre for Experimental Fuel Technologies, University of Warwick, Coventry, UK'
    index: 7
  - name: 'Yusuf Hamied Department of Chemistry, Lensfield Road, Cambridge, UK'
    index: 5
  - name: 'CICA - Interdisciplinary Center for Chemistry and Biology, University of A Coruña, A Coruña, Spain'
    index: 6

    
date: 10 August 2026
bibliography: paper.bib
header-includes:
  - \providecommand{\citeproctext}{}
  - \providecommand{\citeproc}[2]{#2}
---

# Summary

Intermittent Current Interruption (ICI) is an electrochemical diagnostic tool for monitoring the health of battery cells. It can be used to parameterise the internal resistive and diffusive behaviours of the cells as a function of its state of charge via periodic current interruptions (typically 1–10 s) during constant-current cycling. The voltage relaxation during each pause can be analyzed to calculate the internal resistance $R$ ($\Omega$ or $\Omega \ \mathrm{cm}^{2}$), which captures Ohmic and charge-transfer contributions, as well as the diffusion resistance coefficient $k$ ($\Omega \ \mathrm{s}^{-1/2}$ or $\Omega \ \mathrm{cm}^{2} \ \mathrm{s}^{-1/2}$), which captures the contribution of the solid-state mass transport processes[@YIN2022140888; @Chien2023]. For each interruption, the resistances are calculated via linear regression of $\Delta V$ versus $\sqrt{t}$:

$$R = -\frac{\Delta V(0)}{I}, \qquad k = -\frac{1}{I}\times\frac{\mathrm{d}\,\Delta V}{\mathrm{d}\sqrt{t}},$$

where $I$ is the applied current immediately before the interruption.

`pyICI` is an open-source application that automates the analysis of single- and multi-cycle galvanostatic ICI cycling data. It automatically detects cycles, current-interruption pulses, classifies data and performs the $\sqrt{t}$ regression for every pulse with a user-adjustable fitting window, propagates fit uncertainties through to $R$ and $k$ via the regression covariance matrix. All steps are interactive and visual, so the quality of every individual fit can be inspected and corrected.

# Statement of need

Over the last decade, the ICI method has gained adoption in battery research as a robust, faster, and easy-to-implement complement to the galvanostatic intermittent titration technique (GITT) [@Weppner1977], electrochemical impedance spectroscopy (EIS), and direct current internal resistance (DCIR) methods. Its main strength lies in the fact that it resolves resistance contributions
continuously as a function of state of charge during galvanostatic cycling, as opposed to dedicated measurement steps
[@Lacey2017; @Chien2020; @Chien2023], and is straightforward to program on any
battery cycler, provided it has the necessary data sampling frequency (data is recorded every 10 ms during current interruption). To ensure that electrochemical processes within the cell are not kinetically limited, it is recommended that the cell is cycled at a slow cycling rate, e.g., C/5 or slower. Therefore, a single experiment can contain hundreds of interruptions spread over many cycles. Each pulse requires pulse segmentation, selection
of a valid (where V and $\sqrt{t}$ has a linear relationship) regression window inside the rest period, a V vs. $\sqrt{t}$ fit, and error estimation.
Currently, this is usually done with ad hoc spreadsheets or per-lab scripts, which makes results hard to reproduce while hiding unreliable fits inside batch averages. This poses a high entry barrier for researchers to routinely use the technique.

`pyICI` addresses this gap with a documented, open-source desktop application aimed at battery researchers. It prioritises transparency and fit-quality
control. Every pulse can be visualized individually, regression windows can be adjusted per pulse, per cycle, or globally, $R^2$ (coefficient of determination) values are displayed alongside each fit and tracked across cycles, and uncertainties are propagated from the covariance matrix of each regression rather than being ignored. This makes it practical to utilise the ICI method routinely, more importantly, to longer experiments spanning several cycles.

# State of the field

Open-source software for battery data analysis covers neighbouring needs but not ICI analysis specifically. `cellpy` [@Wind2024] reads and harmonizes cycler data and implements techniques such as incremental capacity analysis, but does not segment or fit current-interruption pulses. `impedance.py` [@Murbach2020] fits equivalent-circuit models to impedance spectra. `PyProBE` [@Holland2025] summarises pulsing experiments into per-pulse DC resistance (voltage drop over current at fixed times post-pulse), but does not perform the $\sqrt{t}$-regression needed to separate Ohmic/charge-transfer resistance from diffusion behaviour. The researchers from Uppsala University, who led the development of the ICI method for battery testing provide descriptions and tutorial material for the analysis [@Lacey2017; @Chien2023], and the R scripts used for the analysis in @Chien2023 are openly archived [@Chien2021data]. However, these scripts were specific to that study and require R programming to adapt, rather than being a maintained, general-purpose tool. An interactive, end-to-end application dedicated to ICI — from raw cycling file to $R$ and $k$ with uncertainties, usable without programming has been missing to the best of our knowledge. ICI-specific pulse detection and per-pulse interactive regression control do not fit naturally into the scope of the libraries above, which is why `pyICI` was built as a standalone tool rather than contributed as a feature to an existing package.

# Software design

To keep the analysis reusable and testable independently of the interface, `pyICI` separates analysis logic from presentation: an `analysis` package contains modules for data loading and cycle detection (`data_loader`), charge/discharge classification and capacity calculation (`phase_classifier`), pulse segmentation (`pulse_analyzer`), windowed $\sqrt{t}$ regression (`regression_analyzer`), and extraction of $R$ and $k$ with
covariance-based error propagation (`kinetic_analyzer`). A `tkinter`-based GUI exposes these modules as tabs that mirror the analysis workflow: data loading and visualization, classification, pulse inspection, regression, and resistance analysis with CSV export. Numerical work relies on NumPy [@Harris2020] and pandas [@McKinney2010], and all plots are
produced with Matplotlib [@Hunter2007]. Because the GUI uses only the Python standard library's `tkinter`, the application runs on Windows, macOS, and Linux without compiled
dependencies. Input is a documented plain-text format (time, voltage, current, optionally cycle number), so data from any cycler can be used after a simple export step.

![`pyICI` analysis workflow: After loading, individual cycles are detected and shown in different colours (top left). Each cycle is classified into charge ($I>0$) and discharge ($I<0$) regimes, and the brief current interruptions ($I=0$) are identified within each (top right). For every interruption, the voltage relaxation is plotted as $\Delta V$ versus the square root of the elapsed time and fitted by linear regression; the fitting window can be adjusted and its quality assessed through the coefficient of determination $R^2$ (bottom right). From each fit, the internal resistance $R = -\mathrm{intercept}/I$ and the diffusion resistance coefficient $k = -\mathrm{slope}/I$ are obtained and plotted against voltage (bottom left). \label{fig:1}](figure1.png)

# Research impact statement

An earlier version of the analysis code that became pyICI was used to extract internal resistance parameters from ICI measurements in our earlier work [@Pandey2026]. pyICI consolidates and generalises that code into a documented, interactive application usable without programming, and the repository includes example datasets and a step-by-step tutorial that reproduce the full analysis workflow. By packaging the complete ICI analysis chain including interruption detection, V vs. $\sqrt{t}$ regression, and covariance-based error propagation, in an accessible form, pyICI supports reproducible reporting of $R$ and $k$ for the community of battery researchers adopting the ICI technique.

# AI usage disclosure

`pyICI` was developed with the assistance of Claude (Anthropic), which was used for code generation and refactoring of the analysis and GUI modules. All AI-assisted code and text were reviewed, tested, and validated by the authors, who made all core design decisions, including the analysis methodology, the numerical procedures, and the software architecture. 

# Acknowledgements

This work was supported by the Faraday Institution's Visiting Research Fellowship scheme. 

# References
