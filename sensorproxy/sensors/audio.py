import subprocess

from .base import register_sensor, FileSensor


@register_sensor
class Microphone(FileSensor):
    def __init__(self, *args, device_name="hw:1,0", file_type="wav",
                 duration_sec=30, format="S16_LE", rate=44100, **kwargs):
        super().__init__(file_type, *args, **kwargs)

        self.device_name = device_name
        self.file_type = file_type
        self.format = format
        self.rate = rate

    def read(self, duration_s=1):
        subprocess.run([
            "arecord",
            "-D", self.device_name,
            "-t", self.file_type,
            "-f", self.format,
            "-r", str(self.rate),
            "-d", str(duration_s),
            self.file_path])
