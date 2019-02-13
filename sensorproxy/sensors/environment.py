import time

from .base import register_sensor, LogSensor, SensorNotAvailableException


@register_sensor
class AM2302(LogSensor):
    def __init__(self, *args, pin=23, **kwargs):
        super().__init__(*args, **kwargs)

        global Adafruit_DHT
        import Adafruit_DHT

        self.pin = pin

    def read(self):
        ts = time.time()

        try:
            humidity, temp = Adafruit_DHT.read_retry(
                Adafruit_DHT.AM2302, self.pin)
        except RuntimeError as e:
            raise SensorNotAvailableException(e)

        if humidity == None or temp == None:
            raise SensorNotAvailableException(
                "No AM2302 instance on pin {}".format(self.pin))

        with open(self.file_path, "a") as file:
            file.write("{},{},{}\n".format(ts, humidity, temp))

        return self.file_path


@register_sensor
class TSL2561(LogSensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        global tsl2561
        import tsl2561

    def read(self):
        ts = time.time()
        try:
            lux = tsl2561.TSL2561().lux()
        except OSError as e:
            raise SensorNotAvailableException(e)

        with open(self.file_path, "a") as file:
            file.write("{},{}\n".format(ts, lux))

        return self.file_path
