import RPi.GPIO as GPIO
import time

class UltrasonicSensor:
    def __init__(self, trig_pin=23, echo_pin=25):
        # Set up GPIO only once during initialization
        GPIO.setwarnings(False)  # Disable warnings
        GPIO.setmode(GPIO.BCM)
        
        self.trig = trig_pin
        self.echo = echo_pin
        
        # Setup the pins
        GPIO.setup(self.trig, GPIO.OUT)
        GPIO.setup(self.echo, GPIO.IN)
        
        # Make sure trigger is low initially
        GPIO.output(self.trig, False)
        time.sleep(0.1)  # Short delay to ensure pin is properly set
        
    def read_distance(self):
        try:
            # Send a 10μs pulse
            GPIO.output(self.trig, True)
            time.sleep(0.00001)  # 10μs
            GPIO.output(self.trig, False)

            # Find time when echo starts (pulse_start)
            pulse_start = time.time()
            timeout_start = time.time()
            while GPIO.input(self.echo) == 0:
                pulse_start = time.time()
                # Safety timeout
                if time.time() - timeout_start > 0.1:  # 100ms timeout
                    return 0.0
            
            # Find time when echo ends (pulse_end)
            pulse_end = time.time()
            timeout_start = time.time()
            while GPIO.input(self.echo) == 1:
                pulse_end = time.time()
                # Safety timeout
                if time.time() - timeout_start > 0.1:  # 100ms timeout
                    return 0.0

            # Calculate time difference and convert to distance
            pulse_duration = pulse_end - pulse_start
            distance = pulse_duration * 17150  # Speed of sound = 343m/s, distance = time * speed / 2
            return round(distance, 2)
        except Exception as e:
            print(f"Error reading distance: {e}")
            return 0.0
            
    def cleanup(self):
        # Only clean up when the object is being destroyed
        try:
            GPIO.cleanup((self.trig, self.echo))
        except:
            # Ignore cleanup errors
            pass