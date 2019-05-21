import os
import time
import uuid
import csv
import logging
import threading

from abc import ABC, abstractmethod
from typing import Type
from pytimeparse import parse as parse_time

from sensorproxy.influx_helpers import influx_process

logger = logging.getLogger(__name__)


class Sensor:
    """Abstract sensor class"""

    def __init__(self, proxy, name: str, **kwargs):
        """
        Args:
            name (str): given name of the sensor
            storage_path (str): path to store files in
        """

        self.proxy = proxy
        self.name = name

        self._lock = threading.Lock()
        super().__init__()

    @abstractmethod
    def record(self, *args, height_m: float = None, count: int = 1, delay: str = "0s", **kwargs):
        """Read the sensor and write the value. """

        pass

    @abstractmethod
    def refresh(self):
        """Refresh the sensor, e.g. creating a new file."""
        pass

    @abstractmethod
    def get_file_path(self):
        pass

    @staticmethod
    def time_repr():
        """Current time, formatted."""

        return time.strftime("%Y-%m-%dT%H%M%S", time.gmtime())


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
    def _fixed_header(self):
        return ["Time (s)", ".Height (m)"]

    @property
    @abstractmethod
    def _header(self):
        """Header of the sensor readings."""

        pass

    def get_file_path(self):
        return self.__file_path

    def refresh(self):
        # basic file format cst_00001_moon-PiCamera-cam-2019-05-07T203027
        file_name = "{}-{}-{}-{}.csv".format(self.proxy.id, self.__class__.__name__,
                                             self.name, Sensor.time_repr())

        # generate and return full path
        self.__file_path = os.path.join(
            self.proxy.storage_path, self.proxy.hostname, file_name)

        with open(self.get_file_path(), "a") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(self._fixed_header + self._header)
            csv_file.flush()

    def record(self, *args, count: int = 1, delay: str = "0s", **kwargs):
        logger.debug("acquire access to {}".format(self.name))
        self._lock.acquire()
        try:
            for num in range(count):
                ts = Sensor.time_repr()
                reading = self._read(*args, **kwargs)
                self._publish(ts, reading, *args, **kwargs)

                if num == count - 1:
                    time.sleep(parse_time(delay))
        finally:
            logger.debug("release access to {}".format(self.name))
            self._lock.release()

    def _publish(self, ts, reading, *args, height_m: float = None, influx_publish: bool = False, **kwargs):
        file_path = self.get_file_path()

        with open(file_path, "a") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow([ts, height_m] + reading)
            csv_file.flush()

        if self.proxy.influx is not None and influx_publish:
            logger.info("Publishing {} metering to Influx".format(self.name))

            header = self._fixed_header + self._header
            row = [ts, height_m] + reading

            body = influx_process(self.__class__.__name__, header, row)
            tags = {"hostname": self.proxy.hostname,
                    "id": self.proxy.id,
                    "sensor": self.name, }

            try:
                self.proxy.influx.write_points(
                    points=[body], tags=tags, time_precision="s")
            except Exception as e:
                logger.warn("Publishing on infux failed: {}".format(e))

        return file_path


class FileSensor(Sensor):
    """Class for sensors logging more complex data to binary files."""

    def __init__(self, file_ext: str, *args, **kwargs):
        """
        Args:
            file_ext (str): log file extension
        """

        super().__init__(*args, **kwargs)
        self.file_ext = file_ext

    def get_file_path(self, height_m: float = None):
        """Generated file path for a sensor reading."""
        # basic file format cst_00001_moon-cam-2019-05-07T203027
        file_name = "{}-{}-{}-{}".format(self.proxy.id, self.__class__.__name__,
                                         self.name, Sensor.time_repr())

        # append height if available
        if height_m is not None:
            file_name += "-{}m".format(height_m)

        # append file extension
        file_name += ".{}".format(self.file_ext)

        # generate and return full path
        return os.path.join(self.proxy.storage_path, self.proxy.hostname, file_name)

    @abstractmethod
    def _read(self, file_path: str, *args, **kwargs):
        """Read the sensor.

        Args:
            file_path (str): path to save the file
        """

        pass

    def record(self, *args, height_m: float = None, count: int = 1, delay: str = "0s", **kwargs):
        logger.debug("acquire access to {}".format(self.name))
        self._lock.acquire()

        try:
            for num in range(count):
                file_path = self.get_file_path(height_m=height_m)
                logger.debug(
                    "running {} reading {}/{}, {} delay.".format(self.name, num, count, delay))
                self._read(file_path, *args, **kwargs)
                if num == count - 1:
                    time.sleep(parse_time(delay))

        finally:
            logger.debug("release access to {}".format(self.name))
            self._lock.release()

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
