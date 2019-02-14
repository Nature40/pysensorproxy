import time
import logging

from .base import register_sensor, LogSensor, SensorNotAvailableException

log = logging.getLogger("pysensorproxy.sensors.environment")


@register_sensor
class AM2302(LogSensor):
    def __init__(self, *args, pin=23, **kwargs):
        super().__init__(*args, **kwargs)

        global Adafruit_DHT
        import Adafruit_DHT

        self.pin = pin

    def read(self):
        ts = time.time()
        log.debug("Reading AM2302 sensor on pin {}".format(self.pin))

        try:
            humidity, temp = Adafruit_DHT.read_retry(
                Adafruit_DHT.AM2302, self.pin)
        except RuntimeError as e:
            raise SensorNotAvailableException(e)

        if humidity == None or temp == None:
            raise SensorNotAvailableException(
                "No AM2302 instance on pin {}".format(self.pin))

        log.info("Read {}°C, {}% humidity".format(temp, humidity))

        with open(self.file_path, "a") as file:
            file.write("{},{},{}\n".format(ts, humidity, temp))

        return self.file_path


@register_sensor
class TSL2561(LogSensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        global tsl2561
        import tsl2561

        self.tsl2561 = tsl2561.TSL2561()
        self.tsl2561

    def read(self):
        ts = time.time()
        log.debug("Reading TSL2561 sensor via I2C")

        try:
            broadband, ir = self.tsl2561._get_luminosity()
            lux = self.tsl2561._calculate_lux(broadband, ir)
        except OSError as e:
            raise SensorNotAvailableException(e)

        log.info("Read {} lux (br: {}, ir: {})".format(lux, broadband, ir))

        with open(self.file_path, "a") as file:
            file.write("{},{},{},{}\n".format(ts, lux, broadband, ir))

        return self.file_path
