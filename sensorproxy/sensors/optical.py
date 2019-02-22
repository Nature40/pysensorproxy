import time
import logging

from pytimeparse import parse as parse_time

from .base import register_sensor, FileSensor, SensorNotAvailableException

logger = logging.getLogger(__name__)


@register_sensor
class PiCamera(FileSensor):
    def __init__(self, *args, img_format, **kwargs):
        super().__init__(img_format, *args, **kwargs)

        global picamera
        import picamera

        self.format = img_format

    def _read(self, file_path, res_X, res_Y, adjust_time):
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

        logger.info("image file written to '{}'".format(file_path))
