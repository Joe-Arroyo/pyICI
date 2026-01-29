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

2. **Data loading and visualization:** Raw data visualization, no data treatment. ICI starting points deteceted based on the current.
  
   For files with fewer than 10 cycles, each cycle will have its unique color, and the plot will have a legend indicating cycle number and the ICI start points (first point where I > 0).
   
    <img width="400" height="300" alt="1 cycles raw" src="https://github.com/user-attachments/assets/c2116944-4621-4d98-9038-9fc94b94ba6c" />
    <img width="400" height="300" alt="10 cycles raw" src="https://github.com/user-attachments/assets/19fa4bc8-3e47-46ab-a5a5-50b0cca84e05" />
    
     With more than 10 cycles, the cycles will be colored according to the Viridis colormap, and the legend will be changed to a colorbar.
     
     <img width="800" height="600" alt="100 cycles raw" src="https://github.com/user-attachments/assets/e76289e6-f95f-4d5d-852a-eacaad2ee965" />

3. **Classification:** In this tab, the data is classified into charge or discharge within each cycle.




