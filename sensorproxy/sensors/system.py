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
        return ["CPU Usage (%)", "CPU Temperature (°C)", "Load Average (1)", "Load Average (5)", "Load Average (15)", "Uptime (s)"]

    def _read(self, *args, **kwargs):
        logger.debug("Reading CPU usage using psutil")
        cpu_usage = psutil.cpu_percent()

        logger.debug("Reading Load Average using psutil")
        load_avg = psutil.getloadavg()

        logger.debug("Reading CPU temperature using gpiozero")
        cpu_temp = gpiozero.CPUTemperature().temperature

        logger.debug("Reading uptime from /proc/uptime")
        with open('/proc/uptime', 'r') as uptime_file:
            uptime = float(uptime_file.readline().split()[0])

        logger.info("Read {}% CPU usage at {}°C, load: {}".format(
            cpu_usage, cpu_temp, load_avg))

        return [cpu_usage, cpu_temp, *load_avg, uptime]


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
