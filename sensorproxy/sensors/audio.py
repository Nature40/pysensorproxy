import subprocess
import logging

from .base import register_sensor, FileSensor, SensorNotAvailableException

log = logging.getLogger("pysensorproxy.sensors.audio")


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
        file_path = self.file_path
        cmd = [
            "arecord",
            "-D", self.device_name,
            "-t", self.file_type,
            "-f", self.format,
            "-r", str(self.rate),
            "-d", str(duration_s),
            file_path]

        log.debug("Recording audio: {}".format(" ".join(cmd)))

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.wait()
        stderr = p.stderr.read()

        if p.returncode != 0:
            raise SensorNotAvailableException(
                "arecord returned {}: {}".format(p.returncode, stderr.decode()))

        log.info("audio file written to '{}'".format(file_path))

        return file_path
