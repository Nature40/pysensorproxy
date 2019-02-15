import os
import time
import uuid
import csv

from abc import ABC, abstractmethod
from typing import Type


class Sensor:
    def __init__(self, name, storage_path, **kwargs):
        self.name = name
        self.storage_path = storage_path
        super().__init__()

    @abstractmethod
    def record(self, *args, dry=False, **kwargs):
        pass


class LogSensor(Sensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.file_path = os.path.join(self.storage_path, "{}_{}.csv".format(
            int(time.time()), self.name))

        with open(self.file_path, "a") as file:
            writer = csv.writer(file)
            writer.writerow(["ts"] + self._header)

    @abstractmethod
    def _read(self, *args, **kwargs):
        pass

    @property
    @abstractmethod
    def _header(self):
        pass

    def record(self, *args, dry=False, **kwargs):
        ts = time.time()
        reading = self._read(*args, **kwargs)

        if not dry:
            with open(self.file_path, "a") as file:
                writer = csv.writer(file)
                writer.writerow([ts] + reading)

        return self.file_path


class FileSensor(Sensor):
    def __init__(self, file_ext, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_ext = file_ext

    @property
    def file_path(self):
        return os.path.join(self.storage_path, "{}_{}.{}".format(
            int(time.time()), self.name, self.file_ext))

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
            file_path = None

        return file_path


classes = {}


def register_sensor(cls: Type[Sensor]):
    classes[cls.__name__] = cls
    return cls


class SensorNotAvailableException(Exception):
    pass
