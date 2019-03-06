import socket
import time
import logging

import RPi.GPIO as gpio

from sensorproxy.wifi import WiFi, WiFiManager

logger = logging.getLogger(__name__)


class MovingException(Exception):
    pass


class LiftConnectionException(Exception):
    pass


class UnknownReponseException(LiftConnectionException):
    pass


class WrongSpeedResponseException(LiftConnectionException):
    pass


class LiftSocketCommunicationException(LiftConnectionException):
    pass


class ResponseTimeoutException(LiftConnectionException):
    pass


class Lift:
    def __init__(self, mgr, ssid, psk, hall_bottom_pin, hall_top_pin, ip="192.168.3.254", port=35037, update_interval_s=0.05, timeout_s=0.5):
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

        gpio.setmode(gpio.BCM)
        gpio.setup(hall_bottom_pin, gpio.IN)
        gpio.setup(hall_top_pin, gpio.IN)

    def __repr__(self):
        return "Lift {}".format(self.wifi.ssid)

    def connect(self, dry=False):
        if self.mgr and not dry:
            logger.info("connecting to '{}'".format(self.wifi.ssid))
            self.mgr.connect(self.wifi)
        else:
            logger.info("wifi is handled externally")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.setblocking(False)

        self._send_speed(0)
        while self._current_speed == None:
            self._recv_responses()

        logger.info("connection to '{}' established".format(self.wifi.ssid))

    def disconnect(self, dry=False):
        logger.info("disconnecting from lift")
        self.sock.close()
        self.sock = None

        if self.mgr and not dry:
            self.mgr.disconnect()

    @property
    def hall_bottom(self):
        return gpio.input(self.hall_bottom_pin)

    @property
    def hall_top(self):
        return gpio.input(self.hall_top_pin)

    def _check_limits(self, speed: int):
        if speed > 0 and self.hall_top:
            raise MovingException("cannot move upwards, reached sensor.")

        if speed < 0 and self.hall_bottom:
            raise MovingException("cannot move downwards, reached sensor.")

    def _check_timeout(self):
        delay = time.time() - self._last_response_ts
        if delay > self.timeout_s:
            raise ResponseTimeoutException(
                "No response since {} s.".format(delay))

    def _send_speed(self, speed: int):
        if not self.sock:
            raise Exception("not connected to a lift")

        self._check_limits(speed)

        logger.debug("sending speed {}".format(speed))
        request = "speed {}".format(speed).encode()
        try:
            self.sock.sendto(request, (self.ip, self.port))
        except OSError as e:
            raise LiftSocketCommunicationException(
                "Sending speed failed: {}".format(e))

    def _recv_responses(self):
        if not self.sock:
            raise Exception("not connected to a lift")

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
