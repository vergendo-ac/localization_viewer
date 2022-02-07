import argparse
import json
import logging
import pathlib
import re
from pathlib import PurePath
import math

from config import LOG_FORMAT, WINDOW_WIDTH, WINDOW_HEIGHT, DEFAULT_VIEW_DATA
from helper import dir_path
from natsort import natsorted
from open3d import *
import numpy as np
from pyquaternion import Quaternion

from api import GetReconstructionsJsonRequest

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

placeholders_ids = []


a = 6378137
b = 6356752.3142
f = (a - b) / a
e_sq = f * (2-f)


def align_cloud(cloud):
    yz_rotation = Quaternion(axis=[1, 0, 0], angle=-(np.pi/2))

    cloud_rotation = geometry.get_rotation_matrix_from_quaternion(yz_rotation.elements)
    cloud.rotate(cloud_rotation, [0, 0, 0])


def geodetic_to_ecef(lat, lon, h):
    # (lat, lon) in WSG-84 degrees
    # h in meters
    lamb = math.radians(lat)
    phi = math.radians(lon)
    s = math.sin(lamb)
    N = a / math.sqrt(1 - e_sq * s * s)

    sin_lambda = math.sin(lamb)
    cos_lambda = math.cos(lamb)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)

    x = (h + N) * cos_lambda * cos_phi
    y = (h + N) * cos_lambda * sin_phi
    z = (h + (1 - e_sq) * N) * sin_lambda

    return x, y, z


def ecef_to_enu(x, y, z, lat0, lon0, h0):
    lamb = math.radians(lat0)
    phi = math.radians(lon0)
    s = math.sin(lamb)
    N = a / math.sqrt(1 - e_sq * s * s)

    sin_lambda = math.sin(lamb)
    cos_lambda = math.cos(lamb)
    sin_phi = math.sin(phi)
    cos_phi = math.cos(phi)

    x0 = (h0 + N) * cos_lambda * cos_phi
    y0 = (h0 + N) * cos_lambda * sin_phi
    z0 = (h0 + (1 - e_sq) * N) * sin_lambda

    xd = x - x0
    yd = y - y0
    zd = z - z0

    xEast = -sin_phi * xd + cos_phi * yd
    yNorth = -cos_phi * sin_lambda * xd - sin_lambda * sin_phi * yd + cos_lambda * zd
    zUp = cos_lambda * cos_phi * xd + cos_lambda * sin_phi * yd + sin_lambda * zd

    return xEast, yNorth, zUp


def geodetic_to_enu(lat, lon, h, lat_ref, lon_ref, h_ref):
    x, y, z = geodetic_to_ecef(lat, lon, h)
    
    return ecef_to_enu(x, y, z, lat_ref, lon_ref, h_ref)


def draw_line(path_for_points, color):
    """
    Draw path of queries
    :param path_for_points:
    :param color:
    :return:
    """

    lines = [[i, i + 1] for i in range(len(path_for_points)-1)]
    colors = [color for i in range(len(lines))]
    line_set = geometry.LineSet(
        points=utility.Vector3dVector(path_for_points),
        lines=utility.Vector2iVector(lines),
    )
    line_set.colors = utility.Vector3dVector(colors)
    return line_set


def get_camera_ecef(scene_json):
    with open(scene_json) as f:
        scene = json.load(f)
    return [scene["geopose"]["ecefPose"]["position"]["x"],
            scene["geopose"]["ecefPose"]["position"]["y"],
            scene["geopose"]["ecefPose"]["position"]["z"]]


def get_camera_geodetic(scene_json):
    with open(scene_json) as f:
        scene = json.load(f)
    return [scene["geopose"]["pose"]['latitude'],
            scene["geopose"]["pose"]['longitude'],
            scene["geopose"]["pose"]['ellipsoidHeight']]


