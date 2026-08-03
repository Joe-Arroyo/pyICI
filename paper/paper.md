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
    affiliation: 6,7
  - name: Louis F.J. Piper
    orcid: 0000-0002-3421-3210
    affiliation: 3,4,5
  - name: Ashok. S. Menon
    orcid: 0000-0001-8148-8615
    affiliation: 3,4,5
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
    index: 5
  - name: 'Yusuf Hamied Department of Chemistry, Lensfield Road, Cambridge, UK'
    index: 6
  - name: 'CICA - Interdisciplinary Center for Chemistry and Biology, University of A Coruña, A Coruña, Spain'
    index: 7

    
date: $\today$
bibliography: paper.bib
header-includes:
  - \providecommand{\citeproctext}{}
  - \providecommand{\citeproc}[2]{#2}
---

# Summary

Intermittent Current Interruption (ICI) is an electrochemical diagnostic tool for monitoring the health of battery cells by the determination of the internal and diffusion resistance during galvanostatic cycling. ICI introduces brief current interruptions (typically 1–10 s) during constant-current cycling, and the voltage relaxation during each pause is analyzed to calculate the internal resistance $R$ ($\Omega$), which captures Ohmic and charge-transfer contributions, and the diffusion resistance coefficient $k$ ($\Omega\,\mathrm{s}^{-1/2}$), which captures solid-state mass transport [@YIN2022140888; @Chien2023].During each interruption the voltage change $\Delta V$ is linear in the square root of time, so a linear regression of $\Delta V$ versus $\sqrt{t}$ yields both parameters:

$$R = -\frac{\mathrm{\Delta V(0)}}{I}, \qquad k = -\frac{\mathrm{1}}{I}\times\frac{\mathrm{d\Delta V}}{d \sqrt t},$$

where $I$ is the applied current immediately before the interruption.

`pyICI` is an application that automates the analysis of single- and multi-cycle galvanostatic cycling data. It automatically detects cycles, current-interruption pulses, classifies data and performs the $\sqrt{t}$ regression for every pulse with a user-adjustable fitting window, propagates fit uncertainties through to $R$ and $k$ via the regression covariance matrix. All steps are interactive and visual, so the quality of every individual fit can be inspected and corrected.

# Statement of need

ICI has gained adoption in battery research as a faster, cycling-compatible alternative to
the galvanostatic intermittent titration technique (GITT) [@Weppner1977] and as a complement
to electrochemical impedance spectroscopy, because it resolves resistance contributions
continuously during normal cycling rather than in dedicated measurement steps
[@Lacey2017; @Chien2020; @Chien2023]. The measurement itself is easy to program on any
battery cycler; the barrier is the analysis. A single experiment can contain hundreds of
interruptions spread over many cycles, and each one requires pulse segmentation, selection
of a valid regression window inside the rest period, a $\sqrt{t}$ fit, and error estimation.
In practice this is usually done with ad hoc spreadsheets or per-lab scripts, which makes
results hard to reproduce, hides poor-quality fits inside batch averages, and puts the
technique out of reach of researchers who do not program.

`pyICI` addresses this gap with a documented, freely available desktop application aimed at
experimental battery researchers. Its design priorities are transparency and fit-quality
control: every pulse can be visualized individually, regression windows can be adjusted per
pulse, per cycle, or globally, $R^2$ values are displayed alongside each fit and tracked
across cycles, and uncertainties are propagated from the covariance matrix of each
regression rather than being ignored. This makes it practical to apply ICI routinely — and
defensibly — to long cycling experiments.

# State of the field

Open-source software for battery data covers neighbouring needs but not ICI analysis.
`cellpy` [@Wind2024] reads and harmonizes cycler data and implements techniques such as
incremental capacity analysis, but does not segment or fit current-interruption pulses.
`impedance.py` [@Murbach2020] fits equivalent-circuit models to impedance spectra, a
different measurement altogether. The originators of the ICI method provide descriptions
and tutorial material for the analysis [@Lacey2017; @Chien2023], and the R scripts used
for the analysis in @Chien2023 are openly archived [@Chien2021data]; these scripts,
however, were written to reproduce the figures of one specific study and require R
programming to adapt, rather than being a maintained, general-purpose tool. An
interactive, end-to-end application dedicated to ICI — from raw cycling file to $R$ and
$k$ with uncertainties, usable without programming — has been missing. ICI-specific pulse detection and per-pulse interactive regression control do not fit naturally into the scope of the libraries above, which is why `pyICI` was built as a standalone tool rather than contributed as a feature to an existing package.

# Software design

`pyICI` separates analysis logic from presentation. An `analysis` package contains modules
for data loading and cycle detection (`data_loader`), charge/discharge classification and
capacity calculation (`phase_classifier`), pulse segmentation (`pulse_analyzer`),
windowed $\sqrt{t}$ regression (`regression_analyzer`), and extraction of $R$ and $k$ with
covariance-based error propagation (`kinetic_analyzer`). A `tkinter`-based GUI exposes these
modules as tabs that mirror the analysis workflow: data loading and visualization,
classification, pulse inspection, regression, and resistance analysis with CSV export.
Numerical work relies on NumPy [@Harris2020] and pandas [@McKinney2010], and all plots are
produced with Matplotlib [@Hunter2007]. Because the GUI uses only the Python standard
library's `tkinter`, the application runs on Windows, macOS, and Linux without compiled
dependencies. Input is a documented plain-text format (time, voltage, current, optionally
cycle number), so data from any cycler can be used after a simple export step.

![`pyICI` analysis workflow: After loading, individual cycles are detected and shown in different colours (top left). Each cycle is classified into charge ($I>0$) and discharge ($I<0$) regimes, and the brief current interruptions ($I=0$) are identified within each (top right). For every interruption, the voltage relaxation is plotted as $\Delta V$ versus the square root of the elapsed time and fitted by linear regression; the fitting window can be adjusted and its quality assessed through the coefficient of determination $R^2$ (bottom right). From each fit, the internal resistance $R = -\mathrm{intercept}/I$ and the diffusion resistance coefficient $k = -\mathrm{slope}/I$ are obtained and plotted against voltage (bottom left). .\label{fig:1}](figure1.svg)

# Research impact statement

An earlier version of the analysis code that became pyICI was used to extract internal resistance and diffusion-related parameters from intermittent current interruption measurements in a study of heterogeneous delithiation in single-crystalline Ni-rich layered oxide cathodes [@Pandey2026]. pyICI consolidates and generalises that code into a documented, interactive application usable without programming, and the repository includes example datasets and a step-by-step tutorial that reproduce the full analysis workflow. By packaging the complete ICI analysis chain — interruption detection, quality-controlled $\sqrt{t}$ regression, and covariance-based error propagation — in an accessible form, pyICI supports reproducible, uncertainty-aware reporting of $R$ and $k$ for the growing community of battery researchers adopting the ICI technique.

# AI usage disclosure

`pyICI` was developed with the assistance of Claude (Anthropic), which was used for code
generation and refactoring of the analysis and GUI modules. All AI-assisted code and text were reviewed, tested, and validated by the authorS, who made all core design decisions, including the analysis methodology, the numerical procedures, and the software architecture. 

# Acknowledgements

TO BE COMPLETED

# References
