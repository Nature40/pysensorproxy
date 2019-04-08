import socket
import time
import logging
import threading

import RPi.GPIO as gpio

from sensorproxy.wifi import WiFi, WiFiManager

logger = logging.getLogger(__name__)


class _MovingException(Exception):
    """Exception: lift cannot move further in the requested direction."""
    pass


class LiftConnectionException(Exception):
    """Exception: failed lift connections."""
    pass


class _UnknownReponseException(LiftConnectionException):
    """Exception: unknown response from a lift."""
    pass


class _LiftSocketCommunicationException(LiftConnectionException):
    """Exception: socket error occured while communicating with the lift."""
    pass


class _ResponseTimeoutException(LiftConnectionException):
    """Exception: no response from the lift for defined time."""
    pass


class Lift:
    """Class representing a lift and its configuration."""

    def __init__(self, mgr: WiFiManager, height: float, ssid: str, psk: str = "supersicher", hall_bottom_pin: int = 5, hall_top_pin: int = 6, ip: str = "192.168.3.254", port: int = 35037, update_interval_s: float = 0.05, timeout_s: float = 0.5):
        """
        Args:
            mgr (WiFiManager): WiFi manager to be used to connect
            height (float): Highest point the lift can reach, used for calibration
            ssid (str): WiFi SSID of the LiftSystem
            psk (str): WiFi pre-shared key of the LiftSystem
            hall_bottom_pin (int): GPIO pin of the bottom hall sensor
            hall_top_pin (int): GPIO pin of the top hall sensor
            ip (str): IP address of the LiftSystem
            port (int): server port of the LiftSystem
            update_interval_s (float): interval between lift speed updates
            timeout_s (float): speed commands timeout configured on the LiftSystem

        Examples:
            The lift can be instanciated without a WiFi configured, leaving the 
            WiFi configuration untouched. In the example the lift calibrates 
            itself, moving to the bottom, then to the top and back to the bottom 
            to measure the travel time. 

            >>> l = Lift(None, 12.6, "nature40.liftsystem.1337")
            >>> l.calibrate()
        """

        # mandatory parameters
        self.mgr = mgr
        self.height = height
        self.wifi = WiFi(ssid, psk)

        # optional (defaultable parameters)
        self.hall_bottom_pin = hall_bottom_pin
        self.hall_top_pin = hall_top_pin
        self.ip = ip
        self.port = port
        self.update_interval_s = update_interval_s
        self.timeout_s = timeout_s

        # calibration variables
        self._time_up_s = None
        self._time_down_s = None
        self._current_height_m = None

        # runtime variables
        self.lock = threading.Lock()
        self._sock = None
        self._current_speed = None
        self._last_response_ts = None

        # gpio initialization
        gpio.setmode(gpio.BCM)
        gpio.setup(hall_bottom_pin, gpio.IN)
        gpio.setup(hall_top_pin, gpio.IN)

    def __repr__(self):
        return "Lift {}".format(self.wifi.ssid)

    def connect(self, dry: bool = False, timeout_s: float = 10):
        """Connect to the configured lift.

        Args:
            dry (bool): don't connect to configured WiFi
            timeout (float): timeout for connection attempts

        Raises:
            LiftSocketCommunicationException: if no response from lift on initial connect
        """

        logger.debug("Requesting lift access.")
        self.lock.acquire()

        if self.mgr and not dry:
            logger.info("connecting to '{}'".format(self.wifi.ssid))
            self.mgr.connect(self.wifi)
        else:
            logger.info("wifi is handled externally")

        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._sock.setblocking(False)

        self._send_speed(0)

        start_ts = time.time()
        while self._current_speed == None:
            if start_ts + timeout_s < time.time():
                raise _LiftSocketCommunicationException(
                    "No response in {}s from lift in initial connect".format(timeout_s))
            self._recv_responses()

        logger.info("connection to '{}' established".format(self.wifi.ssid))

    def disconnect(self, dry: bool = False):
        """Disconnect from the configured lift.

        dry (bool): Don't disconnect from configured WiFi.
        """

        logger.info("disconnecting from lift")
        self._sock.close()
        self._sock = None

        if self.mgr and not dry:
            self.mgr.disconnect()

        logger.debug("Releasing lift access.")
        self.lock.release()

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
            self._current_height_m = self.height
            raise _MovingException("cannot move upwards, reached sensor.")

        if speed < 0 and self.hall_bottom:
            self._current_height_m = 0.0
            raise _MovingException("cannot move downwards, reached sensor.")

    def _check_timeout(self):
        """Check if the lift has timed out.

        Raises:
            ResponseTimeoutException: If the lift did not respond in time.
        """

        delay = time.time() - self._last_response_ts
        if delay > self.timeout_s:
            raise _ResponseTimeoutException(
                "No response since {} s.".format(delay))

    def _send_speed(self, speed: int):
        """Send a speed command to the connected lift.

        Args:
            speed (int): speed to be send

        Raises:
            LiftConnectionException: If not connected to a lift.
            LiftSocketCommunicationException: If the speed command could not be send.
        """

        if not self._sock:
            raise LiftConnectionException("not connected to a lift")

        self._check_limits(speed)

        logger.debug("sending speed {}".format(speed))
        request = "speed {}".format(speed).encode()
        try:
            self._sock.sendto(request, (self.ip, self.port))
        except OSError as e:
            raise _LiftSocketCommunicationException(
                "Sending speed failed: {}".format(e))

    def _recv_responses(self):
        """Receive latest responses from the connected lift.

        Raises:
            LiftConnectionException: If not connected to a lift.
            UnknownReponseException: If the response is unknown.
        """

        if not self._sock:
            raise LiftConnectionException("not connected to a lift")

        while True:
            try:
                response = self._sock.recvfrom(65565)[0].decode()
                self._last_response_ts = time.time()
            except BlockingIOError:
                return

            logger.debug("received '{}'".format(response.strip()))
            cmd, speed_response_str = response.split()

            if cmd == "set":
                speed_response = int(speed_response_str)
                self._current_speed = speed_response
            else:
                raise _UnknownReponseException("Response: '{}'".format(cmd))

    def _move(self, speed: int, time_s: float = 300.0):
        """Move the lift for a period of time with a provided speed until the top or bottom is reached.

        Args:
            speed (int): speed to move the lift with, (-255, 255)
            time_s (float): period of time the lift shall move

        Returns:
            float: Time duration the lift moved.
        """

        logger.info(
            "moving lift with speed {} for max {}s".format(speed, time_s))
        ride_start_ts = time.time()

        while True:
            if ride_start_ts + time_s < time.time():
                if speed == 0:
                    logger.info("Lift stopping finished.")
                    return time.time() - ride_start_ts
                else:
                    logger.info("Lift moved for {}s, stopping.".format(time_s))
                    ride_stop_ts = time.time()
                    self._move(0, 1)
                    return ride_stop_ts - ride_start_ts

            try:
                self._send_speed(speed)
                self._recv_responses()
                self._check_timeout()

            except LiftConnectionException as e:
                logger.warn("Lift command exception: {}".format(e))

            except _MovingException as e:
                logger.info("Lift reached end, stopping.")
                ride_stop_ts = time.time()
                self._move(0, 1)
                return ride_stop_ts - ride_start_ts

            time.sleep(self.update_interval_s)

    def move_to(self, height_request: float):
        if self._current_height_m == None:
            logger.error("Lift is not calibrated yet, starting calibration!")
            self.calibrate()

        # location is already reached
        if self._current_height_m == height_request:
            logger.info("Lift is already at {}m.".format(height_request))
            return

        # extremes: move all the way up or down
        # _current_height_m doesn't net to be set, as the hall sensor checks set these values
        if height_request >= self.height:
            logger.info("Requested height is high ({}m >= {}m maximum), moving to the top.".format(
                height_request, self.height))
            self._move(255)
            return
        elif height_request <= 0.0:
            logger.info("Request height is low ({}m <= 0m), moving to the bottom.".format(
                height_request))
            self._move(-255)
            return

        # compute travel distance and duration
        travel_distance_m = height_request - self._current_height_m
        if travel_distance_m < 0:
            travel_speed_mps = self.height / self._time_down_s
            motor_speed = -255
        else:
            travel_speed_mps = self.height / self._time_up_s
            motor_speed = 255

        travel_duration_s = travel_distance_m / travel_speed_mps

        # move the lift
        logger.info("Moving lift by {}m to reach {}m: moving {}s with speed {} m/s".format(
            travel_distance_m, height_request, travel_duration_s, travel_speed_mps))
        travel_duration_s = self._move(motor_speed, travel_duration_s)

        # set the reached height
        logger.debug("Reached height {}m after {}s".format(
            height_request, travel_duration_s))
        self._current_height_m = height_request

    def calibrate(self):
        """Calibrate the lift travel times, by moving fully up and back down."""

        logger.info("Starting lift calibration program")
        logger.info(
            "moving up (1 second steps) and back down to start in defined state.")
        while self.hall_bottom:
            self._move(255, 1)
        self._move(-255)

        logger.info("moving lift to top")
        self._time_up_s = self._move(255)
        logger.info("goint back to bottom")
        self._time_down_s = self._move(-255)

        logger.info("calibration finished, {}s to the top, {}s back to bottom".format(
            self._time_up_s, self._time_down_s))

        travel_speed_up = self.height / self._time_up_s
        travel_speed_down = self.height / self._time_down_s
        logger.info(
            "lift speeds: {} m/s up, {} m/s down".format(travel_speed_up, travel_speed_down))


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

    lift = Lift(mgr=mgr, height=30, ssid="nature40.liftsystem.34a4")

    try:
        lift.connect()
        lift.calibrate()
        lift.disconnect()
    except LiftConnectionException as e:
        logger.error("Couldn't connect to lift: {}".format(e))
