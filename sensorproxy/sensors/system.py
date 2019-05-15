import time
import logging

import psutil
import gpiozero

from .base import register_sensor, LogSensor, SensorNotAvailableException

logger = logging.getLogger(__name__)


@register_sensor
class CPU(LogSensor):
    @property
    def _header(self):
        return ["CPU Usage (%)", "CPU Temperature (°C)"]

    def _read(self, *args, **kwargs):
        logger.debug("Reading CPU usage using psutil")
        cpu_usage = psutil.cpu_percent()

        logger.debug("Reading CPU temperature using gpiozero")
        cpu_temp = gpiozero.CPUTemperature().temperature

        logger.info("Read {}% CPU usage at {}°C".format(cpu_usage, cpu_temp))

        return [cpu_usage, cpu_temp]


@register_sensor
class Memory(LogSensor):
    @property
    def _header(self):
        return ["Memory Available (MiB)", "Memory Used (MiB)", "Memory Free (MiB)"]

    def _read(self, *args, **kwargs):
        logger.debug("Reading Memory usage using psutil")

        m = psutil.virtual_memory()
        logger.info("Read {}% memory in usage".format(m.percent))

        return [m.available / 1024**2, m.used / 1024**2, m.free / 1024**2]
