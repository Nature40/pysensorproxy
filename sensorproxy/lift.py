import socket
import time
import logging

import RPi.GPIO as gpio

from sensorproxy.wifi import WiFi, WiFiManager

log = logging.getLogger("pysensorproxy.lift")


class Lift:
    def __init__(self, mgr: WiFiManager, ssid="LiftSystem 949f", psk="supersicher", ip="192.168.4.1", port=35037, hall_bottom=5, hall_top=6, update_interval_s=0.1):
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
        log.info("connecting to '{}'".format(self.wifi.ssid))
        self.mgr.connect(self.wifi)

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(3)
        self._send_speed(0)
        log.info("connection to '{}' established".format(self.wifi.ssid))

    def disconnect(self):
        log.info("disconnecting from lift")
        self.sock.close()
        self.sock = None
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

        log.debug("sending speed {}".format(speed))
        request = str(speed).encode()
        self.sock.sendto(request, (self.ip, self.port))

        response = self.sock.recvfrom(1024)[0].decode()
        log.debug("received '{}'".format(response.strip()))

        cmd, speed_response_str = response.split()
        speed_response = int(speed_response_str)

        if cmd != "set":
            raise Exception(
                "LiftControl responded with command '{}'".format(cmd))
        elif speed != speed_response:
            log.warn("responded speed ({}) does not match requested ({})".format(
                speed_response, speed))
        else:
            log.debug("speed set successfully")

        return speed_response

    def move(self, speed: int):
        log.info("moving lift with speed {}".format(speed))
        ride_start_ts = time.time()

        try:
            while True:
                self._send_speed(speed)
                time.sleep(self.update_interval_s)
        except Lift.MovingException:
            ride_end_ts = time.time()
            travel_time_s = ride_end_ts - ride_start_ts
            log.info("end reached in {}s".format(travel_time_s))

            self._send_speed(0)

        return travel_time_s

    def calibrate(self):
        log.info("calibrating lift, starting at the bottom")
        self.move(-255)

        log.info("moving lift to top")
        self.time_up_s = self.move(255)
        log.info("goint back to bottom")
        self.time_down_s = self.move(-255)

        log.info("calibration finished, {}s to the top, {}s back to bottom".format(
            self.time_up_s, self.time_down_s))


if __name__ == "__main__":
    logger = logging.getLogger("pysensorproxy")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    mgr = WiFiManager()

    lift = Lift(mgr)
    lift.connect()

    lift.calibrate()

    lift.disconnect()


# # setup hall sensor
# PIN_HALL = 26
# gpio.setmode(gpio.BCM)
# gpio.setup(PIN_HALL, gpio.IN)

# lift = Lift()

# while not gpio.input(PIN_HALL):
#     print("Moving up")
#     lift.move(255)
#     time.sleep(0.2)


# print("Stopping lift")
# lift.move(0)
