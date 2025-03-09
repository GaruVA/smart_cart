from hx711 import HX711

class LoadSensor:
    def __init__(self, dout=5, pd_sck=6):
        self.hx = HX711(dout, pd_sck)
        self.hx.reset()

    def read_weight(self):
        try:
            raw_value = self.hx.get_raw_data_mean(10)
            weight = raw_value / 1000  # Convert to kg (calibrate later)
            return round(weight, 2)
        except Exception as e:
            print(f"Error reading weight: {e}")
            return 0.0
            
    def tare(self):
        """Set current weight as zero/reference"""
        try:
            self.hx.tare()
            return True
        except Exception as e:
            print(f"Error taring scale: {e}")
            return False