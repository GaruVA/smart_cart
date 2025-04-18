import threading
import time
import os

class BarcodeScanner:
    def __init__(self):
        """Initialize barcode scanner interface
        This implementation reads from the scanned_codes.txt file,
        which is populated by the barcode scanner test program.
        """
        self.scanned_codes_file = "/home/user/Desktop/scanned_codes.txt"
        self._last_barcode = None
        self._last_read_time = 0
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        
        # Sample product barcodes for fallback when no real scan available
        self.sample_barcodes = [
            "1234567890128",
            "5901234123457",
            "4005808262816",
            "8710398503968",
            "3574660239881"
        ]
        
        # Start background thread to monitor scanned_codes.txt
        self._start_monitoring()
            
    def _start_monitoring(self):
        """Start background thread to monitor the scanned codes file"""
        self._running = True
        self._thread = threading.Thread(target=self._monitor_file)
        self._thread.daemon = True
        self._thread.start()
        
    def _monitor_file(self):
        """Background thread that monitors the scanned_codes.txt file for new codes"""
        last_modification_time = 0
        last_file_size = 0
        
        while self._running:
            try:
                # Check if the file exists
                if os.path.exists(self.scanned_codes_file):
                    # Get file stats
                    stats = os.stat(self.scanned_codes_file)
                    current_mod_time = stats.st_mtime
                    current_size = stats.st_size
                    
                    # If file was modified or size changed
                    if (current_mod_time > last_modification_time or 
                        current_size > last_file_size):
                        # Update tracking variables
                        last_modification_time = current_mod_time
                        last_file_size = current_size
                        
                        # Read the last line from the file
                        with open(self.scanned_codes_file, 'r') as f:
                            lines = f.read().splitlines()
                            if lines:
                                # Get the latest code and update our cached value
                                with self._lock:
                                    self._last_barcode = lines[-1]
                                    self._last_read_time = time.time()
                                    print(f"New barcode detected: {self._last_barcode}")
            except Exception as e:
                print(f"Error monitoring barcode file: {e}")
                
            # Sleep to avoid tight loop
            time.sleep(0.5)
    
    def scan(self):
        """Get the most recently scanned barcode
        
        This is a non-blocking call that returns the most recently 
        scanned code or a sample code if no recent scan.
        
        Returns:
            str: Scanned barcode or sample code
        """
        with self._lock:
            # If we have a recent scan (within last 3 seconds), use it
            if self._last_barcode and (time.time() - self._last_read_time) < 3:
                return self._last_barcode
        
        # If no real scanner or no recent scan, check if scanned_codes.txt exists
        # and return the last code in the file
        try:
            if os.path.exists(self.scanned_codes_file):
                with open(self.scanned_codes_file, "r") as f:
                    codes = f.read().splitlines()
                    if codes:
                        return codes[-1]
        except Exception as e:
            print(f"Error reading from scanned_codes.txt: {e}")
            
        # Final fallback: return a sample barcode
        import random
        return random.choice(self.sample_barcodes)