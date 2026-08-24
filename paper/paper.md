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
    affiliation: "1, 2, 3, 4"
  - name: Israel Temprano
    orcid: 0000-0001-5610-8908
    affiliation: "5, 6"
  - name: Louis F.J. Piper
    orcid: 0000-0002-3421-3210
    affiliation: "3, 4, 7"
  - name: Ashok S. Menon
    orcid: 0000-0001-8148-8615
    affiliation: "3, 4, 7"
affiliations:
  - name: 'Departamento de Almacenamiento de la Energía, Subgerencia Operativa de Energía y Movilidad, Instituto Nacional de Tecnología Industrial (INTI), Buenos Aires, Argentina'
    index: 1
  - name: 'Consejo Nacional de Investigaciones Científicas y Técnicas (CONICET), Buenos Aires, Argentina'
    index: 2
  - name: 'Warwick Manufacturing Group (WMG), University of Warwick, Coventry, UK'
    index: 3 
  - name: 'The Faraday Institution, Quad One, Harwell Science and Innovation Campus, Didcot, UK'
    index: 4
  - name: 'Yusuf Hamied Department of Chemistry, Lensfield Road, Cambridge, UK'
    index: 5
  - name: 'CICA - Interdisciplinary Center for Chemistry and Biology, University of A Coruña, A Coruña, Spain'
    index: 6
  - name: 'The Hartnoll Centre for Experimental Fuel Technologies, University of Warwick, Coventry, UK'
    index: 7

    
