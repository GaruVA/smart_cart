import RPi.GPIO as GPIO
import time
import threading
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
        self.hx = None
        try:
            self.hx = HX711(dout_pin=dout, pd_sck_pin=pd_sck)
            self.hx.reset()
        except Exception as e:
            print(f"Error initializing HX711: {e}")
        
        self.baseline = None
        self.calibration_factor = CALIBRATION_FACTOR
        
        # For continuous weight reading
        self.is_running = False
        self.reading_thread = None
        self.lock = threading.Lock()
        self._current_weight = 0.0
        self.weight_readings = []
        self.max_readings = 10  # Number of readings to average
        
        # For monitoring weight changes
        self.monitoring = False
        self.monitoring_thread = None
        self.weight_history = []
        self.last_stable_weight = 0.0
        self.weight_threshold = 50.0  # grams threshold to detect item added

    def setup_hx711(self):
        """
        Initialize HX711, let it settle, and compute a baseline (tare) average.
        Returns the raw baseline value.
        """
        if not self.hx:
            print("HX711 not initialized")
            return None
            
        self.hx.reset()
        time.sleep(0.1)  # allow ADC to settle
        
        print(f"Taring scale with {INITIAL_READS} readings... ", end="", flush=True)
        raw_vals = self.hx.get_raw_data(times=INITIAL_READS)
        if not raw_vals:
            raise RuntimeError("Failed to read from HX711 during tare.")
        self.baseline = sum(raw_vals) / len(raw_vals)
        print(f"done (baseline={self.baseline:.1f}).")
        
        # Reset the weight readings buffer
        self.weight_readings = []
        
        return self.baseline

    def read_weight(self):
        """
        Read weight in kg. If continuous reading is active, return the average.
        Otherwise, take a direct reading.
        """
        if self.is_running:
            # Return the current averaged weight from continuous readings
            with self.lock:
                if self.weight_readings:
                    return round(sum(self.weight_readings) / len(self.weight_readings), 2)
                return 0.0
        else:
            # Take a direct reading
            return self._get_direct_weight()
    
    def _get_direct_weight(self):
        """Take a direct weight reading without using the continuous readings"""
        try:
            if self.baseline is None:
                self.setup_hx711()
                
            if not self.hx:
                return 0.0
                
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
    
    def start_reading(self):
        """Start continuous reading of weight data"""
        if self.is_running:
            return
            
        if self.baseline is None:
            self.setup_hx711()
            
        self.is_running = True
        self.reading_thread = threading.Thread(target=self._reading_loop)
        self.reading_thread.daemon = True
        self.reading_thread.start()
        print("Load sensor: Continuous reading started")
    
    def stop_reading(self):
        """Stop continuous reading"""
        self.is_running = False
        if self.reading_thread:
            if self.reading_thread.is_alive():
                self.reading_thread.join(1.0)
            self.reading_thread = None
        print("Load sensor: Continuous reading stopped")
    
    def _reading_loop(self):
        """Background thread for continuous weight reading"""
        while self.is_running:
            try:
                weight = self._get_direct_weight()
                
                # Update readings buffer with lock
                with self.lock:
                    self.weight_readings.append(weight)
                    if len(self.weight_readings) > self.max_readings:
                        self.weight_readings.pop(0)
            except Exception as e:
                print(f"Error in reading loop: {e}")
            
            time.sleep(0.1)  # Small delay between readings
    
    def start_monitoring(self):
        """Start monitoring for added items"""
        if self.monitoring:
            return
            
        # Make sure continuous reading is active
        if not self.is_running:
            self.start_reading()
            
        self.monitoring = True
        self.weight_history = []
        self.last_stable_weight = self.read_weight() * 1000.0  # Convert to grams
        
        # Start monitoring thread
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        print("Load sensor: Weight change monitoring started")
    
    def stop_monitoring(self):
        """Stop monitoring for added items"""
        self.monitoring = False
        if self.monitoring_thread:
            if self.monitoring_thread.is_alive():
                self.monitoring_thread.join(1.0)
            self.monitoring_thread = None
        print("Load sensor: Weight change monitoring stopped")
    
    def _monitoring_loop(self):
        """Background thread for detecting when items are added or removed"""
        history_size = 5  # Number of readings to keep for stability check
        stable_threshold = 2.0  # grams of max deviation to consider weight stable
        
        while self.monitoring:
            current_weight = self.read_weight() * 1000.0  # Convert to grams
            
            # Add to history
            self.weight_history.append(current_weight)
            if len(self.weight_history) > history_size:
                self.weight_history.pop(0)
                
            # Check if weight is stable (all readings within threshold)
            if len(self.weight_history) == history_size:
                min_weight = min(self.weight_history)
                max_weight = max(self.weight_history)
                
                # If weight is stable
                if max_weight - min_weight < stable_threshold:
                    # Check if significantly different from last stable weight
                    avg_weight = sum(self.weight_history) / len(self.weight_history)
                    if avg_weight > self.last_stable_weight + self.weight_threshold:
                        # Item was added, update stable weight
                        item_weight = avg_weight - self.last_stable_weight
                        print(f"Item added! Weight increased by {item_weight:.1f}g to {avg_weight:.1f}g")
                        self.last_stable_weight = avg_weight
                    elif avg_weight < self.last_stable_weight - self.weight_threshold:
                        # Item was removed
                        item_weight = self.last_stable_weight - avg_weight
                        print(f"Item removed! Weight decreased by {item_weight:.1f}g to {avg_weight:.1f}g")
                        self.last_stable_weight = avg_weight
            
            time.sleep(0.2)  # Short delay between monitoring checks
    
    def add_item(self, item_weight=None):
        """For compatibility with mock sensor - real sensor reads actual weight"""
        # Start monitoring if an item is added programmatically
        if not self.monitoring:
            self.start_monitoring()
    
    def remove_item(self, item_weight=None):
        """For compatibility with mock sensor - real sensor reads actual weight"""
        # Not needed for real sensor as weight is read directly
        pass
    
    def tare(self):
        """Set current weight as zero/reference"""
        if not self.hx:
            return False
            
        try:
            # Stop reading temporarily if active
            was_running = self.is_running
            if was_running:
                self.stop_reading()
            
            self.setup_hx711()
            
            # Resume reading if it was active before
            if was_running:
                self.start_reading()
                
            # Reset monitoring state
            self.last_stable_weight = 0.0
            self.weight_history = []
            
            return True
        except Exception as e:
            print(f"Error taring scale: {e}")
            return False
            
    def cleanup(self):
        """Clean up resources"""
        self.stop_monitoring()
        self.stop_reading()
        if self.hx and hasattr(self.hx, 'cleanup'):
            self.hx.cleanup()


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
