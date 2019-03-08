import os
import time
import uuid
import csv
import logging

from abc import ABC, abstractmethod
from typing import Type

logger = logging.getLogger(__name__)


class Sensor:
    """Abstract sensor class"""

    def __init__(self, name, storage_path, **kwargs):
        """
        Args:
            name (str): given name of the sensor
            storage_path (str): path to store files in
        """

        self.name = name
        self.storage_path = storage_path
        super().__init__()

    @abstractmethod
    def record(self, *args, dry=False, **kwargs):
        """Read the sensor and write the value.

        Args:
            dry (bool): don't write the value
        """

        pass

    def refresh(self):
        """Refresh the sensor, e.g. creating a new file."""

        pass

    @staticmethod
    def time_repr():
        """Current time, formatted."""

        return time.strftime("%Y%m%d_%H%M%S", time.gmtime())


class LogSensor(Sensor):
    """Class for sensors logging simple values per record."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.refresh()

    @abstractmethod
    def _read(self, *args, **kwargs):
        """Read the sensor.

        Returns:
            [object]: Values of the sensor.
        """

        pass

    @property
    @abstractmethod
    def _header(self):
        """Header of the sensor readings."""

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
    """Class for sensors logging more complex data to binary files."""

    def __init__(self, file_ext, *args, **kwargs):
        """
        Args:
            file_ext (str): log file extension
        """

        super().__init__(*args, **kwargs)
        self.file_ext = file_ext
        self.records = []

    @property
    def file_path(self):
        """Generated file path for a sensor reading."""

        return os.path.join(self.storage_path, "{}_{}.{}".format(
            Sensor.time_repr(), self.name, self.file_ext))

    @property
    def file_path_dry(self):
        """Generated dummy file path for dry readings."""

        return os.path.join("/tmp", "{}.{}".format(uuid.uuid4(), self.file_ext))

    @abstractmethod
    def _read(self, file_path, *args, **kwargs):
        """Read the sensor.

        Args:
            file_path (str): path to save the file
        """

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
    """Add the sensor to the classes dict by its name."""
    classes[cls.__name__] = cls
    return cls


class SensorNotAvailableException(Exception):
    """Exception: cannot read sensor."""
    pass


class SensorConfigurationException(Exception):
    """Exception: configuration of the sensor doesn't work."""
    pass
