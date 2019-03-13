import socket
import time
import logging
import threading

import RPi.GPIO as gpio

from sensorproxy.wifi import WiFi, WiFiManager

logger = logging.getLogger(__name__)


class MovingException(Exception):
    """Exception: lift cannot move further in the requested direction."""
    pass


class LiftConnectionException(Exception):
    """Exception: failed lift connections."""
    pass


class UnknownReponseException(LiftConnectionException):
    """Exception: unknown response from a lift."""
    pass


class WrongSpeedResponseException(LiftConnectionException):
    """Exception: wrong speed returned by the lift."""
    pass


class LiftSocketCommunicationException(LiftConnectionException):
    """Exception: socket error occured while communicating with the lift."""
    pass


class ResponseTimeoutException(LiftConnectionException):
    """Exception: no response from the lift for defined time."""
    pass


class Lift:
    """Class representing a lift and its configuration."""

    def __init__(self, mgr, ssid, psk, hall_bottom_pin, hall_top_pin, ip="192.168.3.254", port=35037, update_interval_s=0.05, timeout_s=0.5):
        """
        Args:
            mgr (WiFiManager): WiFi manager to be used to connect
            ssid (str): WiFi SSID of the LiftSystem
            psk (str): WiFi pre-shared key of the LiftSystem
            hall_bottom_pin (int): GPIO pin of the bottom hall sensor
            hall_top_pin (int): GPIO pin of the top hall sensor
            ip (str): IP address of the LiftSystem
            update_interval_s (float): interval between lift speed updates
            timeout_s (float): speed commands timeout configured on the LiftSystem

        Examples:
            The lift can be instanciated without a WiFi configured, leaving the 
            WiFi configuration untouched. In the example the lift calibrates 
            itself, moving to the bottom, then to the top and back to the bottom 
            to measure the travel time. 

            >>> l = Lift(None, "nature40.liftsystem.abcd", "supersicher", 5, 6)
            >>> l.calibrate()
        """

        self.mgr = mgr
        self.ip = ip
        self.port = port
        self.hall_bottom_pin = hall_bottom_pin
        self.hall_top_pin = hall_top_pin
        self.update_interval_s = update_interval_s
        self.timeout_s = timeout_s

        self.wifi = WiFi(ssid, psk)
        self.sock = None

        self.time_up_s = None
        self.time_down_s = None
        self._current_speed = None
        self._last_response_ts = None
        self.lock = threading.Lock()

        gpio.setmode(gpio.BCM)
        gpio.setup(hall_bottom_pin, gpio.IN)
        gpio.setup(hall_top_pin, gpio.IN)

    def __repr__(self):
        return "Lift {}".format(self.wifi.ssid)

    def connect(self, dry=False, timeout=10):
        """Connect to the configured lift.

        Args:
            dry (bool): Don't connect to configured WiFi.

        Raises:
            LiftSocketCommunicationException: if no response from lift on initial connect
        """

        if self.mgr and not dry:
            logger.info("connecting to '{}'".format(self.wifi.ssid))
            self.mgr.connect(self.wifi)
        else:
            logger.info("wifi is handled externally")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

        self._send_speed(0)

        start_ts = time.time()
        while self._current_speed == None:
            if start_ts + timeout < time.time():
                raise LiftSocketCommunicationException(
                    "No response in {}s from lift in initial connect".format(timeout))
            self._recv_responses()

        logger.info("connection to '{}' established".format(self.wifi.ssid))

    def disconnect(self, dry=False):
        """Disconnect from the configured lift.

        dry (bool): Don't disconnect from configured WiFi.
        """

        logger.info("disconnecting from lift")
        self.sock.close()
        self.sock = None

        if self.mgr and not dry:
            self.mgr.disconnect()

    @property
    def hall_bottom(self):
        """Value of the bottom hall sensor."""

        return gpio.input(self.hall_bottom_pin)

    @property
    def hall_top(self):
        """Value of the top hall sensor."""

        return gpio.input(self.hall_top_pin)

    def _check_limits(self, speed: int):
        """Check if the lift can move in the requested direction.

        Args:
            speed (int): speed to be set

        Raises:
            MovingException: If the lift cannot move in the requested direction.
        """

        if speed > 0 and self.hall_top:
            raise MovingException("cannot move upwards, reached sensor.")

        if speed < 0 and self.hall_bottom:
            raise MovingException("cannot move downwards, reached sensor.")

    def _check_timeout(self):
        """Check if the lift has timed out.

        Raises:
            ResponseTimeoutException: If the lift did not respond in time.
        """

        delay = time.time() - self._last_response_ts
        if delay > self.timeout_s:
            raise ResponseTimeoutException(
                "No response since {} s.".format(delay))

    def _send_speed(self, speed: int):
        """Send a speed command to the connected lift.

        Args:
            speed (int): speed to be send

        Raises:
            LiftConnectionException: If not connected to a lift.
            LiftSocketCommunicationException: If the speed command could not be send.
        """

        if not self.sock:
            raise LiftConnectionException("not connected to a lift")

        self._check_limits(speed)

        logger.debug("sending speed {}".format(speed))
        request = "speed {}".format(speed).encode()
        try:
            self.sock.sendto(request, (self.ip, self.port))
        except OSError as e:
            raise LiftSocketCommunicationException(
                "Sending speed failed: {}".format(e))

    def _recv_responses(self):
        """Receive latest responses from the connected lift.

        Raises:
            LiftConnectionException: If not connected to a lift.
            UnknownReponseException: If the response is unknown.
        """

        if not self.sock:
            raise LiftConnectionException("not connected to a lift")

        while True:
            try:
                response = self.sock.recvfrom(65565)[0].decode()
                self._last_response_ts = time.time()
            except BlockingIOError:
                return

            logger.debug("received '{}'".format(response.strip()))
            cmd, speed_response_str = response.split()

            if cmd == "set":
                speed_response = int(speed_response_str)
                self._current_speed = speed_response
            else:
                raise UnknownReponseException("Response: '{}'".format(cmd))

    def move(self, speed: int):
        """Move the lift with the given speed until the top or bottom is reached.

        Args:
            speed (int): speed to move the lift with, (-255, 255)

        Returns:
            float: Time the lift moved until the end was reached.
        """

        logger.info("moving lift with speed {}".format(speed))
        ride_start_ts = time.time()

        while True:
            try:
                self._send_speed(speed)
                self._recv_responses()
                self._check_timeout()

            except LiftConnectionException as e:
                logger.warn("Lift command exception: {}".format(e))

            except MovingException as e:
                ride_end_ts = time.time()
                travel_time_s = ride_end_ts - ride_start_ts
                logger.info("end reached in {}s".format(travel_time_s))
                break

            time.sleep(self.update_interval_s)

        return travel_time_s

    def calibrate(self):
        """Calibrate the lift travel times, by moving fully up and back down."""

        logger.info("calibrating lift, starting at the bottom")
        self.move(-255)

        logger.info("moving lift to top")
        self.time_up_s = self.move(255)
        logger.info("goint back to bottom")
        self.time_down_s = self.move(-255)

        logger.info("calibration finished, {}s to the top, {}s back to bottom".format(
            self.time_up_s, self.time_down_s))


if __name__ == "__main__":
    logger = logging.getLogger("pysensorproxy")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    mgr = None
    mgr = WiFiManager(interface="wlan0")

    lift = Lift(
        mgr=mgr,
        ssid="nature40.liftsystem.34a4",
        psk="supersicher",
        ip="192.168.3.254",
        port=35037,
        hall_bottom_pin=5,
        hall_top_pin=6,
        update_interval_s=0.1)

    try:
        lift.connect()
        lift.calibrate()
        lift.disconnect()
    except LiftConnectionException as e:
        logger.error("Couldn't connect to lift: {}".format(e))
