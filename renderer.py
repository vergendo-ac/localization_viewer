import argparse
import json
import logging
import pathlib
import re
from pathlib import PurePath

from config import LOG_FORMAT, WINDOW_WIDTH, WINDOW_HEIGHT, DEFAULT_VIEW_DATA
from helper import dir_path
from natsort import natsorted
from open3d import *

from api import GetReconstructionsJsonRequest

logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)

placeholders_ids = []


def draw_line(path_for_points, color):
    """
    Draw path of queries
    :param path_for_points:
    :param color:
    :return:
    """

    lines = [[i, i + 1] for i in range(len(path_for_points))]
    colors = [color for i in range(len(lines))]
    line_set = geometry.LineSet(
        points=utility.Vector3dVector(path_for_points),
        lines=utility.Vector2iVector(lines),
    )
    line_set.colors = utility.Vector3dVector(colors)
    return line_set


def get_camera_object(scene_json, color):
    """
    Create camera object from json as TriangleMesh
    :param scene_json:
    :param color:
    :return:
    """
    with open(scene_json) as f:
        scene = json.load(f)

    camera_position = [scene["camera"]["pose"]["position"]["x"], scene["camera"]["pose"]["position"]["y"],
                       scene["camera"]["pose"]["position"]["z"]]
    camera_orientation = [scene["camera"]["pose"]["orientation"]["w"], scene["camera"]["pose"]["orientation"]["x"],
                          scene["camera"]["pose"]["orientation"]["y"], scene["camera"]["pose"]["orientation"]["z"]]
    # camera = geometry.TriangleMesh.create_arrow(cylinder_radius=0.3, cone_radius=1.5 / 3, cylinder_height=5.0 / 3,
    #                                             cone_height=4.0 / 3, resolution=20, cylinder_split=4, cone_split=1)
    camera = geometry.TriangleMesh.create_sphere(radius=0.3)
    camera.compute_vertex_normals()
    camera.paint_uniform_color(color)

    camera_rotation = geometry.get_rotation_matrix_from_quaternion(camera_orientation)
    camera.rotate(camera_rotation, [0, 0, 0])
    camera.translate(camera_position)
    return camera


def scene_object(scene_json):
    """
    Create placeholder object as list of Open3d primitives
    :param scene_json:
    :return:
    """
    geometries = []
    with open(scene_json) as f:
        scene = json.load(f)
    for placeholder in scene["placeholders"]:

        if placeholder['placeholder_id'] not in placeholders_ids:
            placeholders_ids.append(placeholder['placeholder_id'])
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

            normal = geometry.TriangleMesh.create_arrow(cylinder_radius=0.3, cone_radius=1.5 / 3, cylinder_height=5.0 / 3,
                                                        cone_height=4.0 / 3, resolution=20, cylinder_split=4, cone_split=1)
            normal.compute_vertex_normals()
            normal.paint_uniform_color([0.9, 0.7, 0.1])
            normal_rotation = geometry.get_rotation_matrix_from_quaternion(orientation)
            normal.rotate(normal_rotation, [0, 0, 0])
            normal.translate(position)

            geometries.append(normal)
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


def get_scale(rec_id):
    """
    Get points cloud scale with GetReconstructionsJson request
    :param rec_id:
    :return:
    """
    params = {'p_reconstruction_ids': "{" + str(rec_id) + "}",
              'p_need_images': False,
              'p_need_polygon': False}
    scale = GetReconstructionsJsonRequest(method='get', params=params).execute()
    return scale.json()[0]['reconstruction']['ecef']['human_readable_info']['scale']


if __name__ == '__main__':
    # Parse commandline arguments
    parser = argparse.ArgumentParser(description='Draw points cloud with cameras and placeholder')

    parser.add_argument('directory', type=dir_path, default=None, help="Directory with points cloud and localization responses")
    parser.add_argument('--reference_images', type=dir_path, default=None, help="Directory with reference images")
    args = parser.parse_args()
    directory = args.directory
    ref_directory = args.reference_images


    # Load datasets and scale info
    dataset = read_dataset_simple(directory)
    scale = get_scale(str(PurePath(directory).name))
    print(str(PurePath(directory).name))

    # Load cloud and set scale
    cloud = io.read_point_cloud(directory+'/'+str(PurePath(directory).name)+'.ply')
    cloud.scale(scale, [0, 0, 0])
    cloud = cloud.voxel_down_sample(voxel_size=0.02)
    cloud, _ = cloud.remove_radius_outlier(nb_points=16, radius=0.5)

    # Create visualization object with callback and add objects to render
    vis = visualization.VisualizerWithKeyCallback()
    vis.create_window(width=WINDOW_WIDTH, height=WINDOW_HEIGHT)
    vis.get_render_option().point_size = 1
    vis.get_render_option().background_color = [0, 0, 0]
    vis.add_geometry(cloud)

    path_of_camera = []

    for json_path in dataset:
        camera_query = get_camera_object(json_path, [0, 0, 1])
        path_of_camera.append(camera_query.get_center())
        vis.add_geometry(camera_query)
        list_of_objects = scene_object(json_path)
        for object_geometry in list_of_objects:
            vis.add_geometry(object_geometry)

    vis.add_geometry(draw_line(path_of_camera, [0, 1, 1]))

    # if reference directory presented in commandline arguments
    if ref_directory is not None:
        dataset = read_dataset_simple(ref_directory)
        path_of_camera2 = []
        for json_path in dataset:
            camera_query = get_camera_object(json_path, [1, 0, 0])
            path_of_camera2.append(camera_query.get_center())
            vis.add_geometry(camera_query)

    # Keys for callback: X(88) and Z(z)
    vis.register_key_callback(90, save)
    vis.register_key_callback(88, load)

    vis.run()
    vis.destroy_window()
