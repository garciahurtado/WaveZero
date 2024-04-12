from ulab import numpy as np

from camera3d import Camera, Point3D
import math

class PerspectiveCamera():
    def __init__(self, screen_width, screen_height, pos_x=0, pos_y=0, pos_z=0, vp_x=0, vp_y=0, focal_length=100):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.focal_length = focal_length
        self.pos = {"x":pos_x, "y":pos_y, "z":pos_z} # location of camera in 3D space
        self.vp = {"x": vp_x, "y":vp_y} # vanishing point
        self.focal_length = focal_length # Distance from the camera to the projection plane in pixels
        self.horiz_z = 5000 # past this point all sprites are considered to be in the horizon line
        self.min_z = pos_z


    def to_viewport(self, point:Point3D):
        camera_point = point.world_to_camera(self.camera_3d)

        # Project the point onto the 2D screen
        projected_point = self.camera_3d.perspective_project(camera_point)

        # Transform the projected point to viewport coordinates
        viewport_point = self.camera_3d.viewport_transform(projected_point)

        # Invert Y, since Y is at the top on the viewport
        viewport_point.y = self.screen_height - viewport_point.y

        return int(viewport_point.x), int(viewport_point.y)




    def to2d2(self, x, y, z):
        """Based on:
        https://forum.gamemaker.io/index.php?threads/basic-pseudo-3d-in-gamemaker.105242/"""

        half_width = self.screen_width / 2
        half_height = self.screen_height / 2

        fov_angle = 70  # Desired FOV angle in degrees
        focal_length = half_height / np.tan(np.radians(fov_angle / 2))
        # print(f"Focal length: {focal_length}") # 55

        z = z - self.pos['z']
        if z == 0:
            z = 0.001 # avoid division by zero

        camera_y = self.pos['y']
        screen_x = (((x - self.pos['x']) * focal_length) / (z)) + half_width
        screen_y = (((y - camera_y) * focal_length) / (z)) + half_height

        # Invert, since the screen y=0 is at the top, and in 3D space it is on the floor
        screen_y = self.screen_height - screen_y - (self.vp['y'])
        screen_x = screen_x - (self.pos['x'])

        return int(screen_x), int(screen_y)