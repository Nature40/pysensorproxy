import time
import os
import random
import logging

from .base import register_sensor, LogSensor, FileSensor

logger = logging.getLogger(__name__)


@register_sensor
class Random(LogSensor):
    def __init__(self, *args, maximum=100, **kwargs):
        super().__init__(*args, **kwargs)

        self.maximum = maximum

    @property
    def _header(self):
        return ["int"]

    def _read(self, *args, **kwargs):
        return [random.randint(0, self.maximum)]


@register_sensor
class RandomFile(FileSensor):
    def __init__(self, *args, **kwargs):
        super().__init__("bin", *args, **kwargs)

    def _read(self, file_path, bytes, *args, **kwargs):
        with open(file_path, "ab") as file:
            file.write(os.urandom(bytes))

        return file_path
