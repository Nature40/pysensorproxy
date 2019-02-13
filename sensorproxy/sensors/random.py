import time
import os
import random

from .base import register_sensor, LogSensor, FileSensor


@register_sensor
class Random(LogSensor):
    def __init__(self, *args, maximum=100, **kwargs):
        super().__init__(*args, **kwargs)

        self.maximum = maximum

    def read(self):
        ts = time.time()

        with open(self.file_path, "a") as file:
            file.write("{},{}\n".format(
                ts, random.randint(0, self.maximum)))


@register_sensor
class RandomFile(FileSensor):
    def __init__(self, *args, **kwargs):
        super().__init__("bin", *args, **kwargs)

    def read(self, bytes):
        with open(self.file_path, "ab") as file:
            file.write(os.urandom(bytes))
