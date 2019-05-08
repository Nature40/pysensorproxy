import logging
import subprocess
import os

from sensorproxy.wifi import WiFi


logger = logging.getLogger(__name__)


class RsyncException(Exception):
    pass


class RsyncSender:
    def __init__(self, proxy, mgr, ssid, psk, destination, start_time):
        self.proxy = proxy
        self.mgr = mgr
        self.destination = destination
        self.start_time = start_time

        self.wifi = WiFi(ssid, psk)

    def _rsync_cmd(self, dry):
        cmd = ["rsync", "-avz", "--remove-source-files", "--no-relative",
               "-e", "ssh -o StrictHostKeyChecking=no"]

        if dry:
            cmd.append("--dry-run")

        local_storage_path = os.path.join(
            self.proxy.storage_path, self.proxy.hostname)
        cmd.append(os.path.join(local_storage_path, "."))
        cmd.append(os.path.join(self.destination, self.proxy.hostname))

        return cmd

    def sync(self, dry=False):
        if self.mgr and not dry:
            logger.info("connecting to WiFi '{}'".format(self.wifi.ssid))
            self.mgr.connect(self.wifi)
        else:
            logger.info("WiFi is handled externally, dry: {}".format(dry))

        cmd = self._rsync_cmd(dry)
        logger.info("Launching rsync: {}".format(" ".join(cmd)))

        p = subprocess.Popen(cmd)
        p.wait()

        if self.mgr and not dry:
            logger.info("disconnecting from WiFi")
            self.mgr.disconnect()

        if p.returncode != 0:
            raise RsyncException("rsync returned {}".format(p.returncode))

        # Call refresh on each Sensor.
        # This will create new filenames for each FileSensor atm.
        for _, sensor in self.proxy.sensors.items():
            sensor.refresh()
