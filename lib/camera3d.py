import math
from ulab import numpy as np
class Point3D:
    def __init__(self, x, y, z):
        self.vector = np.array([x, y, z, 1])

    @property
    def x(self):
        return self.vector[0]

    @property
    def y(self):
        return self.vector[1]


    @property
    def z(self):
        return self.vector[2]

    @x.setter
    def x(self, value):
        self.vector[0] = value

    @y.setter
    def y(self, value):
        self.vector[1] = value

    @z.setter
    def z(self, value):
        self.vector[2] = value

    def world_to_camera(self, camera):
        translation_matrix = translate_matrix(-camera.position.x, -camera.position.y, -camera.position.z)
        rotation_matrix = rotate_y_matrix(-camera.yaw)
        transformation_matrix = np.dot(rotation_matrix, translation_matrix)
        transformed_vector = np.dot(transformation_matrix, self.vector)

        return Point3D(transformed_vector[0], transformed_vector[1], transformed_vector[2])

class Camera:
    def __init__(self, position=Point3D(0, 0, 0), yaw=0, fov=60, near=0.1, far=100, screen_width=800, screen_height=600):
        self.position = position
        self.yaw = yaw
        self.fov = fov
        self.near = near
        self.far = far
        self.screen_width = screen_width
        self.screen_height = screen_height

    def perspective_project(self, point):
        aspect_ratio = self.screen_width / self.screen_height
        fov_rad = math.radians(self.fov)
        tan_half_fov = math.tan(fov_rad / 2)

        projection_matrix = np.array([
            [1 / (aspect_ratio * tan_half_fov), 0, 0, 0],
            [0, 1 / tan_half_fov, 0, 0],
            [0, 0, (self.far + self.near) / (self.near - self.far), (2 * self.far * self.near) / (self.near - self.far)],
            [0, 0, -1, 0]
        ])
        projected_vector = np.dot(projection_matrix, point.vector)
        projected_vector /= projected_vector[3]

        return Point3D(projected_vector[0], projected_vector[1], projected_vector[2])

    def viewport_transform(self, point):
        viewport_matrix = np.array([
            [self.screen_width / 2, 0, 0, self.screen_width / 2],
            [0, -self.screen_height / 2, 0, self.screen_height / 2],
            [0, 0, 1, 0],
            [0, 0, 0, 1]
        ])
        transformed_vector = np.dot(viewport_matrix, point.vector)

        return Point3D(transformed_vector[0], transformed_vector[1], transformed_vector[2])

def translate_matrix(tx, ty, tz):
    return np.array([
        [1, 0, 0, tx],
        [0, 1, 0, ty],
        [0, 0, 1, tz],
        [0, 0, 0, 1]
    ])

def rotate_y_matrix(angle):
    cos_val = math.cos(angle)
    sin_val = math.sin(angle)
    return np.array([
        [cos_val, 0, sin_val, 0],
        [0, 1, 0, 0],
        [-sin_val, 0, cos_val, 0],
        [0, 0, 0, 1]
    ])