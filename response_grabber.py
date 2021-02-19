import argparse
import logging
import os
import pathlib
from datetime import datetime
from os import path

from config import LOG_FORMAT, DIR_RESULT
from helper import dir_path, load_json, get_exif, get_hint_from_cmd

from api import LocalizeRequest, GetReconstructionPly


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
    headers_ply = {'Accept': 'model/ply'}
    params = {'p_reconstruction_id': reconstruction_id}
    return GetReconstructionPly(method='get', headers=headers_ply, params=params).execute()


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


if __name__ == '__main__':
    # Parse commandline arguments
    parser = argparse.ArgumentParser(description='Grab images from selected directory and localize them')

    parser.add_argument('directory', type=dir_path, default=None, help="Directory with images")
    parser.add_argument('--reference_images', type=dir_path, default=None, help="Directory with reference images")
    parser.add_argument('--hint', type=int, default=None, help="Series id to localized in")

    args = parser.parse_args()
    directory = args.directory
    ref_directory = args.reference_images

    dataset = read_dataset_simple(directory)

    timestamp = f'{datetime.now():%Y_%m_%d_%H_%M_%S%f}'
    timestamp_dir = f'{DIR_RESULT}/{timestamp}'
    logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

    if not path.exists(DIR_RESULT):
        os.mkdir(DIR_RESULT)
    if not path.exists(timestamp_dir):
        os.mkdir(timestamp_dir)

    for file in dataset:
        image_file = open(file, 'rb')
        description = get_exif(image_file.name)
        hint = get_hint_from_cmd(args.hint)
        form_data = {"image": image_file,
                     "description": description,
                     "hint": hint}
        response = localize_as(form_data)

        # Path logic (Creating timestamp directory with reconstructions ids directories with jsons and plys)
        if response.json()['status']['message'] != 'Cannot localize image':
            rec_id = response.json()['reconstruction_id']
            rec_dir = f"{timestamp_dir}/{rec_id}"
            if not path.exists(rec_dir):
                os.mkdir(rec_dir)
                # Downloading ply
                response_with_ply = get_ply(rec_id)
                with open(f"{rec_dir}/{rec_id}.ply", 'wb') as f1:
                    f1.write(response_with_ply.content)
            with open(f"{rec_dir}/{pathlib.Path(image_file.name).stem}.json", 'w') as f2:
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





