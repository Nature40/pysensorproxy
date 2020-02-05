import select
import logging
import threading
import subprocess

from time import sleep
from systemd import journal
from .base import register_sensor, LogSensor, SensorNotAvailableException

logger = logging.getLogger(__name__)


@register_sensor
class LoggingHandler(logging.Handler, LogSensor):
    def __init__(self, *args, level: str = "WARNING", logger_name: str = "sensorproxy", influx_publish=False, **kwargs):
        if level.upper() not in logging._nameToLevel:
            raise SensorNotAvailableException(
                "Level must be in {}.".format(logging._nameToLevel.keys()))

        level_num = logging._nameToLevel[level.upper()]
        logging.Handler.__init__(self, level_num)
        LogSensor.__init__(self, *args, uses_height=False, **kwargs)

        root = logging.getLogger(logger_name)
        root.addHandler(self)

        self.influx_publish = influx_publish

    _header_sensor = [
        "#Name",
        "#Level",
        "Message",
    ]

    def record(self, *args, **kwargs):
        raise SensorNotAvailableException(
            "The Logger sensor can't be called explicitly, but is called when writing to the log.")

    def emit(self, record):
        # influx publishing can be overwritten by supplying the extra argument in a dict
        # logger.warning("test", {"influx_publish": False})

        ts = self.time_repr()
        reading = [record.name, record.levelname, record.msg]

        if (record.args != None) and isinstance(record.args, dict) and "influx_publish" in record.args:
            self._publish(ts, reading, **record.args)
        else:
            self._publish(ts, reading, influx_publish=self.influx_publish)


@register_sensor
class Dmesg(LogSensor):
    def __init__(self, influx_publish=True, *args, **kwargs):
        super().__init__(*args, uses_height=False, **kwargs)
        self.influx_publish = influx_publish

        read_journal_ctl_thread = threading.Thread(target=self.__read_journal_ctl, args=())
        read_journal_ctl_thread.start()

        _header_sensor = [
            "#Message"
        ]

    def __read_journal_ctl(self):
        reader = journal.Reader()
        reader.log_level(journal.LOG_INFO)

        reader.seek_tail()
        reader.get_previous()

        poll = select.poll()
        poll.register(reader, reader.get_events())

        while poll.poll():
            if reader.process() != journal.APPEND:
                continue

            for entry in reader:
                message = str(entry['MESSAGE'])
                if message != "":
                    self.__store_message(message)

    def __store_message(self, message):
        ts = self.time_repr()
        self._publish(ts, [message], influx_publish=self.influx_publish)

    def record(self, *args, **kwargs):
        raise SensorNotAvailableException(
            "The Logger sensor can't be called explicitly, but is called when writing to the log.")

@register_sensor
class VcgencmdWatchDog(LogSensor):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, uses_height=False, **kwargs)
        self.influx_publish = True

    _header_sensor = [
        "Temperature (°C)",
        "Voltage (V)",
        "CPU Frequency (Hz)",
        "Throttled (Boolean)"
    ]

    def _read(self, *args, **kwargs):
        return [
            subprocess.check_output(["vcgencmd", "measure_temp"]).split("=")[1][:-3],
            subprocess.check_output(["vcgencmd", "measure_volts"]).split("=")[1][:-2],
            subprocess.check_output(["vcgencmd", "measure_clock arm"]).split("=")[1][:-1],
            subprocess.check_output(["vcgencmd", "get_throttled"]).split("=")[1][2:-1]
        ]
