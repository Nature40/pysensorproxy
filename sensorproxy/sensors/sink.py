import os
import logging

from .base import register_sensor, Sensor, SensorNotAvailableException
from sensorproxy.influx_api import InfluxAPI

logger = logging.getLogger(__name__)


@register_sensor
class Sink(Sensor):
    """ Sink consumes all files from a given directory and publishes their content 
    via different methods, including InfluxDB (more yet to come). After beeing consumed
    the files are moved away from the incoming directory.
    """

    def __init__(self, *args, input_directory, **kwargs):
        super().__init__(*args, **kwargs)

        # create input directory
        try:
            os.makedirs(input_directory)
        except FileExistsError:
            pass

        # allow everybody to write to input directory
        os.chmod(input_directory, 0o777)

        self.input_directory = input_directory

    def _consume_influx(self, influx: InfluxAPI, hostname: str, id: str, file_path: str, dry: bool = False):
        if not file_path.endswith(".csv"):
            logger.debug("ignoring non-csv file")
            return

        logger.info("Sending {} to InfluxDB".format(file_path))
        if not dry:
            influx.submit_file(file_path, id, hostname)

    def record(self, *args, dry: bool = False, influx: InfluxAPI = None, influx_publish: bool = True, ** kwargs):
        if not os.path.isdir(self.input_directory):
            raise SensorNotAvailableException(
                "Input directory '{}' is not existing.".format(self.input_directory))

        for hostname in os.listdir(self.input_directory):
            host_dir_input = os.path.join(self.input_directory, hostname)

            # ignore files in the input directory
            if not os.path.isdir(host_dir_input):
                continue

            logger.info("consuming data from {}".format(hostname))

            # create host directory
            host_dir = os.path.join(self.proxy.storage_path, hostname)
            try:
                os.makedirs(host_dir)
            except FileExistsError:
                pass

            for file_name in os.listdir(host_dir_input):
                file_path_incoming = os.path.join(host_dir_input, file_name)

                # convention: first part of the filename is the sensorbox id
                id = file_name.split("-")[0]

                # call the different consumers
                if influx_publish:
                    self._consume_influx(
                        influx, hostname, id, file_path_incoming, dry)

                # move the file away to avoid double-consumption
                if not dry:
                    file_path = os.path.join(host_dir, file_name)
                    os.rename(file_path_incoming, file_path)

    def refresh(self):
        pass

    def get_file_path(self):
        return None