def get_camera_object(scene_json, color, cs, zero=None):
    """
    Create camera object from json as TriangleMesh
    :param scene_json:
    :param color:
    :return:
    """
    with open(scene_json) as f:
        scene = json.load(f)

    if cs == 'local':
        if 'camera' in scene:
            camera_position = [scene["camera"]["pose"]["position"]["x"], scene["camera"]["pose"]["position"]["y"],
                               scene["camera"]["pose"]["position"]["z"]]
            camera_orientation = [scene["camera"]["pose"]["orientation"]["w"], scene["camera"]["pose"]["orientation"]["x"],
                                  scene["camera"]["pose"]["orientation"]["y"], scene["camera"]["pose"]["orientation"]["z"]]
        else:
            camera_position = [scene["geopose"]["localPose"]["position"]["x"], scene["geopose"]["localPose"]["position"]["y"],
                               scene["geopose"]["localPose"]["position"]["z"]]
            camera_orientation = [scene["geopose"]["localPose"]["orientation"]["w"], scene["geopose"]["localPose"]["orientation"]["x"],
                                  scene["geopose"]["localPose"]["orientation"]["y"], scene["geopose"]["localPose"]["orientation"]["z"]]            

    elif cs == 'ecef':
        camera_position = [scene["geopose"]["ecefPose"]["position"]["x"], scene["geopose"]["ecefPose"]["position"]["y"],
                           scene["geopose"]["ecefPose"]["position"]["z"]]
        camera_orientation = [scene["geopose"]["ecefPose"]["orientation"]["w"], scene["geopose"]["ecefPose"]["orientation"]["x"],
                              scene["geopose"]["ecefPose"]["orientation"]["y"], scene["geopose"]["ecefPose"]["orientation"]["z"]]
    elif cs == 'enu':
        geodetic_position = [scene['geopose']['pose']['latitude'], scene['geopose']['pose']['longitude'], scene['geopose']['pose']['ellipsoidHeight']]
        camera_position = geodetic_to_enu(geodetic_position[0], geodetic_position[1], geodetic_position[2], zero[0], zero[1], zero[2])
        camera_orientation = [scene["geopose"]['pose']["quaternion"]["w"], scene["geopose"]['pose']["quaternion"]["x"],
                              scene["geopose"]['pose']["quaternion"]["y"], scene["geopose"]['pose']["quaternion"]["z"]] 

     
    camera = geometry.TriangleMesh.create_sphere(radius=0.5)
    camera.compute_vertex_normals()
    camera.paint_uniform_color(color)

    camera.translate(camera_position)

    camera_rotation = geometry.get_rotation_matrix_from_quaternion(camera_orientation)

    camera_system = geometry.TriangleMesh.create_coordinate_frame(size=2.0)
    camera_system.compute_vertex_normals()
    camera_system.rotate(camera_rotation, [0, 0, 0])
    camera_system.translate(camera_position)

    if cs == 'ecef':
        camera.translate(zero)
        camera_system.translate(zero)

    return camera, camera_system


def scene_object(scene_json, cs, zero=None):
    """
    Create placeholder object as list of Open3d primitives
    :param scene_json:
    :return:
    """
    geometries = []
    with open(scene_json) as f:
        scene = json.load(f)

    objects = []
    if cs == 'local':
        if 'placeholders' in scene:
            objects = scene["placeholders"]
        else:
            objects = scene['scrs']
    elif cs == 'enu' or cs == 'ecef':
        objects = scene['scrs']
    for placeholder in objects:
        placeholder_id = placeholder['placeholder_id'] if 'placeholder_id' in placeholder else placeholder['id']
        if placeholder_id not in placeholders_ids:
            placeholders_ids.append(placeholder_id)

            if cs == 'local':
                if 'content' not in placeholder:
                    position = [placeholder["pose"]["position"]["x"], placeholder["pose"]["position"]["y"],
                                placeholder["pose"]["position"]["z"]]
                    orientation = [placeholder["pose"]["orientation"]["w"], placeholder["pose"]["orientation"]["x"],
                                   placeholder["pose"]["orientation"]["y"], placeholder["pose"]["orientation"]["z"]]

                    frame_points = []
                    if "frame" in placeholder:
                        for frame_item in placeholder["frame"]:
                            point = [frame_item["x"], frame_item["y"], frame_item["z"]]
                            frame_sphere = geometry.TriangleMesh.create_sphere(radius=0.5)
                            frame_sphere.compute_vertex_normals()
                            frame_sphere.paint_uniform_color([0.1, 0.7, 0.1])
                            sphere_rotation = geometry.get_rotation_matrix_from_quaternion(orientation)
                            frame_sphere.translate(point)
                            frame_sphere.translate(position)
                            frame_sphere.rotate(sphere_rotation, position)

                            geometries.append(frame_sphere)

                            frame_points.append(frame_sphere.get_center())

                        frame_lines = [[0, 1], [1, 2], [2, 3], [3, 0]]

                        line_set = geometry.LineSet(points=utility.Vector3dVector(frame_points),
                                                    lines=utility.Vector2iVector(frame_lines))
                        colors = [[0.1, 0.7, 0.1] for i in range(len(frame_lines))]
                        line_set.colors = utility.Vector3dVector(colors)
                        geometries.append(line_set)
                else:
                    position = [placeholder['content']["localPose"]["position"]["x"], placeholder['content']["localPose"]["position"]["y"],
                                placeholder['content']["localPose"]["position"]["z"]]
                    orientation = [placeholder['content']["localPose"]["orientation"]["w"], placeholder['content']["localPose"]["orientation"]["x"],
                                   placeholder['content']["localPose"]["orientation"]["y"], placeholder['content']["localPose"]["orientation"]["z"]]                    
            elif cs == 'ecef':
                position = [placeholder['content']["ecefPose"]["position"]["x"], placeholder['content']["ecefPose"]["position"]["y"],
                            placeholder['content']["ecefPose"]["position"]["z"]]
                orientation = [placeholder['content']["ecefPose"]["orientation"]["w"], placeholder['content']["ecefPose"]["orientation"]["x"],
                               placeholder['content']["ecefPose"]["orientation"]["y"], placeholder['content']["ecefPose"]["orientation"]["z"]]
            elif cs == 'enu':
                geodetic_position = [placeholder['content']['geopose']['latitude'], placeholder['content']['geopose']['longitude'], placeholder['content']['geopose']['ellipsoidHeight']]
                position = geodetic_to_enu(geodetic_position[0], geodetic_position[1], geodetic_position[2], zero[0], zero[1], zero[2])
                orientation = [placeholder['content']["geopose"]["quaternion"]["w"], placeholder['content']["geopose"]["quaternion"]["x"],
                               placeholder['content']["geopose"]["quaternion"]["y"], placeholder['content']["geopose"]["quaternion"]["z"]]

            rotation = geometry.get_rotation_matrix_from_quaternion(orientation)

            obj_system = geometry.TriangleMesh.create_coordinate_frame(size=2.0)
            obj_system.compute_vertex_normals()
            obj_system.rotate(rotation, [0, 0, 0])
            obj_system.translate(position)
            if cs == 'ecef':
                obj_system.translate(zero)

            obj_position = geometry.TriangleMesh.create_sphere(radius=0.5)
            obj_position.compute_vertex_normals()
            obj_position.translate(position)
            if cs == 'ecef':
                obj_position.translate(zero)

            geometries.append(obj_system)
            geometries.append(obj_position)

    return geometries


