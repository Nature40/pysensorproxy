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

        if not os.path.isdir(self._directory):
            raise SensorNotAvailableException(
                "InfluxSink's directory {} does not exist".format(
                    self._directory))

        files = [os.path.join(self._directory, f)
                 for f in os.listdir(self._directory)
                 if f.endswith('.csv')]

        for file_path in files:
            logger.info("Sending {} to InfluxDB".format(file_path))

            # convention: first part of the filename is the sensorbox id
            id = os.path.basename(file_path).split("-")[0]
            # convention: rsynced files are copied to /data/incoming/<hostname>/<id>-<timestamp>-<name>.csv
            hostname = os.path.basename(os.path.dirname(file_path))

            if not dry:
                influx.submit_file(file_path, id, hostname)

    def refresh(self):
        pass

    def get_file_path(self):
        return None
