import sys
import tty
import termios

class BarcodeScanner:
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = termios.tcgetattr(self.fd)
        
    def scan(self):
        try:
            tty.setcbreak(sys.stdin.fileno())
            barcode = ""
            while True:
                char = sys.stdin.read(1)
                if char == "\r":  # Enter key ends input
                    break
                barcode += char
            return barcode.strip()
        finally:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)
            
    def reset(self):
        """Reset terminal settings"""
        termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)