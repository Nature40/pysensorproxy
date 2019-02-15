#!/usr/bin/env python3

import argparse
import json
import yaml
import logging
import time
import threading
import os

import schedule
import flask

import sensors.base
import sensors.optical
import sensors.audio
import sensors.environment
from wifi import WiFiManager
from lift import Lift

log = logging.getLogger("pysensorproxy")


def run_threaded(job_func):
    job_thread = threading.Thread(target=job_func)
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
            sensor_cls = sensors.base.classes[params["type"]]
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
            metering = yaml.load(metering_file)

        self.ongoing = SensorProxy.Metering()
        self.ongoing.interval_s = metering["ongoing"]["interval_s"]
        self.ongoing.meterings = metering["ongoing"]["meterings"]

        self.scheduled = SensorProxy.Metering()
        self.scheduled.schedule = metering["scheduled"]["schedule"]
        self.scheduled.meterings = metering["scheduled"]["meterings"]

        self._test_metering()
        # self._test_lift()

    def _test_lift(self):
        if self.lift:
            log.debug("testing lift connection")
            self.lift.connect()
            self.lift.disconnect()

    def _test_metering(self):
        self._meter_ongoing()
        self._meter_scheduled()

    def _meter_ongoing(self):
        log.info("ongoing metering started")
        for name, params in self.ongoing.meterings.items():
            sensor = self.sensors[name]
            try:
                sensor.record(**params)
            except sensors.base.SensorNotAvailableException as e:
                log.warn("Sensor {} is not available: {}".format(name, e))

        log.info("ongoing metering finished")

    def _meter_scheduled(self, threaded=False):
        log.info("scheduled metering started")
        for name, params in self.scheduled.meterings.items():
            sensor = self.sensors[name]
            try:
                sensor.record(**params)
            except sensors.base.SensorNotAvailableException as e:
                log.warn("Sensor {} is not available: {}".format(name, e))

        log.info("scheduled metering finished")

    def run(self):
        # schedule ongoing meterings
        schedule.every(self.ongoing.interval_s).seconds.do(
            run_threaded, self._meter_ongoing)
        log.info("scheduling ongoing meterings for every {} seconds".format(
            self.ongoing.interval_s))

        # schedule meterings for distinct times
        for entry in self.scheduled.schedule:
            job = schedule.every().day.at(entry["time"]).do(
                run_threaded, self._meter_scheduled)
            log.info("scheduled metering for {}".format(
                job.next_run))

        # run the schedule
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


logger = setup_logging(args.log)
app = flask.Flask(__name__)
proxy = SensorProxy(args.config, args.metering)


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
    if isinstance(sensor, sensors.base.LogSensor):
        return flask.send_file(sensor.file_path, as_attachment=True, cache_timeout=0)

    if isinstance(sensor, sensors.base.FileSensor):
        records = "\n".join(sensor.records)
        return flask.Response(records, mimetype='text/plain')


@app.route("/sensors/<name>/<file_name>")
def serve_sensor_file(name, file_name):
    sensor = proxy.sensors[name]
    if file_name == "latest":
        file_name = sensor.records[-1]

    file_path = os.path.join(proxy.storage_path, file_name)

    if isinstance(sensor, sensors.base.FileSensor):
        return flask.send_file(file_path, as_attachment=True, attachment_filename=file_name, cache_timeout=0)

    flask.abort(404)


flask_thread = threading.Thread(
    target=app.run, kwargs={"host": "0.0.0.0", "port": args.port})
flask_thread.start()

proxy.run()
