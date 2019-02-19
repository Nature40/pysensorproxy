#!/usr/bin/env python3

import argparse
import json
import yaml
import logging
import time
import threading
import os
import datetime

import schedule
import flask
from pytimeparse import parse as parse_time

import sensorproxy.sensors.base
import sensorproxy.sensors.optical
import sensorproxy.sensors.audio
import sensorproxy.sensors.environment
from sensorproxy.wifi import WiFiManager
from sensorproxy.lift import Lift

log = logging.getLogger("pysensorproxy")


def run_threaded(job_func, *args):
    job_thread = threading.Thread(target=job_func, args=args)
    job_thread.start()


class SensorProxy:
    class Metering:
        pass

    def __init__(self, config_path, metering_path):
        log.info("loading config file '{}'".format(config_path))
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

        log.info("using storage at '{}'".format(self.storage_path))

        self.sensors = {}
        for name, params in config["sensors"].items():
            sensor_cls = sensorproxy.sensors.base.classes[params["type"]]
            sensor = sensor_cls(name, self.storage_path, **params)
            self.sensors[name] = sensor

            log.info("added sensor {} ({})".format(name, params["type"]))

        self.wifi_mgr = WiFiManager(**config["wifi"])

        if "lift" in config:
            self.lift = Lift(self.wifi_mgr, **config["lift"])
        else:
            self.lift = None

        log.info("loading metering file '{}'".format(metering_path))
        with open(metering_path) as metering_file:
            self.meterings = yaml.load(metering_file)

        self._test_metering()
        # self._test_lift()

    def _test_lift(self):
        if self.lift:
            log.debug("testing lift connection")
            self.lift.connect()
            self.lift.disconnect()

    def _test_metering(self):
        for name, metering in self.meterings.items():
            log.debug("Testing metering {}".format(name))
            for sensor_name, params in metering["sensors"].items():
                self._meter(sensor_name, params)

    def _meter(self, sensor_name: str, params: dict):
        sensor = self.sensors[sensor_name]
        try:
            sensor.record(**params)
        except sensorproxy.sensors.base.SensorNotAvailableException as e:
            log.warn("Sensor {} is not available: {}".format(sensor_name, e))

    def _schedule_metering(self, name: str, metering: dict):
        start = 0
        end = 24 * 60 * 60
        interval = parse_time(metering["schedule"]["interval"])

        if "start" in metering["schedule"]:
            start = parse_time(metering["schedule"]["start"])
        if "end" in metering["schedule"]:
            end = parse_time(metering["schedule"]["end"])

        log.info("metering {} from {} until {}, every {}".format(
            name, start, end, interval))

        for sensor_name, params in metering["sensors"].items():
            for day_second in range(start, end, interval):
                # TODO: remove timezone information here
                ts = datetime.datetime.fromtimestamp(day_second)
                time = ts.time()

                s = schedule.every().day
                s.at_time = time
                s.do(run_threaded, self._meter, sensor_name, params)

                log.info("scheduled {}, next run: {}".format(
                    sensor_name, s.next_run))

    def run(self):
        for name, metering in self.meterings.items():
            self._schedule_metering(name, metering)

        while True:
            schedule.run_pending()
            time.sleep(1)


def setup_logging(logfile_path):
    try:
        os.remove(logfile_path)
    except FileNotFoundError:
        pass

    logger = logging.getLogger("pysensorproxy")
    logger.setLevel(logging.INFO)
    stderr_handler = logging.StreamHandler()
    logfile_handler = logging.FileHandler(logfile_path)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    stderr_handler.setFormatter(formatter)
    logfile_handler.setFormatter(formatter)

    logger.addHandler(stderr_handler)
    logger.addHandler(logfile_handler)

    return logger


app = flask.Flask(__name__)
parser = argparse.ArgumentParser(
    description='Read, log, safe and forward sensor readings.')
parser.add_argument(
    "-c", "--config", help="config file (yml)",
    default="examples/config.yml")
parser.add_argument(
    "-m", "--metering", help="metering protocol (yml)",
    default="examples/measurements.yml")
parser.add_argument(
    "-l", "--log", help="logfile", default="sensorproxy.log")
parser.add_argument(
    "-p", "--port", help="bind port for web interface", default=80, type=int)
args = parser.parse_args()

proxy = SensorProxy(args.config, args.metering)
logger = setup_logging(args.log)


@app.route("/log")
def serve_index():
    with open(args.log) as logfile:
        log = logfile.read()
        return flask.Response(log, mimetype='text/plain')


@app.route("/sensors")
def serve_sensors():
    return flask.Response(",".join(proxy.sensors.keys()), mimetype='text/plain')


@app.route("/sensors/<name>")
def serve_sensor_names(name):
    sensor = proxy.sensors[name]
    if isinstance(sensor, sensorproxy.sensors.base.LogSensor):
        return flask.send_file(sensor.file_path, as_attachment=True, cache_timeout=0)

    if isinstance(sensor, sensorproxy.sensors.base.FileSensor):
        records = "\n".join(sensor.records)
        return flask.Response(records, mimetype='text/plain')


@app.route("/sensors/<name>/<file_name>")
def serve_sensor_file(name, file_name):
    sensor = proxy.sensors[name]
    if file_name == "latest":
        file_name = sensor.records[-1]

    file_path = os.path.join(proxy.storage_path, file_name)

    if isinstance(sensor, sensorproxy.sensors.base.FileSensor):
        return flask.send_file(file_path, as_attachment=True, attachment_filename=file_name, cache_timeout=0)

    flask.abort(404)


def main():
    flask_thread = threading.Thread(
        target=app.run, kwargs={"host": "0.0.0.0", "port": args.port})
    flask_thread.start()
    proxy.run()


if __name__ == "__main__":
    main()
