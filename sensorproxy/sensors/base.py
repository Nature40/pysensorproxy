import os
import time
import uuid
import csv
import logging
import threading

from abc import ABC, abstractmethod
from typing import Type
from pytimeparse import parse as parse_time


logger = logging.getLogger(__name__)


class Sensor:
    """Abstract sensor class"""

    def __init__(self, proxy, name: str, uses_height: bool, file_ext: str, ** kwargs):
        """
        Args:
            name (str): given name of the sensor
            storage_path (str): path to store files in
        """

        self.proxy = proxy
        self.name = name
        self.uses_height = uses_height
        self.file_ext = file_ext

        self._filename_format = "{_id}-{_class}-{_name}-{_custom}.{_file_ext}"

        self._lock = threading.Lock()
        super().__init__()

    def _generate_filename(self, custom: [str]):
        _filename_format = "{_id}-{_class}-{_name}-{_custom}.{_file_ext}"

        _id = self.proxy.id
        _class = self.__class__.__name__
        _name = self.name
        _file_ext = self.file_ext
        _custom = "-".join(custom)

        return _filename_format.format(**locals())

    @staticmethod
    def _parse_filename(filename):
        basename, _file_ext = filename.split(".")
        metadata = basename.split("-")

        tags = dict(zip(["_id", "_class", "_name"], metadata[:3]))
        # TODO: Parse tags in custom headers, e.g. height for images

        return tags

    @property
    def _header_start(self):
        if self.uses_height and self.proxy.lift:
            return ["Time (s)", "#Height (m)"]
        return ["Time (s)"]

    _header_sensor = []

    @property
    def header(self):
        return self._header_start + self._header_sensor

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
        super().__init__(*args, file_ext="csv", **kwargs)
        self.refresh()

    @abstractmethod
    def _read(self, *args, **kwargs):
        """Read the sensor.

        Returns:
            [object]: Values of the sensor.
        """

        pass

    def get_file_path(self):
        return self.__file_path

    def refresh(self):
        # generate and return full path
        file_name = self._generate_filename([Sensor.time_repr()])
        self.__file_path = os.path.join(
            self.proxy.storage_path, self.proxy.hostname, file_name)

        with open(self.get_file_path(), "a") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(self.header)
            csv_file.flush()

    def record(self, *args, count: int = 1, delay: str = "0s", **kwargs):
        logger.debug("acquire access to {}".format(self.name))
        self._lock.acquire()
        try:
            for num in range(count):
                ts = Sensor.time_repr()
                reading = self._read(*args, **kwargs)
                if len(reading) != len(self._header_sensor):
                    raise SensorNotAvailableException("Reading length ({}) does not match header length ({}).".format(
                        len(reading), len(self._header_sensor)))
                self._publish(ts, reading, *args, **kwargs)

                if num == count - 1:
                    time.sleep(parse_time(delay))
        finally:
            logger.debug("release access to {}".format(self.name))
            self._lock.release()

    def _publish(self, ts, reading, *args, influx_publish: bool = False, height_m: float = None, **kwargs):
        file_path = self.get_file_path()

        if self.uses_height and self.proxy.lift:
            row = [ts, height_m] + reading
        else:
            row = [ts] + reading

        with open(file_path, "a") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(row)
            csv_file.flush()

        if self.proxy.influx and influx_publish:
            logger.info("Publishing {} metering to Influx".format(self.name))

            try:
                self.proxy.influx.publish(
                    header=self.header,
                    row=row,
                    _class=self.__class__.__name__,
                    _hostname=self.proxy.hostname,
                    _id=self.proxy.id,
                    _sensor=self.name,
                )
            except Exception as e:
                logger.warn("Publishing on infux failed: {}".format(e))

        return file_path


class FileSensor(Sensor):
    """Class for sensors logging more complex data to binary files."""

    def get_file_path(self):
        custom = [Sensor.time_repr()]

        if self.uses_height and self.proxy.lift:
            custom.append(self.proxy.lift._current_height_m)

        file_name = self._generate_filename(custom)

        # generate and return full path
        return os.path.join(self.proxy.storage_path, self.proxy.hostname, file_name)

    @abstractmethod
    def _read(self, file_path: str, *args, **kwargs):
        """Read the sensor.

        Args:
            file_path (str): path to save the file
        """

        pass

    def record(self, *args, count: int = 1, delay: str = "0s", **kwargs):
        logger.debug("acquire access to {}".format(self.name))
        self._lock.acquire()

        try:
            for num in range(count):
                file_path = self.get_file_path()
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
