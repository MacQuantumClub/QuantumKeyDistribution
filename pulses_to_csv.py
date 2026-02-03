# Live PyVISA script to read rectangular pulses from oscilloscope
# and write detected pulses to CSV file

import pyvisa
import numpy as np
import matplotlib.pyplot as plt
import csv
import time
from datetime import datetime

def detect_pulses(volt_value, time_value, threshold=0.05, min_pulse_width=20, hysteresis=0.5):
    """
    Detect pulses in voltage data.
    Returns list of (time, voltage) for detected pulses.
    
    Parameters:
    - volt_value: list of voltage values from oscilloscope
    - time_value: list of corresponding time values
    - threshold: voltage threshold above baseline to detect a pulse (in volts).
        Higher values = detect only larger spikes, lower = more sensitive
    - min_pulse_width: minimum number of samples required to count as a valid pulse. 
        Prevents noise from being detected as pulses
    - hysteresis: fraction of threshold for pulse end detection (0-1).
        Lower values make pulses end earlier, reducing false detections
    """
    
    if len(volt_value) < min_pulse_width:
        return []
    
    
    baseline = np.percentile(volt_value, 10)
    
    
    end_threshold = baseline + (threshold * hysteresis)
    
    
    pulses = []
    
    in_pulse = False
    
    pulse_start_idx = 0
    
    
    for idx in range(len(volt_value)):
        voltage = volt_value[idx]
        
        
        if voltage > (baseline + threshold) and not in_pulse:
            in_pulse = True
            pulse_start_idx = idx
        
        
        elif voltage < end_threshold and in_pulse:
            in_pulse = False
            
            if idx - pulse_start_idx >= min_pulse_width:
                
                pulse_idx = pulse_start_idx + (idx - pulse_start_idx) // 2
                
                pulses.append((time_value[pulse_idx], volt_value[pulse_idx]))
    
    
    if in_pulse and len(volt_value) - pulse_start_idx >= min_pulse_width:
        pulse_idx = pulse_start_idx + (len(volt_value) - pulse_start_idx) // 2
        pulses.append((time_value[pulse_idx], volt_value[pulse_idx]))
    
    return pulses

def read_oscilloscope_data(sds):
    
    # Returns list of raw voltage values (8-bit integers, not yet converted to volts)
    
    sds.write("c1:wf? dat2")
    
    recv = list(sds.read_raw())[15:]
    
    
    if len(recv) < 2:
        return None
    
    
    recv.pop()
    recv.pop()
    
    volt_value = []
    for data in recv:
        if data > 127:
            
            data = data - 255
        volt_value.append(data)
    
    return volt_value

def get_oscilloscope_settings(sds):
    """
    Returns:
    - vdiv: Voltage per division (V/div)
    - ofst: Voltage offset
    - tdiv: Time per division (s/div)
    - sara: Sample rate per second
    """
    
    vdiv = float(sds.query("c1:vdiv?").strip())
    
    ofst = float(sds.query("c1:ofst?").strip())

    tdiv = float(sds.query("tdiv?").strip())
 
    sara = sds.query("sara?").strip()
    

    sara_unit = {'G': 1E9, 'M': 1E6, 'k': 1E3}
    for unit in sara_unit.keys():
        if sara.find(unit) != -1:
            sara = sara.split(unit)
            sara = float(sara[0]) * sara_unit[unit]
            break
    sara = float(sara)
    
    return vdiv, ofst, tdiv, sara

def main():
    _rm = pyvisa.ResourceManager()
    sds = _rm.open_resource("USB0::0xF4ED::0xEE3A::SDS1EEFD810102::INSTR")
    sds.timeout = 200000
    sds.write("chdr off")
    

    vdiv, ofst, tdiv, sara = get_oscilloscope_settings(sds)
    sds.chunk_size = 20 * 1024 * 1024

    print(f"Oscilloscope settings:")
    print(f"  Voltage/div: {vdiv}V")
    print(f"  Offset: {ofst}V")
    print(f"  Time/div: {tdiv}s")
    print(f"  Sample rate: {sara/1e6:.2f} MS/s")
    print(f"  Sample period: {1/sara*1e9:.2f} ns\n")
    

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_filename = f"pulses_{timestamp}.csv"
    
    
    
    pulse_count = 0
    
    try:
        
        with open(csv_filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            
            writer.writerow(['Time (s)', 'Voltage (V)', 'Pulse #', 'Timestamp'])
            
            
            while True:
                try:
                    
                    volt_raw = read_oscilloscope_data(sds)
                    
                    
                    if volt_raw is None:
                        continue
                    
                    
                    volt_value = []
                    time_value = []
                    for idx, data in enumerate(volt_raw):
                        
                        volt = data / 25 * vdiv - ofst
                        
                        time_data = -(tdiv * 14 / 2) + idx * (1 / sara)
                        volt_value.append(volt)
                        time_value.append(time_data)
                    
                    
                    pulses = detect_pulses(volt_value, time_value, threshold=0.05, min_pulse_width=20)
                    
                    
                    if pulses:
                        
                        current_time = datetime.now().strftime("%H:%M:%S.%f")[:-3]
                        
                        for pulse_time, pulse_volt in pulses:
                            pulse_count += 1
                            
                            writer.writerow([f"{pulse_time:.9e}", f"{pulse_volt:.6f}", pulse_count, current_time])
                            
                            print(f"Pulse #{pulse_count}: Time={pulse_time:.9e}s, Voltage={pulse_volt:.6f}V")
                    
                    
                    csvfile.flush()
                    
                    time.sleep(0.1)
                    
                except Exception as e:
                    
                    print(f"Error reading oscilloscope: {e}")
                    
                    time.sleep(0.5)
    
    except KeyboardInterrupt:
        
        print(f"\n\nStopped. Total pulses detected: {pulse_count}")
        print(f"Saved to: {csv_filename}")
    
    finally:
        
        sds.close()

if __name__ == '__main__':
    main() 

