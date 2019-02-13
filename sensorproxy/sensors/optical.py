import time

from .base import register_sensor, FileSensor


@register_sensor
class PiCamera(FileSensor):
    def __init__(self, *args, format="jpeg", **kwargs):
        super().__init__(format, *args, **kwargs)

        global picamera
        import picamera

        self.format = format

    def read(self):
        with picamera.PiCamera() as camera:
            camera.resolution = (3280, 2464)
            camera.start_preview()
            time.sleep(2)

            camera.capture(self.file_path, format=self.format)
            camera.stop_preview()
