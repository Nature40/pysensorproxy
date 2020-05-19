import time
import logging
import threading
import RPi.GPIO as GPIO
import smbus

from pytimeparse import parse as parse_time

from .base import register_sensor, Sensor, SensorNotAvailableException

logger = logging.getLogger(__name__)


@register_sensor
class BrightPi(Sensor):
    I2C_ADDRESS = 0x70

    def __init__(self,
                 *args,
                 bus_id: int = 1,
                 **kwargs):
        Sensor.__init__(self,
                        *args,
                        uses_height=False,
                        **kwargs)

        self.bus = smbus.SMBus(bus_id)

    @staticmethod
    def _bitmask(leds):
        # shift index by 1, map indices to bit mask, sum bit mask
        return sum(map(lambda x: 2**(x-1), leds))

    GAIN_REGISTER = 0x09
    GAIN_MAX = 0b00001111

    def _set_gain(self,
                  gain: float,):
        # limit gain to [0, 1]
        gain = max(0.0, min(1.0, gain))

        # compute and set gain
        _gain = int(BrightPi.GAIN_MAX * gain)
        self.bus.write_byte_data(BrightPi.I2C_ADDRESS,
                                 BrightPi.GAIN_REGISTER,
                                 _gain)

        return _gain

    BRIGHTNESS_MAX = 0b00111111

    def _set_leds(self,
                  leds: list,
                  brightness: float):
        # limit brightness to [0, 1]
        brightness = max(0.0, min(1.0, brightness))

        # compute brightness
        _brightness = int(BrightPi.BRIGHTNESS_MAX * brightness)
        for led in leds:
            self.bus.write_byte_data(BrightPi.I2C_ADDRESS,
                                     led,
                                     _brightness)

        return _brightness

    STATUS_REGISTER = 0x00

    def _disable_all(self):
        # disable all leds
        self.bus.write_byte_data(BrightPi.I2C_ADDRESS,
                                 BrightPi.STATUS_REGISTER, 0x00)

    def _enable(self,
                leds: list):
        # enable all leds
        self.bus.write_byte_data(BrightPi.I2C_ADDRESS,
                                 BrightPi.STATUS_REGISTER,
                                 BrightPi._bitmask(leds))

    _header_sensor = [
        "Duration (s)",
        f"Brightness White (1/{BRIGHTNESS_MAX})",
        f"Brightness IR (1/{BRIGHTNESS_MAX})",
        f"Gain (1/{GAIN_MAX})",
    ]

    LEDS_WHITE = (2, 4, 5, 7)
    LEDS_IR = (1, 3, 6, 8)
    LEDS_ALL = (1, 2, 3, 4, 5, 6, 7, 8)

    def _read(self,
              duration: str,
              white: float = 1.0,
              ir: float = 1.0,
              gain: float = 1.0,
              **kwargs):

        self._disable_all()

        # parse duration (in case of an error, leds won't stay on)
        duration_s = parse_time(duration)

        # set brightness and gain
        _white = self._set_leds(BrightPi.LEDS_WHITE, white)
        _ir = self._set_leds(BrightPi.LEDS_IR, ir)
        _gain = self._set_gain(gain)

        # enable all leds
        self._enable(BrightPi.LEDS_ALL)

        time.sleep(duration_s)

        self._disable_all()

        return [duration_s, _white, _ir, _gain]


@register_sensor
class LED(Sensor):
    def __init__(self,
                 *args,
                 led_pin: int = 21,
                 **kwargs):
        Sensor.__init__(self,
                        *args,
                        uses_height=False,
                        **kwargs)

        self.led_pin = led_pin
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(led_pin, GPIO.OUT)

    _header_sensor = [
        "Duration (s)",
    ]

    def _read(self,
              duration: str,
              **kwargs):
        duration_s = parse_time(duration)

        # enable
        logger.debug(f"LED {self.led_pin} on for {duration_s}s")
        GPIO.output(self.led_pin, GPIO.HIGH)

        # sleep
        time.sleep(duration_s)

        # disable
        logger.debug(f"LED {self.led_pin} off")
        GPIO.output(self.led_pin, GPIO.LOW)

        return [duration_s]
