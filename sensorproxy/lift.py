import socket
import time
import logging

import RPi.GPIO as gpio

from sensorproxy.wifi import WiFi, WiFiManager

logger = logging.getLogger(__name__)


class Lift:
    def __init__(self, mgr: WiFiManager, ssid="nature40.liftsystem.34c4", psk="supersicher", ip="192.168.4.254", port=35037, hall_bottom=5, hall_top=6, update_interval_s=0.1):
        self.mgr = mgr
        self.ip = ip
        self.port = port
        self.hall_bottom = hall_bottom
        self.hall_top = hall_top
        self.update_interval_s = update_interval_s

        self.wifi = WiFi(ssid, psk)
        self.sock = None

        self.time_up_s = None
        self.time_down_s = None

        gpio.setmode(gpio.BCM)
        gpio.setup(hall_bottom, gpio.IN)
        gpio.setup(hall_top, gpio.IN)

    def __repr__(self):
        return "Lift {}".format(self.wifi.ssid)

    def connect(self):
        if self.mgr:
            logger.info("connecting to '{}'".format(self.wifi.ssid))
            self.mgr.connect(self.wifi)
        else:
            logger.info("wifi is handled externally")

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.ip, self.port))

        self._send_speed(0)
        logger.info("connection to '{}' established".format(self.wifi.ssid))

    def disconnect(self):
        logger.info("disconnecting from lift")
        self.sock.close()
        self.sock = None

        if self.mgr:
            self.mgr.disconnect()

    class MovingException(Exception):
        pass

    def _check_limits(self, speed: int):
        if speed > 0 and gpio.input(self.hall_top):
            raise Lift.MovingException("cannot move upwards, reached sensor.")

        if speed < 0 and gpio.input(self.hall_bottom):
            raise Lift.MovingException(
                "cannot move downwards, reached sensor.")

    def _send_speed(self, speed: int):
        if not self.sock:
            raise Exception("not connected to a lift")

        self._check_limits(speed)

        logger.debug("sending speed {}".format(speed))
        request = str(speed).encode()
        self.sock.send(request)

        response = self.sock.recv(1024).decode()
        logger.debug("received '{}'".format(response.strip()))

        cmd, speed_response_str = response.split()
        speed_response = int(speed_response_str)

        if cmd != "set":
            raise Exception(
                "LiftControl responded with command '{}'".format(cmd))
        elif speed != speed_response:
            logger.warn("responded speed ({}) does not match requested ({})".format(
                speed_response, speed))
        else:
            logger.debug("speed set successfully")

        return speed_response

    def move(self, speed: int):
        logger.info("moving lift with speed {}".format(speed))
        ride_start_ts = time.time()

        try:
            while True:
                self._send_speed(speed)
                time.sleep(self.update_interval_s)
        except Lift.MovingException:
            ride_end_ts = time.time()
            travel_time_s = ride_end_ts - ride_start_ts
            logger.info("end reached in {}s".format(travel_time_s))

            self._send_speed(0)

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

    lift = Lift(mgr=None)
    lift.connect()

    lift.calibrate()

    lift.disconnect()
