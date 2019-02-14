#!/usr/bin/env python3

import argparse
import json
import yaml
import logging

import sensors.base
import sensors.optical
import sensors.audio
import sensors.environment
from wifi import WiFiManager
from lift import Lift

log = logging.getLogger("pysensorproxy")


class SensorProxy:
    def __init__(self, config_path, metering_path):
        log.info("loading config file '{}'".format(config_path))
        with open(config_path) as config_file:
            config = yaml.load(config_file)
        log.info("loading metering file '{}'".format(metering_path))
        with open(metering_path) as metering_file:
            self.metering = yaml.load(metering_file)

        self.storage_path = config["storage"]
        log.info("using storage at '{}'".format(self.storage_path))

        self.sensors = {}
        for name, params in config["sensors"].items():
            sensor = sensors.base.classes[params["type"]](
                name, self.storage_path, **params)
            self.sensors[name] = sensor
            log.info("added sensor {} ({})".format(name, params["type"]))

        log.debug("testing meterings")
        self._metering_test()

        self.wifi_mgr = WiFiManager(**config["wifi"])

        if "lift" in config:
            log.debug("testing lift connection")
            self.lift = Lift(self.wifi_mgr, **config["lift"])
            self.lift.connect()
            self.lift.disconnect()

    def _metering_test(self):
        meterings = {**self.metering["always"]["meterings"],
                     **self.metering["scheduled"]["meterings"]}

        for name, params in meterings.items():
            try:
                self.sensors[name].test(**params)
            except sensors.base.SensorNotAvailableException as e:
                log.warn("Sensor {} is not available: {}".format(name, e))


if __name__ == "__main__":
    logger = logging.getLogger("pysensorproxy")
    logger.setLevel(logging.DEBUG)
    handler = logging.StreamHandler()
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    parser = argparse.ArgumentParser(
        description='Read, log, safe and forward sensor readings.')
    parser.add_argument(
        "-c", "--config", help="config file (yml)",
        default="examples/config.yml")
    parser.add_argument(
        "-m", "--metering", help="metering protocol (yml)",
        default="examples/measurements.yml")
    args = parser.parse_args()

    proxy = SensorProxy(args.config, args.metering)
