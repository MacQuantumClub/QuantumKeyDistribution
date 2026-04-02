import csv
import time
from datetime import datetime

import numpy as np
import pyvisa



# SET SCOPE SETTINGS

VISA_RESOURCE = "USB0::0xF4EC::0xEE3A::SDSMMFCX8R0827::INSTR"
CHANNEL = "C1"
CSV_FILENAME = "photon_pulse_log.csv"

POLL_DELAY_SECONDS = 0.05 # 50 ms between polls

VOLTAGE_THRESHOLD = 0.05 # volts above baseline to trigger pulse detection
HYSTERESIS_VOLTS = 0.2 # volts below trigger level to end pulse (prevents multiple detections from noise)
REFRACTORY_SECONDS = 0.002

PRINT_DEBUG = True



# CONNECT TO SCOPE

def connect_scope(resource_name):
    rm = pyvisa.ResourceManager()
    scope = rm.open_resource(resource_name)

    scope.timeout = 5000 # 5 second timeout 
    scope.encoding = "latin_1" # use latin_1 encoding (It maps every byte (0–255) directly to a character)
    scope.write_termination = "\n" 
    scope.read_termination = "\n"

    print("Connected to:", scope.query("*IDN?").strip())
    return rm, scope


def configure_scope(scope, channel):
    scope.write("chdr off") # turns off header in responses to simplify parsing
    scope.write(f"{channel}:trace on") # turn on channel trace to ensure data is being captured
    scope.write(f"{channel}:wf? dat2") # set waveform data format to dat2 (unsigned 8-bit integers) for easier conversion to voltage



# READ SETTINGS
# read vertical scale, offset, and time division settings from scope to convert raw data to voltage and build time axis

def get_vertical_scale(scope, channel):
    return float(scope.query(f"{channel}:vdiv?").strip())

def get_vertical_offset(scope, channel):
    return float(scope.query(f"{channel}:ofst?").strip())

def get_time_div(scope):
    return float(scope.query("tdiv?").strip())



# GET WAVEFORM
# read raw waveform data as bytes
# converts bytes to voltage values based on scope settings

# read waveform data as bytes from scope using dat2 format (unsigned 8-bit integers)
def read_waveform_bytes(scope, channel):
    return scope.query_binary_values(
        f"{channel}:wf? dat2", 
        datatype="B",
        container=np.array
    )

# convert raw byte values (0-255) to voltage based on vertical scale and offset settings
# voltage = (raw_byte - 128) * (vdiv / 25) - offset 
    # - 128 centers byte values around 0
    # volts per div (vdiv) / bits per div (25))
    # subtract offset to get final voltage relative to baseline
def convert_bytes_to_voltage(raw_bytes, vdiv, offset):
    return (raw_bytes.astype(np.float64) - 128.0) * (vdiv / 25.0) - offset

# build time axis for plotting or analysis based on number of samples and time division setting
def build_time_axis(num_samples, time_div):
    total_time = 14.0 * time_div
    return np.linspace(-total_time / 2, total_time / 2, num_samples)



# SPIKE DETECTION

def estimate_baseline(voltage):
    return float(np.median(voltage))


def detect_pulses(voltage, time_axis, threshold, min_pulse_width, hysteresis):
    baseline = estimate_baseline(voltage) # median voltage as baseline estimate

    trigger_level = baseline + threshold   # voltage level to start pulse
    release_level = trigger_level - hysteresis  # voltage level to end pulse 

    pulses = [] # list to hold detected pulse info
    in_pulse = False # flag to track if currently in a pulse
    start_index = None # index where current pulse starts

    # iterate through voltage samples
        # detect pulsses based on trigger and release level 
    for i, value in enumerate(voltage):

        # if not currently in a pulse, check if voltage exceeds trigger level to start a new pulse
        if not in_pulse:
            if value >= trigger_level:
                in_pulse = True
                start_index = i

        # if currently in a pulse, check if voltage falls below release level to end the pulse
        else:
            # if voltage is under release level, end the pulse 
                end_index = i - 1 # end index is last sample above release level
                width = end_index - start_index + 1 # calculate pulse width in samples
                
                # check if valid (if width is greater than minimum pulse width) 
                    # if valid, get peak voltage and add to list
                if width >= min_pulse_width: 
                    segment = voltage[start_index:end_index + 1] # get voltage samples for this pulse
                    peak_voltage = float(np.max(segment)) # find max voltage in this pulse segment

                    # add pulse info to list
                    pulses.append({
                        "peak_voltage": peak_voltage
                    })

                in_pulse = False # reset pulse flag
                start_index = None # reset start index

    return pulses



# CSV LOGGING (timestamp + voltage)


def initialize_csv(filename):
    try:
        with open(filename, "x", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["timestamp", "voltage"])
    except FileExistsError:
        pass


def append_event_to_csv(filename, pulse):
    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.now().isoformat(),
            pulse["peak_voltage"]
        ])



# MAIN LOOP


def main():
    initialize_csv(CSV_FILENAME)

    rm, scope = connect_scope(VISA_RESOURCE)
    configure_scope(scope, CHANNEL)

    print("Starting detection...\n")

    last_event_time = 0

    try:
        while True:

            vdiv = get_vertical_scale(scope, CHANNEL)
            offset = get_vertical_offset(scope, CHANNEL)
            time_div = get_time_div(scope)

            raw = read_waveform_bytes(scope, CHANNEL)

            if len(raw) == 0:
                continue

            voltage = convert_bytes_to_voltage(raw, vdiv, offset)
            time_axis = build_time_axis(len(voltage), time_div)

            pulses = detect_pulses(
                voltage,
                time_axis,
                VOLTAGE_THRESHOLD,
                3,
                HYSTERESIS_VOLTS
            )

            current_time = time.time()

            for pulse in pulses:
                if current_time - last_event_time >= REFRACTORY_SECONDS:

                    append_event_to_csv(CSV_FILENAME, pulse)
                    last_event_time = current_time

                    if PRINT_DEBUG:
                        print(f"{pulse['peak_voltage']:.4f} V")

            time.sleep(POLL_DELAY_SECONDS)

    except KeyboardInterrupt:
        print("\nStopped.")

    finally:
        scope.close()
        rm.close()
        print("Closed connection.")


if __name__ == "__main__":
    main()