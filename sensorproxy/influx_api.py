import csv
import os

from influxdb import InfluxDBClient
from typing import List


class WrongFilePath(Exception):
    pass

class UnCorrectContent(Exception):
    pass

class WrongLength(Exception):
    pass


class Measurement():
    def __init__(self, box_id: str, sensor: str, timestamp: str, value: float, height: float):
        self.set_box_id(box_id)
        self.set_sensor(sensor)
        self.set_timestamp(timestamp)
        self.set_value(value)
        self.set_height(height)

    def get_box_id(self):
        return self.__box_id

    def set_box_id(self, box_id: str):
        self.__box_id = box_id

    def get_sensor(self):
        return self.__sensor

    def set_sensor(self, sensor: str):
        self.__sensor = sensor

    def get_timestamp(self):
        return self.__timestamp

    def set_timestamp(self, timestamp: str):
        self.__timestamp = timestamp

    def get_value(self):
        return self.__value

    def set_value(self, value: float):
        self.__value = value

    def get_height(self):
        return self.__height

    def set_height(self, height: float):
        self.__height = height


class InfluxAPI():
    def __init__(self, host, port, user, password, db, path=u'', ssl=False):
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
        json_body["measurement"] = measurement.get_sensor()
        tags = {}
        tags["host"] = measurement.get_box_id()
        tags["height"] = measurement.get_height()
        json_body["tags"] = tags
        json_body["time"] = measurement.get_timestamp()
        fields = {}
        fields["value"] = measurement.get_value()
        json_body["fields"] = fields
        return json_body

    def __write_json_to_influx(self, json_data: list):
        """
        use the python influx api to submit the data to the remote influx

        :param json_data: <list> the influx data packed as list of dicts
        """
        self.client.write_points(json_data, time_precision="s", protocol="json")


    def __write_list_of_measurements(self, measurements: List[Measurement]):
        """

        :param measurements: list of all measurements
        """
        json_list = []
        for measurement in measurements:
            json_list.append(self.__create_json(measurement))

        self.__write_json_to_influx(json_list)

    def submit_file(self, file_path: str, box_id: str, delimiter=','):
        """

        :param file_path: full qualified path to the file
        :param box_id: <str> the box_id of the sensorbox also use in the field
        :param delimiter: <str> the delimiter of the submitted file
        :return:
        """
        measurements = []
        if os.path.exists(file_path):
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
                            measurements.append(Measurement(box_id, header[col_number], row[0], col, row[1]))
                            col_number += 1
                    line_count += 1
        else:
            raise WrongFilePath("{} does not exist".format(file_path))
        self.__write_list_of_measurements(measurements)


if __name__== "__main__":
    influx = InfluxAPI("10.0.1.60", 8086, "nature40", "nature40", "sensors")
    influx.submit_file("/Users/lampep/Downloads/2019-03-11T172503_am2302.csv", "test1")
