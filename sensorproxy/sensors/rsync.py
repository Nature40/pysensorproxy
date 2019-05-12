import logging
import subprocess
import os

from .base import register_sensor, Sensor, LogSensor, SensorNotAvailableException
from sensorproxy.wifi import WiFi, WiFiManager

logger = logging.getLogger(__name__)


@register_sensor
class RsyncSender(LogSensor):
    def __init__(self, *args, ssid: str, psk: str, destination: str, **kwargs):
        super().__init__(*args, **kwargs)

        self.destination = destination
        self.wifi = WiFi(ssid, psk)

    @property
    def _header(self):
        return ["RSync Status"]

    def _rsync_cmd(self):
        cmd = ["rsync", "-avz", "--remove-source-files", "--no-relative",
               "-e", "ssh -o StrictHostKeyChecking=no"]

        local_storage_path = os.path.join(
            self.proxy.storage_path, self.proxy.hostname)
        cmd.append(os.path.join(local_storage_path, "."))
        cmd.append(os.path.join(self.destination, self.proxy.hostname))

        return cmd

    def _read(self):
        if self.proxy.wifi_mgr:
            logger.info("connecting to WiFi '{}'".format(self.wifi.ssid))
            self.proxy.wifi_mgr.connect(self.wifi)
        else:
            logger.info("WiFi is handled externally.")

        cmd = self._rsync_cmd()
        logger.info("Launching rsync: {}".format(" ".join(cmd)))

        p = subprocess.Popen(cmd)
        p.wait()

        if self.proxy.wifi_mgr:
            logger.info("disconnecting from WiFi")
            self.proxy.wifi_mgr.disconnect()

        if p.returncode != 0:
            raise SensorNotAvailableException(
                "rsync returned {}".format(p.returncode))

        # Call refresh on each Sensor.
        # This will create new filenames for each FileSensor atm.
        logger.info("refreshing sensors")
        for _, sensor in self.proxy.sensors.items():
            sensor.refresh()

        return [p.returncode]