def read_dataset_simple(dataset_path):
    """
    Using to load simple dataset without distances
    :param dataset_path:
    :return:
    """
    jpg_list = pathlib.Path(dataset_path).glob("*.json")
    return natsorted([str(json_name.absolute()) for json_name in list(jpg_list)])


def get_rec_id_path(message_to_parse):
    """
    Parse ['status']['message'] to get path to reconstruction
    """
    result = re.search("<.*?>", message_to_parse)
    if result is not None:
        return re.sub('<?>?', '', result.group(0))
    else:
        raise Exception("Something wrong with string ['status']['message']")


def save(visu):
    """
    Save view position
    :param visu:
    :return:
    """
    ctr = visu.get_view_control()
    param = ctr.convert_to_pinhole_camera_parameters()
    io.write_pinhole_camera_parameters(DEFAULT_VIEW_DATA, param)


def load(visu):
    """
    Load view position
    :param visu:
    :return:
    """
    ctr = visu.get_view_control()
    param = io.read_pinhole_camera_parameters(DEFAULT_VIEW_DATA)
    ctr.convert_from_pinhole_camera_parameters(param)


def get_scale_ecef_gps_geopose_azimuth_gravity(rec_id):
    """
    Get points cloud scale with GetReconstructionsJson request
    :param rec_id:
    :return:
    """
    params = {'p_reconstruction_ids': "{" + str(rec_id) + "}",
              'p_need_images': False,
              'p_need_polygon': False}
    response = GetReconstructionsJsonRequest(method='get', params=params).execute()
    origin_geopose_position = [response.json()[0]["reconstruction"]['ecef']['human_readable_info']['origin_geopose']["latitude"],
        response.json()[0]["reconstruction"]['ecef']['human_readable_info']['origin_geopose']["longitude"],
        response.json()[0]["reconstruction"]['ecef']['human_readable_info']['origin_geopose']["ellipsoidHeight"]]
    origin_geopose_orientation = [
        response.json()[0]['reconstruction']['ecef']['human_readable_info']['origin_geopose']['quaternion']['w'],
        response.json()[0]['reconstruction']['ecef']['human_readable_info']['origin_geopose']['quaternion']['x'],
        response.json()[0]['reconstruction']['ecef']['human_readable_info']['origin_geopose']['quaternion']['y'],
        response.json()[0]['reconstruction']['ecef']['human_readable_info']['origin_geopose']['quaternion']['z']]

    return (response.json()[0]['reconstruction']['ecef']['human_readable_info']['scale'],
            np.array(response.json()[0]["reconstruction"]["ecef"]["transformation"]).reshape(4, 4).transpose(),
            [response.json()[0]['reconstruction']['ecef']['human_readable_info']['gps']['latitude'],
            response.json()[0]['reconstruction']['ecef']['human_readable_info']['gps']['longitude'],
            response.json()[0]['reconstruction']['ecef']['human_readable_info']['gps']['altitude']],
            (origin_geopose_position, origin_geopose_orientation),
            response.json()[0]['reconstruction']['ecef']['human_readable_info']['azimuth'],
            response.json()[0]['reconstruction']['ecef']['human_readable_info']['gravity'])


