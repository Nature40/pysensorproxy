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


classes = {}


def _register_sensor(cls: Type[Sensor]):
    classes[cls.__name__] = cls
    return cls


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


@_register_sensor
class Random(LogSensor):
    def __init__(self, *args, maximum=100, **kwargs):
        super().__init__(*args, **kwargs)
        self.maximum = maximum

    def read(self):
        import random

        ts = time.time()

        with open(self.file_path, "a") as file:
            file.write("{},{}\n".format(ts, random.randint(0, self.maximum)))


@_register_sensor
class RandomFile(FileSensor):
    def __init__(self, *args, **kwargs):
        super().__init__("bin", *args, **kwargs)

    def read(self, bytes):
        import random

        ts = int(time.time())

        with open(self.file_path, "ab") as file:
            file.write(os.urandom(bytes))


@_register_sensor
class AM2302(LogSensor):
    def __init__(self, *args, pin=23, **kwargs):
        super().__init__(*args, **kwargs)
        self.pin = pin

    def read(self):
        import Adafruit_DHT

        ts = time.time()
        humidity, temp = Adafruit_DHT.read_retry(Adafruit_DHT.AM2302, self.pin)

        with open(self.file_path, "a") as file:
            file.write("{},{},{}\n".format(ts, humidity, temp))


@_register_sensor
class TSL2561(LogSensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def read(self):
        import tsl2561

        ts = time.time()
        lux = tsl2561.TSL2561().lux()

        with open(self.file_path, "a") as file:
            file.write("{},{}\n".format(ts, lux))


@_register_sensor
class Microphone(FileSensor):
    def __init__(self, *args, device_name="hw:1,0", file_type="wav",
                 duration_sec=30, format="S16_LE", rate=44100, **kwargs):
        super().__init__(file_type, *args, **kwargs)
        self.device_name = device_name
        self.file_type = file_type
        self.duration_sec = duration_sec
        self.format = format
        self.rate = rate

    def read(self):
        import subprocess

        subprocess.run([
            "arecord",
            "-D", self.device_name,
            "-t", self.file_type,
            "-d", str(self.duration_sec),
            "-f", self.format,
            "-r", str(self.rate),
            self.file_path])


@_register_sensor
class Camera(FileSensor):
    def __init__(self, *args, format="jpeg", **kwargs):
        super().__init__(format, *args, **kwargs)
        self.format = format

    def read(self):
        import picamera

        with picamera.PiCamera() as camera:
            camera.resolution = (3280, 2464)
            camera.start_preview()
            time.sleep(2)

            camera.capture(self.file_path, format=self.format)
            camera.stop_preview()
