import RPi.GPIO as GPIO
import time
from hx711 import HX711   # pip3 install hx711py

# === USER CONFIGURATION ===
DT_PIN = 5        # GPIO pin connected to HX711 DOUT
SCK_PIN = 6       # GPIO pin connected to HX711 SCK
CALIBRATION_FACTOR = 192.0761  # positive; negate if your readings are inverted
INITIAL_READS = 50  # how many samples to average for initial tare
LOOP_READS    = 5   # samples per weight reading
SLEEP_TIME    = 0.5 # seconds between prints
# ==========================

class LoadSensor:
    def __init__(self, dout=DT_PIN, pd_sck=SCK_PIN):
        self.hx = HX711(dout_pin=dout, pd_sck_pin=pd_sck)
        self.hx.reset()
        self.baseline = None
        self.calibration_factor = CALIBRATION_FACTOR

    def setup_hx711(self):
        """
        Initialize HX711, let it settle, and compute a baseline (tare) average.
        Returns the raw baseline value.
        """
        self.hx.reset()
        time.sleep(0.1)  # allow ADC to settle
        
        print(f"Taring scale with {INITIAL_READS} readings... ", end="", flush=True)
        raw_vals = self.hx.get_raw_data(times=INITIAL_READS)
        if not raw_vals:
            raise RuntimeError("Failed to read from HX711 during tare.")
        self.baseline = sum(raw_vals) / len(raw_vals)
        print(f"done (baseline={self.baseline:.1f}).")
        
        return self.baseline

    def read_weight(self):
        """
        Read raw data, subtract baseline, divide by calibration factor to get grams.
        """
        try:
            if self.baseline is None:
                self.setup_hx711()
                
            raw_vals = self.hx.get_raw_data(times=LOOP_READS)
            if not raw_vals:
                print("Failed to read from HX711")
                return 0.0
                
            raw_avg = sum(raw_vals) / len(raw_vals)
            grams = (raw_avg - self.baseline) / self.calibration_factor
            return round(grams / 1000, 2)  # Convert to kg
        except Exception as e:
            print(f"Error reading weight: {e}")
            return 0.0
            
    def tare(self):
        """Set current weight as zero/reference"""
        try:
            self.setup_hx711()
            return True
        except Exception as e:
            print(f"Error taring scale: {e}")
            return False


def setup_hx711():
    """
    Initialize HX711, let it settle, and compute a baseline (tare) average.
    Returns the hx object and the raw baseline value.
    """
    hx = HX711(dout_pin=DT_PIN, pd_sck_pin=SCK_PIN)
    hx.reset()
    time.sleep(0.1)  # allow ADC to settle
    
    print(f"Taring scale with {INITIAL_READS} readings... ", end="", flush=True)
    raw_vals = hx.get_raw_data(times=INITIAL_READS)
    if not raw_vals:
        raise RuntimeError("Failed to read from HX711 during tare.")
    baseline = sum(raw_vals) / len(raw_vals)
    print(f"done (baseline={baseline:.1f}).")
    
    return hx, baseline

def get_weight(hx, baseline, calibration_factor):
    """
    Read raw data, subtract baseline, divide by calibration factor to get grams.
    """
    raw_vals = hx.get_raw_data(times=LOOP_READS)
    if not raw_vals:
        return None
    raw_avg = sum(raw_vals) / len(raw_vals)
    grams = (raw_avg - baseline) / calibration_factor
    return grams

def main():
    GPIO.setmode(GPIO.BCM)
    try:
        hx, baseline = setup_hx711()
        print("=== STARTING WEIGHT READINGS ===")
        print("Press Ctrl+C to quit.\n")
        
        while True:
            w = get_weight(hx, baseline, CALIBRATION_FACTOR)
            if w is None:
                print("\rRead error!          ", end="", flush=True)
            else:
                print(f"\rWeight: {w:8.2f} g", end="", flush=True)
            time.sleep(SLEEP_TIME)
            
    except KeyboardInterrupt:
        print("\nExiting.")
    except Exception as e:
        print(f"\nError: {e}")
    finally:
        GPIO.cleanup()

if __name__ == "__main__":
    main()