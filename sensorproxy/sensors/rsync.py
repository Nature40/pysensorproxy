import subprocess
import logging

from .base import register_sensor, Sensor, SensorNotAvailableException

logger = logging.getLogger(__name__)


@register_sensor
class Rsync(Sensor):
    def __init__(self, *args, destination, remove_source_files, **kwargs):
        super().__init__(*args, **kwargs)

        self.destination = destination
        self.remove_source_files = remove_source_files

    def record(self, *args, dry=False, **kwargs):
        cmd = ["rsync", "-avz"]

        if self.remove_source_files:
            cmd.append("--remove-source-files")

        if dry:
            cmd.append("--dry-run")

        cmd.append(self.storage_path)
        cmd.append(self.destination)

        logger.info("Launching rsync: {}".format(" ".join(cmd)))

        p = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.wait()
        stderr = p.stderr.read()

        if p.returncode != 0:
            raise SensorNotAvailableException(
                "rsync returned {}: {}".format(p.returncode, stderr.decode()))

        for _, sensor in self.proxy.sensors.items():
            sensor.refresh()

    def refresh(self):
        pass
