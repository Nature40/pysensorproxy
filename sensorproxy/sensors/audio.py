import subprocess
import logging
import os

from pytimeparse import parse as parse_time

from .base import register_sensor, FileSensor, SensorNotAvailableException, SensorConfigurationException

logger = logging.getLogger(__name__)


@register_sensor
class Microphone(FileSensor):
    def __init__(self, *args, card, device, sample_format, rate, level, **kwargs):
        super().__init__("flac", *args, **kwargs)

        self.card = card
        self.device = device
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

        cmd = "arecord -q -D {device_name} -t wav -f {sample_format} -r {rate} -d {duration_s} | flac - -r --best -s -o {file_path}".format(
                device_name=device_name,
                sample_format=self.sample_format,
                rate=self.rate,
                duration_s=duration_s,
                file_path=file_path)

        logger.debug("Recording audio: {}".format(cmd))

        p = subprocess.Popen(cmd, shell=True,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()
        err_msg = p.communicate()[0]

        if p.returncode != 0:
            raise SensorNotAvailableException(
                    "arecord returned {}: {}".format(p.returncode, err_msg))

        logger.info("audio file written to '{}'".format(file_path))
