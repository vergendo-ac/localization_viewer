import argparse
import logging
import os
import pathlib
from datetime import datetime
from os import path
import base64
import uuid
import json
import piexif

from config import LOG_FORMAT, DIR_RESULT
from helper import dir_path, load_json, get_exif, get_hint_from_cmd

from api import LocalizeRequest, GetReconstructionPly, LocalizeByGeopose, GetReconstructionsJsonRequest


def read_dataset_simple(dataset_path):
    """
    Using to load simple dataset without distances
    :param dataset_path:
    :return:
    """
    jpg_list = pathlib.Path(dataset_path).glob("*.jpg")
    return sorted([str(jpg_name.absolute()) for jpg_name in list(jpg_list)])


def get_ply(reconstruction_id):
    """
    Wrapper for GetReconstructionPly class
    :param reconstruction_id:
    :return:
    """
    params = {'p_reconstruction_ids': "{" + str(reconstruction_id) + "}",
              'p_need_images': False,
              'p_need_polygon': False}
    response = GetReconstructionsJsonRequest(method='get', params=params).execute()

    sparse_cloud_path = response.json()[0]["reconstruction"]["sparse_cloud_path"] if len(response.json()) else ""

    if sparse_cloud_path == "":
        return None

    return GetReconstructionPly(method='get', path=sparse_cloud_path).execute()


def localize_as(request_data):
    """
    Wrapper for 2 types of localization request
    :param request_data:
    :return:
    """
    headers_img = None
    if isinstance(request_data, dict):
        # headers_img = {'Content-Type': 'multipart/form-data'}
        request_data = request_data
        return LocalizeRequest(method='post', headers=headers_img, files=request_data).execute()
    else:
        # headers_img = {'Content-Type': 'image/jpeg'}
        request_data = open(request_data, 'rb')
        return LocalizeRequest(method='post', headers=headers_img, data=request_data).execute()


def localize_native(image_path):
    image_file = open(image_path, 'rb')
    description = get_exif(image_file.name)
    hint = get_hint_from_cmd(args.hint)
    form_data = {"image": image_file,
                 "description": description,
                 "hint": hint}
    response = localize_as(form_data)

    return response


def localize_geopose(image_path):
    def load_image(img_file_name):
        """
        Load image and encode it in base64
        :param img_file_name:
        :return:
        """
        try:
            img_file = open(img_file_name, 'rb').read()
            img_file_base64 = base64.b64encode(img_file)
            return img_file_base64.decode('utf-8')
        except IOError:
            print("Wrong filename or file not exist\n")
            return None
        except:
            print("Base64 encode/decode error")
            return None


    def create_geopose_request(img_file_base64_string, lat, lon):
        """
        Create request body for geopose
        :param img_file_base64_string:
        :param lat:
        :param lon:
        :return:
        """
        return {
            "id": str(uuid.uuid4()),
            "timestamp": str(datetime.now()),
            "type": "geopose",
            "sensors": [
                {
                    "id": "0",
                    "type": "camera"
                },
                {
                    "id": "1",
                    "type": "geolocation"
                }
            ],
            "sensorReadings": [
                {
                    "timestamp": str(datetime.now()),
                    "sensorId": "0",
                    "reading": {
                        "sequenceNumber": 0,
                        "imageFormat": "JPG",
                        "imageOrientation": {
                            "mirrored": False,
                            "rotation": 0
                        },
                        "imageBytes": img_file_base64_string
                    }
                },
                {
                    "timestamp": str(datetime.now()),
                    "sensorId": "1",
                    "reading": {
                        "latitude": float(lat),
                        "longitude": float(lon),
                        "altitude": 0
                    }
                }
            ]
        }


    def to_decimals(coordinates):
        """
        Convert lat and lon from exif to decimals
        :param coordinates:
        :return:
        """
        decimals = []
        for coordinate in coordinates:
            decimal: float = (coordinate[0][0] / coordinate[0][1]) + \
                             ((coordinate[1][0] / coordinate[1][1]) / 60) + \
                             ((coordinate[2][0] / coordinate[2][1]) / 3600)
            decimals.append(decimal)
        return decimals

    def get_exif_from_img(imagefile):
        """
        Try to read exif from image file
        :return:
        """
        try:
            coordinates = []
            exif = piexif.load(imagefile)
            lat = exif["GPS"][piexif.GPSIFD.GPSLatitude]
            lon = exif["GPS"][piexif.GPSIFD.GPSLongitude]
            lat_ref = str(exif["GPS"][piexif.GPSIFD.GPSLatitudeRef], 'utf-8')
            lon_ref = str(exif["GPS"][piexif.GPSIFD.GPSLongitudeRef], 'utf-8')
            coordinates.append(lat)
            coordinates.append(lon)

            decimals = to_decimals(coordinates)
            lat_normalized = round(decimals[0], 6)
            lon_normalized = round(decimals[1], 6)

            if lat_ref != 'N':
                lat_normalized = -lat_normalized
            if lon_ref != 'E':
                lon_normalized = -lon_normalized
            return lat_normalized, lon_normalized
        except:
            print('Error reading latitude and longitude from imagefile EXIF data')
            return None, None

    lat, lon = get_exif_from_img(image_path)
    img_file_base64_string = load_image(image_path)
    req_body = create_geopose_request(img_file_base64_string, lat, lon)
    json_headers={'Content-Type': 'application/json'}
    request_data = json.dumps(req_body)
    return LocalizeByGeopose(method='post', headers=json_headers, data=request_data).execute()


