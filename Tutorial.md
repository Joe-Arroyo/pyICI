# Tutorial
1. **File format**: this GUI only reads .txt files, and the units used are seconds, Volts and milliAmps
  - **Single cycle**: three-column files:
    ```
    Time (s)  Voltage (V)  Current (mA) 
    time0     Voltage0     Current0      
    time1     Voltage1     Current1      
    time2     Voltage2     Current2
    ...       ...          ...      
    ```
  - **Multiple cycles**: four-column files:
    ```

    Cycle number  Time (s)  Voltage (V)  Current (mA) 
    Cycle0        time0     Voltage0     Current0      
    Cycle1        time1     Voltage1     Current1      
    Cycle2        time2     Voltage2     Current2
    ...           ...       ...          ...      
    ```
  See examples in the [data](/data) folder

2. **Data loading and visualization:** Raw data visualization, no data treatment. ICI starting points are detected based on the current.
  
   For files with fewer than 10 cycles, each cycle will have its unique color, and the plot will have a legend indicating cycle number and the ICI start points (the first point where I > 0).
   
    <img width="400" height="300" alt="1 cycles raw" src="https://github.com/user-attachments/assets/c2116944-4621-4d98-9038-9fc94b94ba6c" />
    <img width="500" height="400" alt="10 cycles raw" src="https://github.com/user-attachments/assets/30032b39-4a17-4932-81c3-c99f0c98a528" />

    
     With more than 10 cycles, the cycles will be colored using the Viridis colormap, and the legend will be replaced with a colorbar.
     
4. **Classification:** In this tab, the data is classified into charge or discharge within each cycle. Data can be plotted as:
   - **Voltage vs time:** seconds are converted to hours, and one can plot either individual or multiple cycles.
     
     The single-cycle option will give this:
     
     <img width="400" height="300" alt="V vs t single cicle" src="https://github.com/user-attachments/assets/3cfc025c-b158-4bf6-8a09-01209bebc328" />

     On the other hand, the multi-cycle will give this:
     
     <img width="400" height="300" alt="10 cycles V vs t single cicle" src="https://github.com/user-attachments/assets/3cc4cd35-1f80-4453-bbcc-8ce8210e298a" />

     Multi-cycle can also be used to plot individual cycles without the current plot, but they will retain their assigned color within the colormap.

   - **Voltage vs capacity:** Cycles can be plotted individually or in groups. Same color scheme as in the multi-cycle option in the phase classification tab. If the sample mass (in mg) is changed, the plot will now show specific capacity in mAhg<sup>-1</sup>.
       Sample mass (mg) = 0
       
      <img width="400" height="300" alt="v vs cap" src="https://github.com/user-attachments/assets/86c1d7ee-532f-44d3-b7f8-782d3a841829" />
      
      Sample mass (mg) = 1000
     
      <img width="400" height="300" alt="v vs spec cap" src="https://github.com/user-attachments/assets/b15b808c-9829-4b98-8dd5-08d2f8857e0c" />

5. **Pulse visualization:** Here, one can see each individual pulse within a cycle

   Cycle 0 showing voltage vs time and current vs time curves
   
   <img width="400" height="300" alt="Cycle0" src="https://github.com/user-attachments/assets/ad1d71ea-c038-4d3a-8b68-e91613221950" />

   Pulse 1 in Cycle 0
   
   <img width="400" height="300" alt="Pusle 1 Cycle0" src="https://github.com/user-attachments/assets/a3ac2281-d097-45d0-a098-ea3a31eaee47" />

    Blue = Charge and Red = Discharge

   Top plots: Voltage vs time during the current interruption. The shaded area indicates the period where I = 0. V<sub>0</sub>. is the voltage immediately prior to the current interruption, and it will later be used to calculate ΔV.

   Bottom plots: complete Voltage vs time of each pulse

6. **Regression:**
   
    - **Pulse analysis:** By default, the regression is made from 0.1 - 1 s, and the results  will be presented in the ΔV vs t<sup>1/2</sup> plot as well as in R<sup>2</sup>

      Analysis of Pulse 1 in Cycle 0. Left: charge, right: discharge
      
      <img width="300" height="400" alt="regression" src="https://github.com/user-attachments/assets/e5f7dff2-8283-4e3c-8cd8-b46a71f00b46" /><img width="300" height="600" alt="regression discharge" src="https://github.com/user-attachments/assets/2af039e5-acb5-4965-bc48-414132f7fef0" />



      The starting and ending values of the regression can be modified, but they must be within the interruption period. This change can affect an individual pulse (via the Update -> Save buttons), all pulses within a cycle (via the Apply to all pulses -> Save all buttons), or all cycles (via Apply to all cycles).

     - **R<sup>2</sup> vs cycles:** Once the changes to the regression are finished, click on "Analyze All Cycles" to re-calculate the regression parameters of all cycles, which later will be used in the kinetic analysis. After that, the Multi-cycle analysis subtab will be open, showing the coefficient of determination, R<sup>2</sup>, vs cycle number. Each data point in the cycles corresponds to each pulse.

        <img width="400" height="300" alt="R2 vs cycles" src="https://github.com/user-attachments/assets/b6fc09b5-e129-4dea-b5d8-4cda15e78660" />
        
8. **Kinetic analysis:** Based on the regression parameters calculated above, the internal resistance (*R*) and the diffusion resistance coefficient (*k*) can be calculated as:
   ```
   R = -intercept / I
   k = -slope / I
   ``` 
    Analysis of Pulse 1 in Cycle 0. Left: charge, right: discharge
   
    <img width="300" height="300" alt="R and k charge" src="https://github.com/user-attachments/assets/afb7d277-fae7-4cc3-b968-460df96527bf" /><img width="300" height="300" alt="R and k discharge" src="https://github.com/user-attachments/assets/7cc6147d-10b2-419b-8c69-69ca0eaa3fe8" />

    As in point 2, when working with more than 10 cycles, the legend changes to a colormap
 
9. **Export results:** In tab 5, *R*, *k*, and R<sup>2</sup> can be exported into a CSV file, along with their errors, cycle, and pulse numbers. Charge and discharge data are exported in different files. See the exported resultsfor the 10 cycles in the [data](/data) folder.
