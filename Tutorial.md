# Tutorial

pyICI opens with four sections, shown as tabs across the top and worked through
left to right:

1. **Data loading** — load files and view the raw data / capacity
2. **Pulse verification** — check that the current-interruption pulses are detected correctly
3. **Regression** — fit ΔV vs √t for each pulse and inspect R²
4. **Kinetic analysis** — compute and plot the resistances *R* and *k*

Every section has its controls on the left and its plots on the right, and each
section picks its own active file, so you can compare datasets side by side.


---

## File format

pyICI reads **.txt** files, with units of **seconds, Volts and milliAmps**.

- **Single cycle** — three columns:
  ```
  Time (s)  Voltage (V)  Current (mA)
  time0     Voltage0     Current0
  time1     Voltage1     Current1
  ...       ...          ...
  ```
- **Multiple cycles** — four columns:
  ```
  Cycle number  Time (s)  Voltage (V)  Current (mA)
  Cycle0        time0     Voltage0     Current0
  Cycle1        time1     Voltage1     Current1
  ...           ...       ...          ...
  ```

See examples in the [data](/data) folder.

**Cycle detection.** Files with a cycle-number column use those numbers directly.
Three-column files have their cycles detected automatically from the current
signal — each charge + discharge pair counts as one cycle, and the brief current
interruptions are absorbed into the surrounding half-cycle. Files with **more than
three columns** (or with no recognizable header) open a **column-mapping dialog**
on load, where you assign which columns are Time, Voltage, Current and (optionally)
Cycle number; any other columns are ignored.

<img width="424" height="399" alt="1" src="https://github.com/user-attachments/assets/b71be6e6-29d7-4372-8d7f-fa62273ce59b" />

---

## 1. Data loading

Use **Browse…** then **Add file** to load one or more datasets; they appear in the
**Loaded files** list, where you can set the active file, set a per-file sample
**mass (mg)**, or remove files (**Clear all** removes them all). Tick **Overlay all
files** to compare several files on one plot.

The **View** dropdown switches between two plots:

- **Voltage vs time** — seconds shown in hours, coloured by cycle. Use the
  **Cycles** field to show all cycles (leave blank), a subset (`1,3,5` or `1-5`),
  or a single cycle. Tick **Show current (time view)** to add a current-vs-time
  subplot beneath the voltage.

<img width="2880" height="1704" alt="2" src="https://github.com/user-attachments/assets/51b30d78-dd99-4055-b104-564164df2be3" />


  For 10 cycles or fewer each cycle gets its own colour with a legend; with more
  than 10, the legend becomes a colorbar.

- **Capacity vs voltage** — voltage against capacity, coloured by cycle. If the
  sample **mass (mg)** is left at 0 the x-axis is capacity (mAh); set a mass and
  it becomes **specific capacity** (mAh g⁻¹).


<img width="2880" height="1704" alt="3" src="https://github.com/user-attachments/assets/a0121bfb-f922-4ff5-88c2-6bcb388e0b49" />
<img width="2880" height="1704" alt="4" src="https://github.com/user-attachments/assets/7554ff41-1427-4382-b5c6-a016ec1b78ba" />


Axis limits can be fixed with the **Axis limits** fields (blank = auto), and the
capacity data can be written to CSV. The **Export settings** panel sets figure
size / DPI / format for saving the plot.

---

## 2. Pulse verification

This section is for **checking that the ICI pulses are segmented correctly** before
you fit them. Pick the **File**, the **Phase** (Charge / Discharge), and step through
with the **Cycle** and **Pulse** navigators (arrows, or type a number and press
**Go**). Charge is drawn in **blue**, discharge in **red**.

<img width="2880" height="1704" alt="5" src="https://github.com/user-attachments/assets/258ec5e0-d7f8-407a-9f65-b03ebe162a4f" />

Three plots update together:

- **Top (whole-cycle overview)** — the full cycle's voltage vs time (in hours),
  coloured by charge/discharge, with each pulse's **V₀** marked (the voltage just
  before each interruption) and the **currently selected pulse highlighted**.