def filter_cloud(cloud):
    cloud = cloud.voxel_down_sample(voxel_size=0.02)
    cloud, _ = cloud.remove_radius_outlier(nb_points=16, radius=0.5)
    return cloud


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Draw points cloud with cameras and placeholder')

    parser.add_argument('directory', type=dir_path, default=None, help="Directory with points cloud and localization responses")
    parser.add_argument('--cs', choices=['local', 'enu', 'ecef'], default='local', help="Show the result in a specified coordinate system")
    parser.add_argument('--no_filter', action='store_true', default=False, help="Do not filter cloud")
    parser.add_argument('--hide_objects', action='store_true', default=False, help="Hide objects")
    parser.add_argument('--hide_cameras', action='store_true', default=False, help="Hide cameras")
    parser.add_argument('--hide_cloud', action='store_true', default=False, help="Hide cloud")
    parser.add_argument('--hide_frame', action='store_true', default=False, help="Hide cloud frame")

    args = parser.parse_args()
    directory = args.directory
    cs = args.cs
    no_filter = args.no_filter
    hide_objects = args.hide_objects
    hide_cameras = args.hide_cameras
    hide_cloud = args.hide_cloud
    hide_frame = args.hide_frame


    # Load datasets and scale info
    dataset = read_dataset_simple(directory)

    # Create visualization object with callback and add objects to render
    vis = visualization.VisualizerWithKeyCallback()
    vis.create_window(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
    vis.get_render_option().point_size = 1
    vis.get_render_option().background_color = [0, 0, 0]

    cloud_path = directory+'/'+str(PurePath(directory).name)+'.ply'
    cloud = io.read_point_cloud(cloud_path)

    scale, ecef, gps, origin_geopose, azimuth, gravity = get_scale_ecef_gps_geopose_azimuth_gravity(str(PurePath(directory).name))

    zero = None

    if not hide_cloud:
        if cs == 'local':
            cloud.scale(scale, [0, 0, 0])

            if no_filter is False:
                cloud = filter_cloud(cloud)
        elif cs == 'ecef':
            zero = get_camera_ecef(dataset[0])
            zero = np.array(zero) * -1
            cloud.transform(ecef)
            cloud.translate(zero)

            if no_filter is False:
                cloud = filter_cloud(cloud)
        elif cs == 'enu':
            align_cloud(cloud)
            cloud.scale(scale, [0, 0, 0])

            cloud_rotation = geometry.get_rotation_matrix_from_quaternion(origin_geopose[1])
            cloud.rotate(cloud_rotation, [0, 0, 0])

            zero = origin_geopose[0]
            cloud_position = geodetic_to_enu(gps[0], gps[1], gps[2], zero[0], zero[1], zero[2])
            cloud.translate(cloud_position)

            if no_filter is False:
                cloud = filter_cloud(cloud)
        vis.add_geometry(cloud)

    path_of_camera = []

    for scene_json in dataset:
        if not hide_cameras:
            camera_position, camera_system = get_camera_object(scene_json, [0, 0, 1], cs, zero)
            path_of_camera.append(camera_position.get_center())
            vis.add_geometry(camera_system)
            vis.add_geometry(camera_position)
        if not hide_objects:
            list_of_objects = scene_object(scene_json, cs, zero)
            for object_geometry in list_of_objects:
                vis.add_geometry(object_geometry)

    if not hide_cameras:
        vis.add_geometry(draw_line(path_of_camera, [0, 1, 1]))

    if not hide_frame:
        coord_frame = geometry.TriangleMesh.create_coordinate_frame(size=3.)
        coord_frame.translate([0, 0, 0])
        vis.add_geometry(coord_frame)

    vis.run()
    vis.destroy_window()
