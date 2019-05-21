import csv
import logging

logger = logging.getLogger(__name__)


class CSVFormatException(Exception):
    pass


def __bool(string):
    if string.lower() in ["true", "yes"]:
        return True
    if string.lower() in ["false", "no"]:
        return False
    raise ValueError("'{}' cannot be casted to boolean.")


def __autocast(string):
    for cast in (__bool, int, float):
        try:
            return cast(string)
        except ValueError:
            pass
    return string


def _influx_seperate_header(header: [], tag_prefix: str = "."):
    header_list = list(enumerate(header))

    if not "time" in header_list[0][1].lower():
        raise CSVFormatException(
            "First column does not contain time ('{}')".format(header_list[0]))

    val_cols = [(num, name) for (num, name) in header_list[1:]
                if not name.startswith(tag_prefix)]
    tag_cols = [(num, name[1:]) for (num, name) in header_list[1:]
                if(name.startswith(tag_prefix))]

    logger.debug("Parsed csv header; values: {}, tags: {}".format(
        tag_cols, val_cols))

    return val_cols, tag_cols


def _influx_construct_dict(measurement: str, row: [], val_cols: [(int, str)], tag_cols: [(int, str)]):
    body = {}
    body["measurement"] = measurement
    body["time"] = row[0]

    body["fields"] = {}
    for num, name in val_cols:
        body["fields"][name] = __autocast(row[num])

    body["tags"] = {}
    for num, name in tag_cols:
        body["tags"][name] = __autocast(row[num])

    return body


def influx_process(measurement: str, header: [], row: [], tag_prefix="."):
    val_cols, tag_cols = _influx_seperate_header(header, tag_prefix=tag_prefix)
    body = _influx_construct_dict(measurement, row, val_cols, tag_cols)
    return body


def influx_process_csv(csv_path: str, measurement: str, csv_delimiter=",", tag_prefix="."):
    """

    :param csv_path: <str> full qualified path to the csv file
    :param measurement: <str> name of the measurement, e.g. class of sensor
    :param csv_delimiter: <str> the delimiter of the submitted file
    :param csv_tag_prefix: <str> prefix in csv header to identify tags
    :return:
    """

    with open(csv_path, 'r') as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=csv_delimiter)

        # read and parse header: extract time, values and tags
        val_cols, tag_cols = _influx_seperate_header(
            next(csv_reader), tag_prefix=tag_prefix)

        # read and parse content based on the header definition
        data = []

        for row in csv_reader:
            body = _influx_construct_dict(measurement, row, val_cols, tag_cols)
            data.append(body)

        logger.debug("Read {} rows from '{}'".format(len(data), csv_path))

    return data