- **Bottom-left (pulse detail)** — the selected pulse's voltage **and** current vs
  time, with its V₀ point marked.
- **Bottom-right (rest-period zoom)** — a close-up of that pulse's relaxation after
  the current switches off (voltage vs time since the interruption), with V₀ at
  t = 0. This is the raw segment the ΔV-vs-√t fit is computed on.

V₀ is the voltage immediately before the current interruption and is used to form
ΔV = E − V₀ in the next section.

**Cycle numbering.** How cycles are numbered depends on the file. Files **with a
cycle-number column** keep the file's own numbers exactly as given — so a file that
counts from 0 shows Cycle 0, 1, 2 … Files **without** one (three-column) are
numbered automatically from the current signal, **starting at 1**: one cycle = one
charge + one discharge half-cycle pair, detected regardless of whether cycling
begins on charge or discharge (brief current interruptions are absorbed into the
surrounding half-cycle). So the same data can start at Cycle 0 or Cycle 1 depending
on whether the file carries its own cycle column.

---

## 3. Regression

For the selected **File / Phase / Cycle / Pulse**, the top plot shows the per-pulse
linear fit of **ΔV vs √time** (with a secondary **Time (s)** axis on top), and the
bottom plot tracks **R²** across the pulses of the current cycle.

<img width="2880" height="1704" alt="6" src="https://github.com/user-attachments/assets/b5d6723a-a13e-479a-992a-3c9220a3a89e" />

- **Regression window.** The fit window defaults to **0.1–1.0 s**. The mode
  dropdown switches between **time** (seconds) and **index** (sample points); set
  **start** and **end**, keeping them inside the interruption period.
- **Applying a window.** **Apply → pulse / cycle / all cycles** previews the typed
  window at that scope; the **Save** button beside each **persists** it (per file),
  so it survives navigation and feeds the kinetic analysis. Hand-tuned pulses keep
  their saved window; untuned pulses use the default. **Restore defaults** clears
  them.
- **R** and **k** for the current pulse are shown on the fit plot.
- **Overall check (R² all cycles)** toggles the bottom plot to show R² of every
  pulse across every cycle — charge in blues, discharge in reds, darkening by cycle.
  The **R² plot axis limits** (X / R²) let you zoom in on fit quality.

<img width="2880" height="1704" alt="7" src="https://github.com/user-attachments/assets/ded3a77a-21c7-4d62-9d87-0a9cf07b75fb" />

---

## 4. Kinetic analysis

Using the per-pulse windows carried over from Regression, this section computes the
internal resistance **R** and the diffusion resistance coefficient **k**:

```
R = -intercept / I
k = -slope / I
```

with *I* the current just before each interruption (in amps). Pick the **File**,
**Phase**, and the **Cycles** to include, choose the **X-axis** (Voltage, Capacity,
or Specific capacity), and click **Plot R & k**. R and k are shown on two stacked
plots with 1σ error bars, coloured by cycle (legend for ≤ 10 cycles, colorbar above).

<img width="2880" height="1704" alt="8" src="https://github.com/user-attachments/assets/2909b8a0-72ad-418a-9b8c-6a9ada812814" />

- **Overlay all files** compares several files on the same axes (one colour per file).

<img width="2880" height="1704" alt="9" src="https://github.com/user-attachments/assets/60856623-6ebf-4a7d-a865-13eee0dca7d6" />

- **Axis limits** (X, R, k) fix the ranges; **Auto** clears them.
- **Export.** The **Export settings** panel saves the figure (size / DPI / format),
  and the **Plots** dropdown chooses **Both**, **R only**, or **k only**. The
  **Export … CSV** button writes *V*, *R*, *R_errors*, *k*, *k_errors* and *R²* per
  pulse — charge and discharge in separate files (and one row per file when
  overlaid). See the exported results for the 10-cycle example in the
  [data](/data) folder.



