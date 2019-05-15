import time
import logging

from .base import register_sensor, LogSensor, SensorNotAvailableException

logger = logging.getLogger(__name__)


@register_sensor
class LoggingHandler(logging.Handler, LogSensor):
    def __init__(self, *args, level: str = "WARNING", logger_name: str = "sensorproxy", **kwargs):
        if level.upper() not in logging._nameToLevel:
            raise SensorNotAvailableException(
                "Level must be in {}.".format(logging._nameToLevel.keys()))

        level_num = logging._nameToLevel[level.upper()]
        logging.Handler.__init__(self, level_num)
        LogSensor.__init__(self, *args, **kwargs)

        root = logging.getLogger(logger_name)
        root.addHandler(self)

    @property
    def _header(self):
        return ["Name", "Level", "Message"]

    def record(self, *args, **kwargs):
        raise SensorNotAvailableException(
            "The Logger sensor can't be called explicitly, but is called when writing to the log.")

    def emit(self, record):
        ts = self.time_repr()
        reading = [record.name, record.levelname, record.msg]
        self._publish(ts, reading)
