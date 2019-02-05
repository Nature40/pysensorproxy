#!/usr/bin/env python3

import argparse
import json

from sensors import sensors 

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Read, log, safe and forward sensor readings.')
    parser.add_argument("-c", "--config", help="config file (json)", default="examples/config.json")
    parser.add_argument("-m", "--measure_protocol", help="measurement protocol", default="/etc/sensorproxy/measurements.json")
    args = parser.parse_args()
    
    with open(args.config) as config_file:
        config = json.load(config_file)
    
    connected_sensors = []

    for sensor_type, sensor_config in config["sensors"].items():
        connected_sensors = sensors[sensor_type](path=config["storage"]["location"], **sensor_config)
        connected_sensors.read()


    