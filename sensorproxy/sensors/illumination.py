import time
import logging
import os
import glob
import threading

from pytimeparse import parse as parse_time

from .base import register_sensor, Sensor, SensorNotAvailableException

logger = logging.getLogger(__name__)

@register_sensor
class LED(Sensor):
    def __init__(self, *args, cam_led: int = 6, gpiochip_labels: [str] = ["raspberrypi-exp-gpio", "brcmexp-gpio"], **kwargs):
        super().__init__(*args, ** kwargs)
        gpio_base = self.__gpiochip_label_base(gpiochip_labels)
        self.led_gpio = gpio_base + cam_led
        self.led_gpio_path = "/sys/class/gpio/gpio{}/value".format(self.led_gpio)

        # export the requested gpio port
        if not os.path.exists(self.led_gpio_path):
            with open("/sys/class/gpio/export", "a") as gpio_export_file:
                gpio_export_file.write(str(self.led_gpio))

    @staticmethod
    def __gpiochip_label_base(gpiochip_labels):
        for gpiochip_path in glob.glob("/sys/class/gpio/gpiochip*/"):
            with open(os.path.join(gpiochip_path, "label"), "r") as gpiochip_label_file:
                label = gpiochip_label_file.readline().strip()

            if label in gpiochip_labels:
                with open(os.path.join(gpiochip_path, "base"), "r") as gpiochip_base_file:
                    base = int(gpiochip_base_file.readline())

                return base

        raise SensorNotAvailableException(
            "Could not find gpio base for {}".format(gpiochip_labels))

    def _read(self, duration: str, **kwargs):
        duration_s = parse_time(duration)

        logger.debug("Switching the LEDs on")
        x = threading.Thread(target=self._switch_on_wait_switch_off, args=(duration_s,))
        x.start()


    def _switch_on_wait_switch_off(self, duration_s):
        # Turn the leds on
        with open(self.led_gpio_path, "a") as gpio_file:
            gpio_file.write(str(int(True)))
            time.sleep(2)

        #sleep for duration
        time.sleep(duration_s)

        with open(self.led_gpio_path, "a") as gpio_file:
            gpio_file.write(str(int(False)))
            time.sleep(2)
