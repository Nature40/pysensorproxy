import subprocess
import tempfile
import base64
import logging
import signal

logger = logging.getLogger(__name__)


class WiFi:
    """Class to hold configuration of a WiFi Network."""

    def __init__(self, ssid, psk):
        """
        Args:
            ssid (str): WiFi SSID
            psk (str): WiFi pre-shared key
        """

        self.ssid = ssid
        self.psk = psk

    def _generate_config(self):
        """Generates a wpa_supplicant config file from the configuration.

        Returns:
            str: path to the generated config file
        """

        base64_name = base64.encodestring(
            self.ssid.encode()).decode()[:-1]
        config_path = "/tmp/wpa_{}.conf".format(base64_name)

        logger.debug("generating wpa config at {}".format(config_path))

        p = subprocess.Popen(["wpa_passphrase", self.ssid, self.psk],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        p.wait()

        stderr = p.stderr.read()
        stdout = p.stdout.read()
        if p.returncode != 0:
            raise Exception(
                "wpa_passphrase returned {} ({})".format(p.returncode, stderr.decode()))

        with open(config_path, "wb") as config_file:
            config_file.write(stdout)
            config_file.flush()

        return config_path


def run(args):
    """Run a command

    Args:
        args ([str]): command and arguments to run

    Raises:
        Exception: if return code is not 0

    Returns:
        str: stdout of the command
    """

    logger.debug("running {}".format(" ".join(args)))
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()

    stdout = p.stdout.read()
    stderr = p.stderr.read()

    if p.returncode != 0:
        raise Exception("{} error {}: {}".format(
            args[0], p.returncode, stderr.decode()))

    return stdout.decode()


class WiFiManager:
    """A Class to manage WiFi connections."""

    def __init__(self, interface="wlan0", host_ap=True):
        """
        Args:
            interface (str): WiFi interface to be managed
        """

        self.interface = interface
        self.host_ap = host_ap

        self.wpa_supplicant = None

    def _run_ap(self, cmd):
        logger.info("{}ing an access point".format(cmd))

        hostapd_cmd = ["systemctl", cmd, "hostapd"]
        p = subprocess.Popen(hostapd_cmd, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE)
        p.wait()
        stderr = p.stderr.read()

        if p.returncode != 0:
            raise Exception("{}ing hostapd returned {}: {}".format(
                cmd, p.returncode, stderr.decode()))

    def start_ap(self):
        if self.wpa_supplicant is not None:
            logger.info("don't starting ap; a wpa_supplicant is running")
        else:
            self._run_ap("start")

    def stop_ap(self):
        self._run_ap("stop")

    def connect(self, wifi, timeout="30"):
        """Connect to WiFi.

        Args:
            wifi (WiFi): WiFi to connect to
            timeout (int): timeout for dhclient
        """

        logger.info("connecting to wifi '{}'".format(wifi.ssid))
        if self.wpa_supplicant != None:
            self.disconnect()

        self.stop_ap()

        config_path = wifi._generate_config()
        wpa_cmd = ["wpa_supplicant", "-c", config_path, "-i", self.interface]

        logger.debug("running {}".format(" ".join(wpa_cmd)))
        self.wpa_supplicant = subprocess.Popen(wpa_cmd)

        try:
            run(["timeout", timeout, "dhclient", self.interface])
            logger.info("wifi connection established")
        except Exception as e:
            self.wpa_supplicant.kill()
            logger.error("wifi connection failed: {}".format(e))

            self.start_ap()

    def disconnect(self):
        """Disconnect from current WiFi"""

        logger.info("disconnecting wifi")
        run(["dhclient", "-r", self.interface])

        logger.debug("killing wpa_supplicant")
        self.wpa_supplicant.send_signal(signal.SIGINT)
        self.wpa_supplicant.wait()
        self.wpa_supplicant = None

        run(["ifconfig", self.interface, "down"])

        logger.info("wifi disconnected")

        self.start_ap()


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    wifi = WiFi("nature40.liftsystem.34a4", "supersicher")

    mgr = WiFiManager()
    mgr.connect(wifi)

    import time
    time.sleep(5)

    mgr.disconnect()
