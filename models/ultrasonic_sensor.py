import RPi.GPIO as GPIO
import time

class UltrasonicSensor:
    def __init__(self, trig_pin=23, echo_pin=24):
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(trig_pin, GPIO.OUT)
        GPIO.setup(echo_pin, GPIO.IN)
        self.trig = trig_pin
        self.echo = echo_pin
        
    def read_distance(self):
        try:
            GPIO.output(self.trig, True)
            time.sleep(0.00001)
            GPIO.output(self.trig, False)

            while GPIO.input(self.echo) == 0:
                pulse_start = time.time()
            while GPIO.input(self.echo) == 1:
                pulse_end = time.time()

            pulse_duration = pulse_end - pulse_start
            distance = pulse_duration * 17150  # cm
            return round(distance, 2)
        except Exception as e:
            print(f"Error reading distance: {e}")
            return 0.0
        finally:
            GPIO.cleanup((self.trig, self.echo))
            
    def cleanup(self):
        GPIO.cleanup((self.trig, self.echo))