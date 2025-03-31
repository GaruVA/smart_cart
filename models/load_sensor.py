import RPi.GPIO as GPIO
import time
from hx711 import HX711  # Requires: pip3 install hx711py
import threading

class LoadSensor:
    def __init__(self, dout_pin=5, pd_sck_pin=6):
        """Initialize the load sensor with HX711 interface
        
        Args:
            dout_pin: Data output pin (DT pin of HX711)
            pd_sck_pin: Clock pin (SCK pin of HX711)
        """
        self.dout_pin = dout_pin
        self.pd_sck_pin = pd_sck_pin
        # Calibration factor (adjust based on load cell's sensitivity)
        self.calibration_factor = 192.07609999999997
        self.hx = None
        self.tare_value = 0
        self.weight = 0.0
        self._running = False
        self._thread = None
        self._lock = threading.Lock()  # Thread safety for sensor readings
        
        # Initialize the sensor
        self._setup_sensor()
    
    def _setup_sensor(self):
        """Initialize the HX711 module and perform initial tare"""
        try:
            self.hx = HX711(dout_pin=self.dout_pin, pd_sck_pin=self.pd_sck_pin)
            self.hx.reset()
            self.tare_value = self._get_raw_average(10)  # Perform initial tare
            print("Load sensor initialized successfully")
        except Exception as e:
            print(f"Error during load sensor setup: {e}")
            self.hx = None
    
    def _get_raw_average(self, num_readings=5):
        """Get the average of raw readings from the HX711"""
        if not self.hx:
            return 0
            
        try:
            raw_data = self.hx.get_raw_data(times=num_readings)
            if raw_data:
                return sum(raw_data) / len(raw_data)
            else:
                print("Failed to get valid readings from load cell")
                return 0
        except Exception as e:
            print(f"Error getting raw average from load cell: {e}")
            return 0
    
    def start_simulation(self):
        """Start continuous weight monitoring (for compatibility with mock sensor)"""
        self._running = True
        self._thread = threading.Thread(target=self._continuous_reading)
        self._thread.daemon = True
        self._thread.start()
        
    def stop_simulation(self):
        """Stop continuous monitoring (for compatibility with mock sensor)"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
    
    def _continuous_reading(self):
        """Continuously read weight in background thread"""
        while self._running:
            if self.hx:
                with self._lock:
                    self.weight = self.read_weight()
            time.sleep(0.3)  # Read interval
    
    def read_weight(self):
        """Get current weight in kg (converted from grams)"""
        if not self.hx:
            return 0.0
            
        try:
            with self._lock:
                raw_avg = self._get_raw_average(5)
                # Calculate weight in grams then convert to kilograms
                weight_grams = (raw_avg - self.tare_value) / self.calibration_factor
                weight_kg = weight_grams / 1000.0  # Convert to kilograms
                
                # Power down and up between readings
                self.hx.power_down()
                time.sleep(0.001)
                self.hx.power_up()
                
                return max(0.0, weight_kg)  # Ensure non-negative weight
        except Exception as e:
            print(f"Error reading weight: {e}")
            return 0.0
    
    def add_item(self, item_weight=None):
        """For compatibility with mock sensor - real sensor reads actual weight"""
        # Not needed for real sensor as weight is read directly
        pass
    
    def remove_item(self, item_weight=None):
        """For compatibility with mock sensor - real sensor reads actual weight"""
        # Not needed for real sensor as weight is read directly
        pass
    
    def tare(self):
        """Set current weight as zero/reference"""
        if not self.hx:
            return False
            
        try:
            self.tare_value = self._get_raw_average(10)
            return True
        except Exception as e:
            print(f"Error during tare operation: {e}")
            return False