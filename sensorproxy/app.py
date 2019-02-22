#!/usr/bin/env python3

import argparse
import json
import yaml
import logging
import time
import threading
import os
import datetime
import http.server
import socketserver

import schedule
from pytimeparse import parse as parse_time

import sensorproxy.sensors.base
import sensorproxy.sensors.optical
import sensorproxy.sensors.audio
import sensorproxy.sensors.environment
from sensorproxy.wifi import WiFiManager
from sensorproxy.lift import Lift

logger = logging.getLogger(__name__)


def run_threaded(job_func, *args):
    job_thread = threading.Thread(target=job_func, args=args)
    job_thread.start()


class SensorProxy:
    class Metering:
        pass

    def __init__(self, config_path, metering_path):
        logger.info("loading config file '{}'".format(config_path))
        with open(config_path) as config_file:
            config = yaml.load(config_file)

        if "storage" in config:
            self.storage_path = config["storage"]
            try:
                os.makedirs(self.storage_path)
            except FileExistsError:
                pass
        else:
            self.storage_path = ''

        logger.info("using storage at '{}'".format(self.storage_path))

        self.sensors = {}
        for name, params in config["sensors"].items():
            sensor_cls = sensorproxy.sensors.base.classes[params["type"]]
            sensor = sensor_cls(name, self.storage_path, **params)
            self.sensors[name] = sensor

            logger.info("added sensor {} ({})".format(name, params["type"]))

        self.wifi_mgr = WiFiManager(**config["wifi"])

        if "lift" in config:
            self.lift = Lift(self.wifi_mgr, **config["lift"])
        else:
            self.lift = None

        logger.info("loading metering file '{}'".format(metering_path))
        with open(metering_path) as metering_file:
            self.meterings = yaml.load(metering_file)

        self._test_metering()
        # self._test_lift()

    def _test_lift(self):
        if self.lift:
            logger.debug("testing lift connection")
            self.lift.connect()
            self.lift.disconnect()

    def _test_metering(self):
        for name, metering in self.meterings.items():
            logger.debug("Testing metering {}".format(name))
            for sensor_name, params in metering["sensors"].items():
                if "duration" in params:
                    params = params.copy()
                    params["duration"] = "1s"
                self._meter(sensor_name, params)

    def _meter(self, sensor_name: str, params: dict):
        sensor = self.sensors[sensor_name]
        try:
            sensor.record(**params)
        except sensorproxy.sensors.base.SensorNotAvailableException as e:
            logger.warn(
                "Sensor {} is not available: {}".format(sensor_name, e))

    def _schedule_metering(self, name: str, metering: dict):
        start = 0
        end = 24 * 60 * 60
        interval = parse_time(metering["schedule"]["interval"])

        if "start" in metering["schedule"]:
            start = parse_time(metering["schedule"]["start"])
        if "end" in metering["schedule"]:
            end = parse_time(metering["schedule"]["end"])

        logger.info("metering {} from {} until {}, every {}".format(
            name, start, end, interval))

        for sensor_name, params in metering["sensors"].items():
            for day_second in range(start, end, interval):
                # TODO: remove timezone information here
                ts = datetime.datetime.fromtimestamp(day_second)
                time = ts.time()

                s = schedule.every().day
                s.at_time = time
                s.do(run_threaded, self._meter, sensor_name, params)

                logger.debug("scheduled {}, next run: {}".format(
                    sensor_name, s.next_run))

    def run(self):
        for name, metering in self.meterings.items():
            self._schedule_metering(name, metering)

        while True:
            schedule.run_pending()
            time.sleep(1)


def setup_logging(logfile_path, level):
    try:
        os.remove(logfile_path)
    except FileNotFoundError:
        pass

    logger = logging.getLogger("sensorproxy")

    # create stderr log
    stderr_formatter = logging.Formatter(
        '%(name)s - %(levelname)s - %(message)s')
    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(stderr_formatter)
    logger.addHandler(stderr_handler)

    # create logfile
    logfile_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logfile_handler = logging.FileHandler(logfile_path)
    logfile_handler.setFormatter(logfile_formatter)
    logger.addHandler(logfile_handler)

    logger.setLevel(level)


def main():
    parser = argparse.ArgumentParser(
        description='Read, log, safe and forward sensor readings.')
    parser.add_argument(
        "-c", "--config", help="config file (yml)",
        default="examples/sensorproxy.yml")
    parser.add_argument(
        "-m", "--metering", help="metering protocol (yml)",
        default="examples/meterings.yml")
    parser.add_argument(
        "-l", "--log", help="logfile", default="sensorproxy.log")
    parser.add_argument(
        "-p", "--port", help="bind port for web interface", default=80, type=int)
    parser.add_argument(
        "-v", "--verbose", help="enable verbose log", action='store_const', const=logging.DEBUG, default=logging.INFO)

    args = parser.parse_args()

    setup_logging(args.log, args.verbose)

    proxy = SensorProxy(args.config, args.metering)
    os.chdir(proxy.storage_path)

    Handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("", args.port), Handler)

    httpd_thread = threading.Thread(target=httpd.serve_forever)
    httpd_thread.start()
    proxy.run()


if __name__ == "__main__":
    main()
