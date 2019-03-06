import os
import time
import uuid
import csv
import logging

from abc import ABC, abstractmethod
from typing import Type

logger = logging.getLogger(__name__)


class Sensor:
    def __init__(self, name, storage_path, **kwargs):
        self.name = name
        self.storage_path = storage_path
        super().__init__()

    @abstractmethod
    def record(self, *args, dry=False, **kwargs):
        pass

    def refresh(self):
        pass

    @staticmethod
    def time_repr():
        return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


class LogSensor(Sensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.refresh()

    @abstractmethod
    def _read(self, *args, **kwargs):
        pass

    @property
    @abstractmethod
    def _header(self):
        pass

    def record(self, *args, dry=False, **kwargs):
        ts = Sensor.time_repr()
        reading = self._read(*args, **kwargs)

        if not dry:
            with open(self.file_path, "a") as file:
                writer = csv.writer(file)
                writer.writerow([ts] + reading)

        return self.file_path

    def refresh(self):
        self.file_path = os.path.join(self.storage_path, "{}_{}.csv".format(
            Sensor.time_repr(), self.name))

        with open(self.file_path, "a") as file:
            writer = csv.writer(file)
            writer.writerow(["ts"] + self._header)


class FileSensor(Sensor):
    def __init__(self, file_ext, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_ext = file_ext
        self.records = []

    @property
    def file_path(self):
        return os.path.join(self.storage_path, "{}_{}.{}".format(
            Sensor.time_repr(), self.name, self.file_ext))

    @property
    def file_path_dry(self):
        return os.path.join("/tmp", "{}.{}".format(uuid.uuid4(), self.file_ext))

    @abstractmethod
    def _read(self, file_path, *args, **kwargs):
        pass

    def record(self, *args, dry=False, **kwargs):
        file_path = self.file_path

        if dry:
            file_path = self.file_path_dry

        self._read(file_path, *args, **kwargs)

        if dry:
            os.remove(file_path)
            return None

        self.records.append(os.path.split(file_path)[1])
        return file_path


classes = {}


def register_sensor(cls: Type[Sensor]):
    classes[cls.__name__] = cls
    return cls


class SensorNotAvailableException(Exception):
    pass


class SensorConfigurationException(Exception):
    pass
