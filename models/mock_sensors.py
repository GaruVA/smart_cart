import random
import threading
import time

class MockUltrasonicSensor:
    def __init__(self):
        self.distance = 100.0
        self._running = False
        self._thread = None
        
    def start_simulation(self):
        """Start simulating distance changes"""
        self._running = True
        self._thread = threading.Thread(target=self._simulate_detection)
        self._thread.daemon = True
        self._thread.start()
        
    def stop_simulation(self):
        """Stop simulation"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            
    def _simulate_detection(self):
        """Simulate distance changes based on random movement"""
        while self._running:
            # Simulate detection (random movement between 10cm and 200cm)
            self.distance += random.uniform(-5.0, 5.0)
            self.distance = max(10.0, min(200.0, self.distance))
            time.sleep(0.5)
            
    def read_distance(self):
        """Return simulated distance"""
        return round(self.distance, 2)
        
    def cleanup(self):
        self.stop_simulation()

    def get_distance(self):
        return random.uniform(0.5, 5.0)


class MockLoadSensor:
    def __init__(self):
        self.weight = 0.0
        self._running = False
        self._thread = None
        
    def start_simulation(self):
        """Start simulating weight changes"""
        self._running = True
        self._thread = threading.Thread(target=self._simulate_detection)
        self._thread.daemon = True
        self._thread.start()
        
    def stop_simulation(self):
        """Stop simulation"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            
    def _simulate_detection(self):
        """Simulate weight changes based on random fluctuations"""
        while self._running:
            # Simulate small fluctuations in weight reading
            self.weight += random.uniform(-0.05, 0.05)
            self.weight = max(0.0, self.weight)
            time.sleep(0.3)
            
    def read_weight(self):
        """Return simulated weight"""
        return round(self.weight, 2)
        
    def add_item(self, item_weight=None):
        """Simulate adding item to cart"""
        if item_weight is None:
            # Random item weight between 0.2kg and 2.0kg
            item_weight = random.uniform(0.2, 2.0)
        self.weight += item_weight
        
    def remove_item(self, item_weight=None):
        """Simulate removing item from cart"""
        if item_weight is None:
            # Random item weight between 0.2kg and 2.0kg
            item_weight = random.uniform(0.2, min(2.0, self.weight))
        self.weight = max(0.0, self.weight - item_weight)
        
    def tare(self):
        """Set current weight as zero/reference"""
        self.weight = 0.0
        return True

    def get_weight(self):
        return random.uniform(0.0, 10.0)


class MockBarcodeScanner:
    def __init__(self):
        # Sample product barcodes with dummy data
        self.sample_barcodes = [
            "1234567890128",
            "5901234123457",
            "4005808262816",
            "8710398503968",
            "3574660239881"
        ]
        
    def scan(self):
        """Simulate scanning by returning a random barcode"""
        return random.choice(self.sample_barcodes)