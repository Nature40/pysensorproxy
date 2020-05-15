import time
import logging
import threading
import RPi.GPIO as GPIO

from pytimeparse import parse as parse_time

from .base import register_sensor, Sensor, SensorNotAvailableException

logger = logging.getLogger(__name__)

@register_sensor
class LED(Sensor):
    # use a suitable cam_led pin, if not it will fail
    def __init__(self, *args, led_pin: int = 6, **kwargs):
        super().__init__(*args, uses_height=False, ** kwargs)
        self.led_pin = led_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(led_pin, GPIO.OUT)

    def _read(self, duration: str, **kwargs):
        duration_s = parse_time(duration)

        logger.debug("Switching the LEDs on")
        x = threading.Thread(target=self._switch_on_wait_switch_off, args=(duration_s,))
        x.start()


    def _switch_on_wait_switch_off(self, duration_s):
        # Turn the leds on
        GPIO.output(self.led_pin, GPIO.HIGH)

        #sleep for duration
        time.sleep(duration_s)

        # Turn the leds off
        GPIO.output(self.led_pin, GPIO.LOW)
