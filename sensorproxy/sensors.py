import time
import os

from typing import Dict, Type
from abc import ABC, abstractmethod


class Sensor:
    def __init__(self, path):
        self._path = path
        super().__init__()
    
    @abstractmethod
    def read(self):
        pass

sensors: Dict[str, Type[Sensor]] = {}
def _register_sensor(cls: Type[Sensor]):
    sensors[cls.__name__] = cls
    return cls


import random

@_register_sensor
class RandomSensor(Sensor):
    def __init__(self, maximum=100, *args, **kwargs):
        self._maximum = maximum
        super().__init__(*args, **kwargs)

    def read(self):
        ts = time.time()
        file_name = os.path.join(self._path, f"random.csv")

        with open(file_name, "a") as file:
            file.write(f"{ts},{random.randint(0, self._maximum)}")



# import picamera

# @_register_sensor
# class PiCamera(Sensor):
#     def __init__(self, _format="jpeg", *args, **kwargs):
#         self._format = _format
#         super().__init__(*args, **kwargs)

#     def read(self):
#         ts = time.time()
#         file_name = os.path.join(self._path, f"picam-{ts}.jpg")

#         with picamera.PiCamera() as camera:
#             camera.resolution = (3280, 2464)
#             camera.start_preview()
#             time.sleep(2)

#             camera.capture(file_name, format=self._format)
#             camera.stop_preview()
