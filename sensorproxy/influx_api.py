import csv
import os

from collections import namedtuple
from influxdb import InfluxDBClient
from typing import List


class WrongFilePath(Exception):
    pass


class UnCorrectContent(Exception):
    pass


class WrongLength(Exception):
    pass


Measurement = namedtuple(
    "Measurement",
    ["hostname", "id", "sensor", "timestamp", "value", "height"])


class InfluxAPI():
    def __init__(self, proxy, host, port, user, password, db, path=u'', ssl=False):
        self.proxy = proxy
        self.client = InfluxDBClient(
            host=host, port=port,
            username=user, password=password, database=db,
            ssl=ssl, verify_ssl=ssl, path=path)

    def __create_json(self, measurement: Measurement):
        """
        puts all attributes from the measurement in a json to fit the influx formation

        :param measurement: <Measurement>
        """
        json_body = {}
        json_body["measurement"] = measurement.sensor
        tags = {}
        tags["id"] = measurement.id
        tags["hostname"] = measurement.hostname
        tags["height"] = measurement.height
        json_body["tags"] = tags
        json_body["time"] = measurement.timestamp
        fields = {}
        fields["value"] = measurement.value
        json_body["fields"] = fields
        return json_body

    def __write_json_to_influx(self, json_data: list):
        """
        use the python influx api to submit the data to the remote influx

        :param json_data: <list> the influx data packed as list of dicts
        """
        self.client.write_points(
            json_data, time_precision="s", protocol="json")

    def __write_list_of_measurements(self, measurements: List[Measurement]):
        """

        :param measurements: list of all measurements
        """
        json_list = []
        for measurement in measurements:
            json_list.append(self.__create_json(measurement))

        self.__write_json_to_influx(json_list)

    def submit_measurement(self, measurement: Measurement):
        """
        Append a single Measurement to the Influx database. The Measurement's
        id or hostname will be set to the SensorProxy's name, if it is None.

        :param measurement: <Measurement> single measurement
        """
        # if measurement.id is None:
        #     measurement = measurement._replace(id=self.proxy.id)
        # if measurement.hostname is None:
        #     measurement = measurement._replace(hostname=self.proxy.hostname)

        self.__write_list_of_measurements([measurement])

    def submit_file(self, file_path: str, id: str, hostname: str, delimiter=','):
        """

        :param file_path: full qualified path to the file
        :param delimiter: <str> the delimiter of the submitted file
        :return:
        """
        measurements = []
        if not os.path.exists(file_path):
            raise WrongFilePath("{} does not exist".format(file_path))

        with open(file_path, 'r') as csv_file:
            csv_reader = csv.reader(csv_file, delimiter=delimiter)
            header = []
            line_count = 0

            for row in csv_reader:
                if line_count == 0:
                    header = row[2:]
                else:
                    col_number = 0
                    for col in row[2:]:
                        measurements.append(Measurement(
                            id=str(id),
                            hostname=str(hostname),
                            sensor=header[col_number],
                            timestamp=row[0],
                            value=col,
                            height=row[1]))
                        col_number += 1
                line_count += 1

            self.__write_list_of_measurements(measurements)
