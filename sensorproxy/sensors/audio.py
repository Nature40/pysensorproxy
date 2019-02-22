import subprocess
import logging
import os

from .base import register_sensor, FileSensor, SensorNotAvailableException, SensorConfigurationException

logger = logging.getLogger(__name__)


@register_sensor
class Microphone(FileSensor):
    def __init__(self, *args, device_name, file_type, sample_format, **kwargs):
        super().__init__(file_type, *args, **kwargs)

        self.device_name = device_name
        self.file_type = file_type
        self.sample_format = sample_format
        self.rate = rate

    def _read(self, file_path, duration_s):
        cmd = [
            "arecord",
            "-D", self.device_name,
            "-t", self.file_type,
            "-f", self.sample_format,
            "-r", str(self.rate),
            "-d", str(duration_s),
            file_path]

        logger.debug("Recording audio: {}".format(" ".join(cmd)))

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.wait()
        stderr = p.stderr.read()

        if p.returncode != 0:
            raise SensorNotAvailableException(
                "arecord returned {}: {}".format(p.returncode, stderr.decode()))

        logger.info("audio file written to '{}'".format(file_path))
