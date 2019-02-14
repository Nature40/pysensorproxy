import subprocess
import tempfile
import base64
import logging
import signal

logger = logging.getLogger("pysensorproxy.wifi")


class WiFi:
    def __init__(self, ssid, psk):
        self.ssid = ssid
        self.psk = psk

    def _generate_config(self):
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
    logger.debug("running {}".format(" ".join(args)))
    p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    p.wait()

    stdout = p.stdout.read().decode()
    stderr = p.stderr.read().decode()

    if p.returncode != 0:
        raise Exception("{} error {}: {}".format(
            args[0], p.returncode, stderr))

    return stdout


class WiFiManager:
    def __init__(self, interface="wlan0"):
        self.interface = interface
        self.wpa_supplicant = None

    def connect(self, wifi):
        logger.info("connecting to wifi '{}'".format(wifi.ssid))
        if self.wpa_supplicant != None:
            self.disconnect()

        config_path = wifi._generate_config()
        wpa_cmd = ["wpa_supplicant", "-c", config_path, "-i", self.interface]

        logger.debug("running {}".format(" ".join(wpa_cmd)))
        self.wpa_supplicant = subprocess.Popen(
            wpa_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        run(["dhclient", self.interface])

        logger.info("wifi connection established")

    def disconnect(self):
        logger.info("disconnecting wifi")
        run(["dhclient", "-r", self.interface])

        logger.debug("killing wpa_supplicant")
        self.wpa_supplicant.send_signal(signal.SIGINT)
        self.wpa_supplicant.wait()
        self.wpa_supplicant = None

        run(["ifconfig", self.interface, "down"])

        logger.info("wifi disconnected")


if __name__ == "__main__":
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    logger.addHandler(handler)

    wifi = WiFi("LiftSystem 949f", "supersicher")

    mgr = WiFiManager()
    mgr.connect(wifi)

    import time
    time.sleep(5)

    mgr.disconnect()
