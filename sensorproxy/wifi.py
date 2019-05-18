import subprocess
import tempfile
import base64
import logging
import signal
import threading

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


class ReturncodeException(Exception):
    """Exception for invalid returncodes."""


def run(args, timeout=15, valid_returncodes=[0]):
    """Run a command

    Args:
        args ([str]): command and arguments to run
        timeout (int): maximum timeout for the command
        valid_returncodes ([int]): returncodes not raising an exception

    Raises:
        ReturncodeException: if return code is not in

    Returns:
        str: stdout of the command
    """

    logger.debug("running {}".format(" ".join(args)))
    p = subprocess.Popen(args)

    try:
        outs, errs = p.communicate(timeout=timeout)

        if p.returncode not in valid_returncodes:
            raise ReturncodeException("Returncode {} is not in list of valid ({}), stderr: {}".format(
                p.returncode, valid_returncodes, errs))

    except subprocess.TimeoutExpired as e:
        p.kill()
        outs, errs = p.communicate()
        logger.error("Process timed out, stderr: {}".format(errs))
        raise e

    return outs


class WiFiConnectionError(Exception):
    """Exception for non-successful WiFi connections."""


class WiFiManager:
    """A Class to manage WiFi connections."""

    def __init__(self, interface="wlan0"):
        """
        Args:
            interface (str): WiFi interface to be managed
        """

        self.interface = interface

        self._lock = threading.Lock()
        self.wpa_supplicant = None
        self._start_ap()

    def _start_ap(self):
        if self.wpa_supplicant is not None:
            logger.info("don't starting ap; a wpa_supplicant is running")
        else:
            run(["ifup", self.interface])
            run(["systemctl", "start", "hostapd"])

    def _stop_ap(self):
        run(["systemctl", "stop", "hostapd"])
        run(["ifdown", self.interface])

    def connect(self, wifi, timeout=30):
        """Connect to WiFi.

        Args:
            wifi (WiFi): WiFi to connect to
            timeout (int): timeout for dhclient
        """

        logger.info("requesting wifi access...")
        self._lock.acquire()

        logger.info("onnecting to wifi '{}'".format(wifi.ssid))
        if self.wpa_supplicant != None:
            self.disconnect()

        self._stop_ap()

        config_path = wifi._generate_config()
        wpa_cmd = ["wpa_supplicant", "-c", config_path, "-i", self.interface]

        logger.debug("running {}".format(" ".join(wpa_cmd)))
        self.wpa_supplicant = subprocess.Popen(wpa_cmd)

        try:
            run(["dhclient", self.interface], timeout=timeout)
            logger.info("wifi connection established")
        except Exception as e:
            self.wpa_supplicant.kill()
            self.wpa_supplicant = None

            self._start_ap()
            self._lock.release()

            logger.error("wifi connection failed: {}".format(e))
            raise WiFiConnectionError(e)

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

        self._start_ap()
        self._lock.release()


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
