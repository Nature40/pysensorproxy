#!/usr/bin/env python3

import argparse
import datetime
import http.server
import json
import logging
import os
import platform
import socketserver
import threading
import time
import yaml

import schedule
from pytimeparse import parse as parse_time

import sensorproxy.sensors.audio
import sensorproxy.sensors.base
import sensorproxy.sensors.cellular
import sensorproxy.sensors.environment
import sensorproxy.sensors.logger
import sensorproxy.sensors.optical
import sensorproxy.sensors.rsync
import sensorproxy.sensors.sink
import sensorproxy.sensors.system


from sensorproxy.influx_api import InfluxAPI
from sensorproxy.lift import Lift
from sensorproxy.wifi import WiFiManager


logger = logging.getLogger(__name__)


def run_threaded(job_func, *args):
    job_thread = threading.Thread(target=job_func, args=args)
    job_thread.start()


class SensorProxy:
    class Metering:
        pass

    def __init__(self, config_path, metering_path, test=False):
        self.config_path = config_path

        logger.info("loading config file '{}'".format(config_path))
        with open(config_path) as config_file:
            config = yaml.load(config_file, Loader=yaml.Loader)

        self._init_identifiers(config)
        self._init_storage(**config)
        self._init_logging(**config["log"])
        self._init_optionals(config)
        self._init_sensors(config["sensors"])

        logger.info("loading metering file '{}'".format(metering_path))
        with open(metering_path) as metering_file:
            self.meterings = yaml.load(metering_file, Loader=yaml.Loader)

        self._test_metering()

        if not test:
            self._reset_lift()

    def _init_identifiers(self, config):
        self.hostname = platform.node()
        self.id = config.get("id", None)

    def _init_storage(self, storage_path=".", **kwargs):
        self.storage_path = storage_path
        try:
            os.makedirs(storage_path)
        except FileExistsError:
            pass

        self.storage_path_node = os.path.join(storage_path, self.hostname)
        try:
            os.makedirs(self.storage_path_node)
        except FileExistsError:
            pass

        logger.info("using storage at '{}'".format(storage_path))

    def _init_logging(self, level="info", file_name="sensorproxy.log"):
        logfile_path = os.path.join(self.storage_path, file_name)
        logger.info("Writing logs to '{}'".format(logfile_path))

        try:
            logging_level = logging._nameToLevel[level.upper()]
            logger.info("Using logging level '{}' for logfile".format(level))
        except KeyError:
            logging_level = logging.INFO
            logger.warn(
                "'{}' is no valid logging level, defaulting to 'info'".format(
                    level)
            )

        # create logfile
        logfile_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        logfile_handler = logging.FileHandler(logfile_path)
        logfile_handler.setLevel(logging_level)
        logfile_handler.setFormatter(logfile_formatter)

        main_logger = logging.getLogger("sensorproxy")
        main_logger.addHandler(logfile_handler)

    def _init_sensors(self, sensor_config):
        self.sensors = {}
        for name, params in sensor_config.items():
            sensor_cls = sensorproxy.sensors.base.classes[params["type"]]
            sensor = sensor_cls(self, name, **params)
            self.sensors[name] = sensor

            logger.info("added sensor {} ({})".format(name, params["type"]))

    def _init_optionals(self, config):
        self.wifi_mgr = None
        if "wifi" in config:
            self.wifi_mgr = WiFiManager(**config["wifi"])

        self.lift = None
        if "lift" in config:
            self.lift = Lift(self.wifi_mgr, **config["lift"])

        self.influx = None
        if "influx" in config:
            self.influx = InfluxAPI(self, **config["influx"])

    def _reset_lift(self):
        if not self.lift:
            return

        try:
            self.lift.connect()
        except sensorproxy.wifi.WiFiConnectionError as e:
            logger.error("Couldn't connect to lift wifi: {}".format(e))
            return
        except sensorproxy.lift.LiftConnectionException as e:
            logger.error("Couldn't connect to lift: {}".format(e))
            self.lift.disconnect()
            return

        logger.info("Calibrating Lift")
        self.lift.calibrate()
        self.lift.disconnect()

    def test_interactive(self):
        self._test_hall_interactive()

    def _test_hall_interactive(self):
        if not self.lift:
            logger.info(
                "Interactive hall sensor test: no lift configured, skipping test."
            )
            return

        logger.info(
            "Interactive hall sensor test: approach with a magnet to trigger 1, remove magnet to trigger 0"
        )

        while self.lift.hall_bottom == 0:
            logger.warn(
                "Interactive hall sensor test (1/4):  bottom sensor reads 0, approach with a magnet..."
            )
            time.sleep(1)

        while self.lift.hall_bottom == 1:
            logger.warn(
                "Interactive hall sensor test (2/4): bottom sensor reads 1, remove magnet..."
            )
            time.sleep(1)

        while self.lift.hall_top == 0:
            logger.warn(
                "Interactive hall sensor test (3/4): top sensor reads 0, approach with a magnet..."
            )
            time.sleep(1)

        while self.lift.hall_top == 1:
            logger.warn(
                "Interactive hall sensor test (4/4): top sensor reads 1, remove magnet..."
            )
            time.sleep(1)

        logger.info("Interactive hall sensor test finished.")

    def _test_metering(self):
        for name, metering in self.meterings.items():
            logger.debug("Testing metering '{}'".format(name))
            self._run_metering(name, metering, test=True)

    def _run_metering(self, name, metering, test=False):
        logger.info("Running metering {}".format(name))

        sensors = [self.sensors[name] for name in metering["sensors"]]
        for sensor in sensors:
            logger.debug("Requesting access to {}.".format(sensor.name))
            sensor.lock.acquire()
            logger.debug("Got access to {}.".format(sensor.name))

        if (not "heights" in metering) or (self.lift == None) or test:
            height = self.lift._current_height_m if self.lift else None
            self._record_sensors_threaded(metering["sensors"], test=test)
        else:

            try:
                self.lift.connect()

                for height in metering["heights"]:
                    logger.info(
                        "Running metering {} at {}m.".format(name, height))
                    self.lift.move_to(height)
                    self._record_sensors_threaded(
                        metering["sensors"], test=test)

                logger.info(
                    "Metering {} is done, moving back to bottom.".format(name))
                self.lift.move_to(0.0)
                self.lift.disconnect()

            except sensorproxy.wifi.WiFiConnectionError as e:
                logger.error("Couldn't connect to lift wifi: {}".format(e))
                self._record_sensors_threaded(metering["sensors"], test=test)

            except sensorproxy.lift.LiftConnectionException as e:
                logger.error("Error in lift connection: {}".format(e))
                self.lift.disconnect()
                self._record_sensors_threaded(metering["sensors"], test=test)

        for sensor in sensors:
            logger.debug("Releasing access to {}.".format(sensor.name))
            sensor.lock.release()

    def _record_sensors_threaded(self, sensors: {str: dict}, test: bool):
        meter_threads = []
        height = self.lift._current_height_m if self.lift else None

        for name, params in sensors.items():
            sensor = self.sensors[name]
            t = threading.Thread(
                target=self._record_sensor, args=[sensor, params, test, height]
            )
            t.sensor = sensor
            meter_threads.append(t)
            t.start()

        for t in meter_threads:
            logger.debug("Waiting for {} to finish...".format(t.sensor.name))
            t.join()

    def _record_sensor(
        self,
        sensor: sensorproxy.sensors.base.Sensor,
        params: dict,
        test: bool,
        height_m: float,
    ):
        try:
            if test:
                params = params.copy()
                params["duration"] = "1s"

            sensor.record(height_m=height_m, **params)
        except KeyError:
            logger.error(
                "Sensor '{}' is not defined in config: {}".format(
                    sensor.name, self.config_path
                )
            )
        except sensorproxy.sensors.base.SensorNotAvailableException as e:
            logger.error(
                "Sensor '{}' is not available: {}".format(sensor.name, e))

    def _schedule_metering(self, name: str, metering: dict):
        # default values for start and end (whole day)
        start = 0
        end = 24 * 60 * 60

        if "start" in metering["schedule"]:
            start = parse_time(metering["schedule"]["start"])
        if "end" in metering["schedule"]:
            end = parse_time(metering["schedule"]["end"])

        interval = parse_time(metering["schedule"]["interval"])

        logger.info(
            "metering '{}' from {} until {}, every {}".format(
                name, start, end, interval
            )
        )

        for day_second in range(start, end, interval):
            # TODO: remove timezone information here
            ts = datetime.datetime.fromtimestamp(day_second)
            time = ts.time()

            s = schedule.every().day
            s.at_time = time
            s.do(run_threaded, self._run_metering, name, metering)

    def run(self):
        for name, metering in self.meterings.items():
            self._schedule_metering(name, metering)

        while True:
            schedule.run_pending()
            time.sleep(1)


