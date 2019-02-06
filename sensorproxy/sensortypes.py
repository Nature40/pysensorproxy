import time
import os
import errno

from typing import Dict, Type
from abc import ABC, abstractmethod


class Sensor:
    def __init__(self, name, storage_path, **kwargs):
        self.name = name
        self.storage_path = storage_path
        super().__init__()
    
    @abstractmethod
    def read(self):
        pass

classes: Dict[str, Type[Sensor]] = {}
def _register_sensor(cls: Type[Sensor]):
    classes[cls.__name__] = cls
    return cls

class LogSensor(Sensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.file_path = os.path.join(self.storage_path, f"{int(time.time())}_{self.__class__.__name__}_{self.name}.csv")

class FileSensor(Sensor):
    def __init__(self, file_ext, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.file_ext = file_ext

    @property
    def file_path(self):
        return os.path.join(self.storage_path, f"{int(time.time())}_{self.__class__.__name__}_{self.name}.{self.file_ext}")


import random

@_register_sensor
class Random(LogSensor):
    def __init__(self, *args, maximum=100, **kwargs):
        super().__init__(*args, **kwargs)
        self.maximum = maximum

    def read(self):
        ts = time.time()

        with open(self.file_path, "a") as file:
            file.write(f"{ts},{random.randint(0, self.maximum)}\n")

@_register_sensor
class RandomFile(FileSensor):
    def __init__(self, *args, **kwargs):
        super().__init__("bin", *args, **kwargs)

    def read(self, bytes):
        ts = int(time.time())

        with open(self.file_path, "ab") as file:
            file.write(os.urandom(bytes))



# import picamera

# @_register_sensor
# class PiCamera(Sensor):
#     def __init__(self, _format="jpeg", *args, **kwargs):
#         self._format = _format
#         super().__init__(*args, **kwargs)

#     def read(self):
#         ts = time.time()
#         file_name = os.path.join(self.storage_path, f"picam-{ts}.jpg")

#         with picamera.PiCamera() as camera:
#             camera.resolution = (3280, 2464)
#             camera.start_preview()
#             time.sleep(2)

#             camera.capture(file_name, format=self._format)
#             camera.stop_preview()
