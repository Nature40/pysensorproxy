import os
import logging

from .base import register_sensor, Sensor, SensorNotAvailableException
from sensorproxy.influx_api import InfluxAPI

logger = logging.getLogger(__name__)


@register_sensor
class InfluxSink(Sensor):
    """ InfluxSink consumes all csv files from a given directory and publishes
        their content to an InfluxDB. Therefore a global `influx` configuration
        must exist inside of `sensorproxy.yml`.
    """

    def __init__(self, *args, directory, **kwargs):
        super().__init__(*args, **kwargs)
        self._directory = directory

    def record(self, *args, dry: bool = False, influx: InfluxAPI = None, **kwargs):
        if influx is None:
            raise SensorNotAvailableException(
                    "InfluxSink received an empty `influx` object")

        files = [os.path.join(self._directory, f)
                 for f in os.listdir(self._directory)
                 if f.endswith('.csv')]

        for f in files:
            logger.info("Sending {} to InfluxDB".format(f))
            if not dry:
                influx.submit_file(f, "test1")  # TODO: sensor's name

    def refresh(self):
        pass

    def get_file_path(self):
        return None
