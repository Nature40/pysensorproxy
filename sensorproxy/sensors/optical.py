import time
import logging
import subprocess

import picamera
from pytimeparse import parse as parse_time

from .base import register_sensor, FileSensor, SensorNotAvailableException

logger = logging.getLogger(__name__)


@register_sensor
class PiCamera(FileSensor):
    def __init__(self, *args, img_format: str, **kwargs):
        super().__init__(img_format, *args, **kwargs)

        self.format = img_format

    def _read(self, file_path: str, res_X: int, res_Y: int, adjust_time: str, *args, **kwargs):
        adjust_time_s = parse_time(adjust_time)

        logger.debug("Reading PiCamera with {}x{} for {}s".format(
            res_X, res_Y, adjust_time_s))

        try:
            with picamera.PiCamera() as camera:
                camera.resolution = (res_X, res_Y)
                camera.start_preview()
                time.sleep(adjust_time_s)

                camera.capture(file_path, format=self.format)
                camera.stop_preview()
        except picamera.exc.PiCameraMMALError as e:
            raise SensorNotAvailableException(e)
        except picamera.exc.PiCameraError as e:
            raise SensorNotAvailableException(e)

        logger.info("image file written to '{}'".format(file_path))


@register_sensor
class PiNoirCamera(PiCamera):
    pass


@register_sensor
class IRProCamera(PiCamera):
    def __init__(self, *args, img_format: str, cam_led: int = 134, **kwargs):
        super().__init__(img_format, *args, **kwargs)

        self.cam_led = int(cam_led)

        # export the requested gpio port
        p = subprocess.Popen(["gpio", "export", str(self.cam_led), "output"])
        p.wait()
        if p.returncode != 0:
            logger.warn(
                "GPIO {} (IR filter switch) could not be exported.".format(self.cam_led))

        self.cam_led_path = "/sys/class/gpio/gpio{}/value".format(self.cam_led)

    def _read(self, file_path: str, res_X: int, res_Y: int, adjust_time: str, filter_ir: bool = False, *args, **kwargs):
        adjust_time_s = parse_time(adjust_time)

        logger.debug("Reading IrProCamera with {}x{} for {}s".format(
            res_X, res_Y, adjust_time_s))

        try:
            with picamera.PiCamera() as camera:
                camera.resolution = (res_X, res_Y)
                camera.start_preview()

                # set cam gpio to the matching value
                with open(self.cam_led_path, "a") as gpio_file:
                    gpio_file.write(str(int(filter_ir)))
                    time.sleep(2)

                time.sleep(adjust_time_s)

                camera.capture(file_path, format=self.format)
                camera.stop_preview()
        except picamera.exc.PiCameraMMALError as e:
            raise SensorNotAvailableException(e)
        except picamera.exc.PiCameraError as e:
            raise SensorNotAvailableException(e)

        logger.info("image file written to '{}'".format(file_path))
