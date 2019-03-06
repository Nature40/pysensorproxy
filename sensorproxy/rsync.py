import logging
import schedule
import subprocess

from sensorproxy.wifi import WiFi


logger = logging.getLogger(__name__)


class RsyncException(Exception):
    pass


class RsyncSender:
    def __init__(self, proxy, mgr, ssid, psk, destination, start_time):
        self.proxy = proxy
        self.mgr = mgr
        self.ssid = ssid
        self.psk = psk
        self.destination = destination

        self.wifi = WiFi(ssid, psk)
        schedule.every().day.at(start_time).do(self.sync)

    def _rsync_cmd(self, dry):
        cmd = ["rsync", "-avz", "--remove-source-files"]

        if dry:
            cmd.append("--dry-run")

        cmd.append(self.proxy.storage_path)
        cmd.append(self.destination)

        return cmd

    def sync(self, dry=False):
        if self.mgr and not dry:
            logger.info("connecting to WiFi '{}'".format(self.wifi.ssid))
            self.mgr.connect(self.wifi)
        else:
            logger.info("WiFi is handled externally, dry: {}".format(dry))

        cmd = self._rsync_cmd(dry)
        logger.info("Launching rsync: {}".format(" ".join(cmd)))

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.wait()
        stderr = p.stderr.read()

        if self.mgr and not dry:
            logger.info("disconnecting from WiFi")
            self.mgr.disconnect()

        if p.returncode != 0:
            raise RsyncException("rsync returned {}: {}".format(
                p.returncode, stderr.decode()))

        # Call refresh on each Sensor.
        # This will create new filenames for each FileSensor atm.
        for _, sensor in self.proxy.sensors.items():
            sensor.refresh()
