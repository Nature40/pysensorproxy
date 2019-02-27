import time
import logging

from .base import register_sensor, LogSensor, SensorNotAvailableException

logger = logging.getLogger(__name__)


@register_sensor
class AM2302(LogSensor):
    def __init__(self, *args, pin, **kwargs):
        super().__init__(*args, **kwargs)

        global Adafruit_DHT
        import Adafruit_DHT

        self.pin = pin

    @property
    def _header(self):
        return ["temp", "humid"]

    def _read(self):
        logger.debug("Reading AM2302 sensor on pin {}".format(self.pin))

        try:
            humid, temp = Adafruit_DHT.read_retry(
                Adafruit_DHT.AM2302, self.pin)
        except RuntimeError as e:
            raise SensorNotAvailableException(e)

        if humid == None or temp == None:
            raise SensorNotAvailableException(
                "No AM2302 instance on pin {}".format(self.pin))

        humid = round(humid, 3)
        temp = round(temp, 3)
        logger.info("Read {}°C, {}% humidity".format(temp, humid))

        return [temp, humid]


@register_sensor
class TSL2561(LogSensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        global tsl2561
        import tsl2561

        try:
            self.tsl2561 = tsl2561.TSL2561()
        except OSError:
            self.tsl2561 = None

    @property
    def _header(self):
        return ["lux", "broadband", "ir"]

    def _read(self):
        logger.debug("Reading TSL2561 sensor via i2c")

        if self.tsl2561 == None:
            try:
                self.tsl2561 = tsl2561.TSL2561()
            except OSError as e:
                raise SensorNotAvailableException(e)

        try:
            broadband, ir = self.tsl2561._get_luminosity()
            lux = self.tsl2561._calculate_lux(broadband, ir)
        except OSError as e:
            raise SensorNotAvailableException(e)

        logger.info("Read {} lux (br: {}, ir: {})".format(lux, broadband, ir))

        return [lux, broadband, ir]