if __name__ == '__main__':
    # Parse commandline arguments
    parser = argparse.ArgumentParser(description='Grab images from selected directory and localize them')

    parser.add_argument('directory', type=dir_path, default=None, help="Directory with images")
    parser.add_argument('--reference_images', type=dir_path, default=None, help="Directory with reference images")
    parser.add_argument('--hint', type=int, default=None, help="Series id to localized in")
    parser.add_argument('--use_oscp', action='store_true', default=False, help="Use oscp api to localize")

    args = parser.parse_args()
    directory = args.directory
    ref_directory = args.reference_images
    use_oscp = args.use_oscp

    dataset = read_dataset_simple(directory)

    timestamp = f'{datetime.now():%Y_%m_%d_%H_%M_%S%f}'
    timestamp_dir = f'{DIR_RESULT}/{timestamp}'
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    if not path.exists(DIR_RESULT):
        os.mkdir(DIR_RESULT)
    if not path.exists(timestamp_dir):
        os.mkdir(timestamp_dir)

    for file in dataset:
        is_successfull = False
        rec_id = None
        if use_oscp:
            response = localize_geopose(file)
            is_successfull = response.status_code == 200
            if is_successfull:
                rec_id = response.json()['geopose']['reconstruction_id']
        else:
            response = localize_native(file)
            is_successfull = response.json()['status']['message'] != 'Cannot localize image'
            if is_successfull:
                rec_id = response.json()['reconstruction_id']


        # Path logic (Creating timestamp directory with reconstructions ids directories with jsons and plys)
        if is_successfull:
            rec_dir = f"{timestamp_dir}/{rec_id}"
            if not path.exists(rec_dir):
                os.mkdir(rec_dir)
                # Downloading ply
                response_with_ply = get_ply(rec_id)
                with open(f"{rec_dir}/{rec_id}.ply", 'wb') as f1:
                    f1.write(response_with_ply.content)
            with open(f"{rec_dir}/{pathlib.Path(os.path.basename(file)).stem}.json", 'w') as f2:
                f2.write(load_json(response))

    # if reference directory presented in commandline arguments
    if ref_directory is not None:
        print(''.center(80, '='))
        print('Reference option was set')
        print(''.center(80, '='))
        ref_dir = f'{timestamp_dir}/references'
        if not path.exists(ref_dir):
            os.mkdir(ref_dir)
        ref_dataset = read_dataset_simple(ref_directory)
        for file_ref in ref_dataset:
            image_file = open(file_ref, 'rb')

            description = get_exif(image_file.name)
            hint = get_hint_from_cmd(args.hint)
            form_data = {"image": image_file,
                         "description": description,
                         "hint": hint}
            response = localize_as(form_data)
            rec_id = response.json()['reconstruction_id']
            rec_ref_dir = f"{ref_dir}/{rec_id}"
            if not path.exists(rec_ref_dir):
                os.mkdir(rec_ref_dir)
            with open(f"{rec_ref_dir}/{pathlib.Path(image_file.name).stem}.json", 'w') as f2:
                f2.write(load_json(response))





