#!/usr/bin/env python3

import argparse
import json
import yaml

import sensors.base
import sensors.optical
import sensors.audio
import sensors.environment


class SensorProxy:
    def __init__(self, config_path, metering_path):
        with open(config_path) as config_file:
            config = yaml.load(config_file)

        self.storage_path = config["storage"]
        self.sensors = {}
        for name, params in config["sensors"].items():
            sensor = sensors.base.classes[params["type"]](
                name, self.storage_path, **params)
            self.sensors[name] = sensor

        with open(metering_path) as metering_file:
            self.metering = yaml.load(metering_file)

        self.metering_test()

    def metering_test(self):
        meterings = {**self.metering["always"]["meterings"],
                     **self.metering["scheduled"]["meterings"]}

        for name, params in meterings.items():
            try:
                self.sensors[name].test(**params)
            except sensors.base.SensorNotAvailableException as e:
                print("Sensor {} is not available: {}".format(name, e))


if __name__ == "__main__":
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

    # connected_sensors = []
    # for sensor_name, sensor_config in config["sensors"].items():
    #     connected_sensors = sensortypes.classes[sensor_name](path=config["storage"]["location"], **sensor_config)
    #     connected_sensors.read()
