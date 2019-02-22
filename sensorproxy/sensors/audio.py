import subprocess
import logging
import os

from pytimeparse import parse as parse_time

from .base import register_sensor, FileSensor, SensorNotAvailableException, SensorConfigurationException

logger = logging.getLogger(__name__)


@register_sensor
class Microphone(FileSensor):
    def __init__(self, *args, card, device, file_type, sample_format, rate, level, **kwargs):
        super().__init__(file_type, *args, **kwargs)

        self.card = card
        self.device = device
        self.file_type = file_type
        self.sample_format = sample_format
        self.rate = rate

        self._set_volume(level)

    def _set_volume(self, level):
        cmd = [
            "amixer",
            "-c", str(self.card),
            "sset",
            "Mic",
            str(level)]

        logger.debug("Setting microphone level: {}".format(" ".join(cmd)))

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.wait()
        stderr = p.stderr.read()

        if p.returncode != 0:
            raise SensorConfigurationException(
                "amixer returned {}: {}".format(p.returncode, stderr.decode()))

    def _read(self, file_path, duration):
        device_name = "hw:{},{}".format(self.card, self.device)
        duration_s = parse_time(duration)

        cmd = [
            "arecord",
            "-D", device_name,
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
