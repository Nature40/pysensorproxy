import os
import logging

from .base import register_sensor, Sensor, SensorNotAvailableException
from sensorproxy.influx_api import InfluxAPI

logger = logging.getLogger(__name__)


@register_sensor
class InfluxSink(Sensor):
    def __init__(self, *args, host, port, user, password, db, path, directory, ssl, **kwargs):
        super().__init__(*args, **kwargs)

        self._influx = InfluxAPI(host, port, user, password, db, path, ssl)
        self._directory = directory

        logger.info("Started Influx on {}".format(self._influx.client._baseurl))

    def record(self, *args, dry: bool = False, height_m: float = None, **kwargs):
        logger.info("Recording InfluxSink..")
        files = [os.path.join(self._directory, f)
                 for f in os.listdir(self._directory)
                 if f.endswith('.csv')]

        for f in files:
            logger.info("Sending {} to InfluxDB".format(f))
            if not dry:
                self._influx.submit_file(f, "test1")

    def refresh(self):
        logger.info("Refreshing InfluxSink..")

    def publish(self, **kwargs):
        pass

    def get_file_path(self):
        logger.info("Fetching FilePath for InfluxSink..")
