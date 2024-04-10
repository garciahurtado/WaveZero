import math
import ulab as np


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

    def world_to_camera(self, camera):
        # Implement world-to-camera transformation
        # using the camera's position and orientation
        # and the transformation matrices
        # Return the transformed point in camera space

        translation_matrix = translate_matrix(-camera.position.x, -camera.position.y, -camera.position.z)
        rotation_matrix = rotate_matrix(-camera.look_at.x, -camera.look_at.y, -camera.look_at.z)
        transformation_matrix = np.dot(rotation_matrix, translation_matrix)
        transformed_vector = np.dot(transformation_matrix, self.vector)

        return Point3D(transformed_vector[0], transformed_vector[1], transformed_vector[2])


class Camera:
    def __init__(self, position=Point3D(0, 0, 0), look_at=Point3D(0, 0, 0), up=Point3D(0, 1, 0),
                 fov=60, near=0.1, far=100, screen_width=800, screen_height=600):
        self.position = position
        self.look_at = look_at
        self.up = up
        self.fov = fov
        self.near = near
        self.far = far
        self.screen_width = screen_width
        self.screen_height = screen_height

    def perspective_project(self, point):
        # Implement perspective projection
        # using the camera's field of view and clipping planes
        # Return the projected point on a 2D plane

        aspect_ratio = self.screen_width / self.screen_height
        fov_rad = math.radians(self.fov)
        tan_half_fov = math.tan(fov_rad / 2)

        projection_matrix = np.array([
            [1 / (aspect_ratio * tan_half_fov), 0, 0, 0],
            [0, 1 / tan_half_fov, 0, 0],
            [0, 0, (self.far + self.near) / (self.near - self.far),
             (2 * self.far * self.near) / (self.near - self.far)],
            [0, 0, -1, 0]
        ])
        projected_vector = np.dot(projection_matrix, point.vector)
        projected_vector /= projected_vector[3]

        return Point3D(projected_vector[0], projected_vector[1], projected_vector[2])

    def viewport_transform(self, point):
        # Map the projected point to the viewport's coordinate system
        # based on the screen width and height
        # Return the transformed point in viewport space

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


def rotate_matrix(angle_x, angle_y, angle_z):
    cos_x, sin_x = math.cos(angle_x), math.sin(angle_x)
    cos_y, sin_y = math.cos(angle_y), math.sin(angle_y)
    cos_z, sin_z = math.cos(angle_z), math.sin(angle_z)

    rotation_x = np.array([
        [1, 0, 0, 0],
        [0, cos_x, -sin_x, 0],
        [0, sin_x, cos_x, 0],
        [0, 0, 0, 1]
    ])

    rotation_y = np.array([
        [cos_y, 0, sin_y, 0],
        [0, 1, 0, 0],
        [-sin_y, 0, cos_y, 0],
        [0, 0, 0, 1]
    ])

    rotation_z = np.array([
        [cos_z, -sin_z, 0, 0],
        [sin_z, cos_z, 0, 0],
        [0, 0, 1, 0],
        [0, 0, 0, 1]
    ])

    return np.dot(rotation_z, np.dot(rotation_y, rotation_x))

def scale_matrix(sx, sy, sz):
    return np.array([
        [sx, 0, 0, 0],
        [0, sy, 0, 0],
        [0, 0, sz, 0],
        [0, 0, 0, 1]
    ])