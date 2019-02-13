import time

from .base import register_sensor, FileSensor, SensorNotAvailableException


@register_sensor
class PiCamera(FileSensor):
    def __init__(self, *args, img_format="jpeg", **kwargs):
        super().__init__(img_format, *args, **kwargs)

        global picamera
        import picamera

        self.format = img_format

    def read(self, res_X=3280, res_Y=2464, adjust_time_s=2):
        file_path = self.file_path

        try:
            with picamera.PiCamera() as camera:
                camera.resolution = (res_X, res_Y)
                camera.start_preview()
                time.sleep(adjust_time_s)

                camera.capture(file_path, format=self.format)
                camera.stop_preview()
        except picamera.exc.PiCameraMMALError as e:
            raise SensorNotAvailableException(e)

        return file_path
