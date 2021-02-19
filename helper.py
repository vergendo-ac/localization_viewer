import argparse
import json
import os
from datetime import datetime

import piexif

TS_FORMAT = '%d_%b_%Y_%H_%M_%S_%f'


def get_hint_from_cmd(hint):
    if hint is not None:
        return json.dumps({"reconstructions": [int(hint)], "hint_only": True})
    return None


def filename():
    date_time_obj = datetime.now()
    time_stamp = date_time_obj.strftime(TS_FORMAT)
    return str(time_stamp)


def load_json(response):
    return json.dumps(json.loads(response.text), indent=2)


def _to_decimals(coordinates):
    decimals = []
    for coordinate in coordinates:
        decimal: float = (coordinate[0][0] / coordinate[0][1]) + \
                         ((coordinate[1][0] / coordinate[1][1]) / 60) + \
                         ((coordinate[2][0] / coordinate[2][1]) / 3600)
        decimals.append(decimal)
    return decimals


def get_exif(image_path):
    coordinates = []
    exif = piexif.load(image_path)
    lat = exif["GPS"][piexif.GPSIFD.GPSLatitude]
    lon = exif["GPS"][piexif.GPSIFD.GPSLongitude]
    lat_ref = str(exif["GPS"][piexif.GPSIFD.GPSLatitudeRef], 'utf-8')
    lon_ref = str(exif["GPS"][piexif.GPSIFD.GPSLongitudeRef], 'utf-8')
    coordinates.append(lat)
    coordinates.append(lon)

    decimals = _to_decimals(coordinates)
    lat_normalized = decimals[0]
    lon_normalized = decimals[1]

    if lat_ref != 'N':
        lat_normalized = -lat_normalized
    if lon_ref != 'E':
        lon_normalized = -lon_normalized

    dump = json.dumps({
        "gps": {
            "latitude": lat_normalized,
            "longitude": lon_normalized
        }
    })
    print(f"JSON TO DESCRIPTION:\n{dump}")
    return dump


def dir_path(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"readable_dir:{path} is not a valid path")