def setup_logging(level):
    if level > 3:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.ERROR - (10 * level)

    # create stderr log
    stderr_formatter = logging.Formatter(
        "%(name)s - %(levelname)s - %(message)s")
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(stderr_formatter)

    main_logger = logging.getLogger("sensorproxy")
    main_logger.addHandler(stderr_handler)
    main_logger.setLevel(logging_level)

    if level > 3:
        logger.warn("Logging level cannot be increased further.")


def main():
    parser = argparse.ArgumentParser(
        description="Read, log, safe and forward sensor readings."
    )
    parser.add_argument(
        "-c", "--config", help="config file (yml)", default="/boot/sensorproxy.yml"
    )
    parser.add_argument(
        "-m",
        "--metering",
        help="metering protocol (yml)",
        default="/boot/meterings.yml",
    )
    parser.add_argument(
        "-p", "--port", help="bind port for web interface", default=80, type=int
    )
    parser.add_argument(
        "-v", "--verbose", help="verbose output", action="count", default=0
    )
    parser.add_argument(
        "-t",
        "--test",
        help="only test if sensors are working",
        action="store_const",
        const=True,
        default=False,
    )
    args = parser.parse_args()

    setup_logging(args.verbose)
    proxy = SensorProxy(args.config, args.metering, args.test)

    if args.test:
        proxy.test_interactive()
        logger.info("Testing finished")
        return

    os.chdir(proxy.storage_path)
    Handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", args.port), Handler)

    httpd_thread = threading.Thread(target=httpd.serve_forever)
    httpd_thread.start()
    proxy.run()


if __name__ == "__main__":
    main()