date: 11 August 2026
bibliography: paper.bib
header-includes:
  - \providecommand{\citeproctext}{}
  - \providecommand{\citeproc}[2]{#2}
---

# Summary

Intermittent Current Interruption (ICI) is an electrochemical diagnostic tool for monitoring the health of battery cells. It can be used to parameterise the internal resistive and diffusive behaviours of the cells as a function of its state of charge via periodic current interruptions (typically 1–10 s) during constant-current cycling. The voltage relaxation during each pause can be analyzed to calculate the internal resistance $R$ ($\Omega$ or $\Omega\,\mathrm{cm}^{2}$), which captures Ohmic and charge-transfer contributions, as well as the diffusion resistance coefficient $k$ ($\Omega\,\mathrm{s}^{-1/2}$ or $\Omega\,\mathrm{cm}^{2}\,\mathrm{s}^{-1/2}$), which captures the contribution of the solid-state mass transport processes[@YIN2022140888; @Chien2023]. For each interruption, the resistances are calculated via linear regression of the voltage change during relaxation ($\Delta V$) versus the square root of time ($\sqrt{t}$):

$$R = -\frac{\Delta V(0)}{I}, \qquad k = -\frac{1}{I}\times\frac{\mathrm{d}\,\Delta V}{\mathrm{d}\sqrt{t}},$$

where $I$ is the applied current immediately before the interruption.

`pyICI` is an open-source application that automates the analysis of single- and multi-cycle galvanostatic ICI cycling data. It automatically detects cycles, current-interruption pulses, classifies data and performs the $\sqrt{t}$ regression for every pulse with a user-adjustable fitting window, and propagates fit uncertainties through to $R$ and $k$ via the regression covariance matrix. All steps are interactive and visual, so the quality of every fit can be inspected and corrected.

# Statement of need

Over the last decade, the ICI method has gained adoption in battery research as a robust, faster, and easy-to-implement complement to the galvanostatic intermittent titration technique (GITT) [@Weppner1977], electrochemical impedance spectroscopy (EIS), and direct current internal resistance (DCIR) methods. Its main strength lies in the fact that it resolves resistance contributions
continuously as a function of state of charge during galvanostatic cycling, as opposed to dedicated measurement steps
[@Lacey2017; @Chien2020; @Chien2023], and is straightforward to program on any
battery cycler, provided it has the necessary data sampling frequency (data is recorded every 10 ms during the current interruption). To ensure that electrochemical processes within the cell are not kinetically limited, it is recommended that the cell is cycled at a slow rate, e.g., C/5 or slower. Therefore, a single experiment can contain hundreds of interruptions spread over many cycles. Each pulse requires pulse segmentation, selection
of a valid  regression window (where V and $\sqrt{t}$ has a linear relationship) within the rest period, a $\Delta V$ vs. $\sqrt{t}$ fit, and error estimation.
Currently, this is usually done with ad hoc spreadsheets or custom scripts, which makes results hard to reproduce while hiding unreliable fits inside batch averages. This poses a high entry barrier for researchers to routinely use the technique.

`pyICI` addresses this gap with a documented, open-source desktop application aimed at battery researchers. It prioritises transparency and fit-quality
control. Every pulse can be visualized individually, regression windows can be adjusted per pulse, per cycle, or globally, and $R^2$ (coefficient of determination) values are displayed alongside each fit and tracked across cycles. Finally, uncertainties are propagated from the covariance matrix of each regression rather than being ignored. This makes it practical to utilise the ICI method routinely, and more importantly, for longer experiments spanning several cycles.

# State of the field

Open-source software for battery data analysis covers neighbouring needs but not ICI analysis specifically. `cellpy` [@Wind2024] reads and harmonizes cycler data and implements techniques such as incremental capacity analysis, but does not segment or fit current-interruption pulses. `impedance.py` [@Murbach2020] fits equivalent-circuit models to impedance spectra. `PyProBE` [@Holland2025] summarises pulsing experiments into per-pulse DC resistance (voltage drop over current at fixed times post-pulse), but does not perform the $\sqrt{t}$-regression needed to separate Ohmic/charge-transfer resistance from diffusion behaviour. The researchers from Uppsala University, who led the development of the ICI method for battery testing provide descriptions and tutorial material for the analysis [@Lacey2017; @Chien2023], and the R scripts used for the analysis in @Chien2023 are openly archived [@Chien2021data]. However, these scripts are specific to that study and require R programming to adapt, rather than being a maintained, general-purpose tool. More recently, `ICI Studio` [@ici_studio] has become available for interactive ICI analysis as a browser-based web application `pyICI` instead provides a locally installed, pure-Python implementation whose analysis pipeline: pulse detection, classification, and per-pulse $\sqrt{t}$ regression. It is fully exposed and can be inspected, adapted, and extended by the user. To the best of our knowledge, no other maintained tool takes a raw cycling file through to $R$ and $k$ with uncertainties in a form that is both usable without programming and openly adaptable within a scientific-Python workflow. ICI-specific pulse detection and per-pulse interactive regression control do not fit naturally into the scope of the libraries above, which is why `pyICI` was built as a standalone tool rather than contributed as a feature to an existing package.

# Software design

To keep the analysis reusable and testable independently of the interface, `pyICI` separates analysis logic from presentation: an `analysis` package contains modules for data loading and cycle detection (`data_loader`), charge/discharge classification and capacity calculation (`phase_classifier`), pulse segmentation (`pulse_analyzer`), windowed $\sqrt{t}$ regression (`regression_analyzer`), and extraction of $R$ and $k$ with
covariance-based error propagation (`kinetic_analyzer`). A `tkinter`-based GUI organizes these modules as tabs that mirror the analysis workflow: data loading and visualization, classification, pulse inspection, regression, and resistance analysis with CSV export option. Numerical work relies on NumPy [@Harris2020] and pandas [@McKinney2010], and all plots are
produced with Matplotlib [@Hunter2007]. Because the GUI uses only the Python standard library's `tkinter`, the application runs on Windows, macOS, and Linux without compiled
dependencies. Input is a documented plain-text format (time, voltage, current, optionally cycle number), so data from any cycler can be used after a simple export step.

![`pyICI` analysis workflow: After loading, individual cycles are detected and shown in different colours (top left). Each cycle is classified into charge ($I>0$ mA) and discharge ($I<0$ mA) regimes, and the current interruptions ($I=0$ mA) are identified within each cycle (top right). For every interruption, the voltage relaxation is plotted as $\Delta V$ versus the square root of the elapsed time and fitted by linear regression; the fitting window can be adjusted and its quality assessed through the coefficient of determination $R^2$ (bottom right). From each fit, the internal resistance $R = -\mathrm{intercept}/I$, ($\mathrm{intercept} = \Delta V(0)$), and the diffusion resistance coefficient $k = -\mathrm{slope}/I$, ($\mathrm{slope} = \frac{\mathrm{d}\,\Delta V}{\mathrm{d}\sqrt{t}}$), are obtained and plotted against voltage (bottom left). The data shown is collected from a Graphite–NMC ($LiNi_xMn_yCo_zO_2$) Li-ion single-layer pouch cell similar to that used in @Pandey2026. The cell was cycled between $2.5$–$4.4$ V using the ICI protocol. Note that the fast cycling rate (C/$3$) makes the calculated values of $k$ unreliable, and hence is meant solely for illustrative purposes.\label{fig:1}](figure1.pdf)

# Research impact statement

An earlier version of the analysis code that became pyICI was used to extract internal resistance parameters from ICI measurements in our earlier work [@Pandey2026]. pyICI consolidates and generalises that code into a documented, interactive application usable without programming, and the repository includes example datasets and a step-by-step tutorial that reproduce the full analysis workflow. By packaging the complete ICI analysis chain including interruption detection, $\Delta V$ vs. $\sqrt{t}$ regression, and covariance-based error propagation, in an accessible form, pyICI supports reproducible reporting of $R$ and $k$ for the community of battery researchers utilizing the ICI technique.

# AI usage disclosure

`pyICI` was developed with the assistance of Claude (Anthropic), which was used for code generation and refactoring of the analysis and GUI modules. All AI-assisted code and text were reviewed, tested, and validated by the authors, who made all core design decisions, including the analysis methodology, the numerical procedures, and the software architecture. 

# Acknowledgements

This work was supported by the Faraday Institution's Visiting Research Fellowship scheme. L.F.J.P and A.S.M are grateful for the support from the Hartnoll Centre for Experimental Fuel Technologies. Dr Ferran Brosa Planella (University of Warwick) is also acknowledged for the help and guidance received. Mr Art Cleary, a Faraday Institution FUSE intern at WMG (2023), is also acknowledged for their intital work on Python-based ICI analysis.


# References
