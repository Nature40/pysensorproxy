import os
import time

from abc import ABC, abstractmethod
from typing import Type


class Sensor:
    def __init__(self, name, storage_path, **kwargs):
        self.name = name
        self.storage_path = storage_path
        super().__init__()

    @abstractmethod
    def read(self):
        pass

    def test(self, *args, **kwargs):
        testfile_path = self.read(*args, **kwargs)
        os.remove(testfile_path)


class LogSensor(Sensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.file_path = os.path.join(self.storage_path, "{}_{}_{}.csv".format(
            int(time.time()), self.__class__.__name__, self.name))


class FileSensor(Sensor):
    def __init__(self, file_ext, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_ext = file_ext

    @property
    def file_path(self):
        return os.path.join(self.storage_path, "{}_{}_{}.{}".format(
            int(time.time()), self.__class__.__name__,
            self.name, self.file_ext))


classes = {}


def register_sensor(cls: Type[Sensor]):
    classes[cls.__name__] = cls
    return cls


class SensorNotAvailableException(Exception):
    pass
