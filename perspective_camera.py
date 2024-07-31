import framebuf
import math

import micropython
from profiler import Profiler as prof, timed
from ulab import numpy as np

class PerspectiveCamera():
    def __init__(self, display: framebuf.FrameBuffer, pos_x: int = 0, pos_y: int = 0, pos_z: int = 0, vp_x: int = 0,
                 vp_y: int = 0,
                 focal_length=None) -> object:

        # Use display dimensions
        self.screen_width = display.width
        self.screen_height = display.height

        # Calculate aspect ratio
        self.aspect_ratio = self.screen_width / self.screen_height

        # Near / far clipping planes
        self.near = 0
        self.far = self.horiz_z = 2000  # past this point all sprites are considered to be in the horizon line

        self.cam_x = pos_x
        self.cam_y = pos_y
        self.cam_z = pos_z

        self.half_width = int(self.screen_width / 2)
        self.half_height = int(self.screen_height / 2)

        self.vp = {"x": vp_x, "y": vp_y}  # vanishing point
        self.vp_x = vp_x
        self.vp_y = vp_y
        self.focal_length = focal_length  # Distance from the camera to the projection plane in pixels
        self.fov_y = self.calculate_fov(focal_length)
        self.fov_x = self.fov_y * self.aspect_ratio


        self.min_z = pos_z - 80
        self._y_factor_cache = {}

        self.min_yaw = 0
        self.max_yaw = -100

    def calculate_fov(self, focal_length: float) -> float:
        # Calculate the vertical FOV
        v_fov = 2 * math.atan(self.screen_height / (2 * focal_length))

        # Convert to degrees
        return math.degrees(v_fov)

    def _calculate_y_factor(self, y):
        # Adjust y relative to camera position
        relative_y = self.screen_height - self.vp_y

        # Avoid division by zero
        if relative_y == 0:
            return None  # or handle this case as appropriate for your application

        # Calculate y_factor
        # The factor should increase as y increases (objects further away appear smaller)
        y_factor = self.focal_length / relative_y

        return y_factor

    def get_y_factor(self, y):
        if y not in self._y_factor_cache:
            self._y_factor_cache[y] = self._calculate_y_factor(y)
        return self._y_factor_cache[y]

    def to_2d(self, x: int=0, y: int=0, z: int=0):
        """
        Convert 3D coordinates to 2D screen coordinates, accounting for aspect ratio.
        In this 3D world, +z is up and +y is into the screen.

        Based on:
        https://forum.gamemaker.io/index.php?threads/basic-pseudo-3d-in-gamemaker.105242/
        """
        cam_x = self.cam_x
        cam_y = self.cam_y
        cam_z = self.cam_z

        vp_x = self.vp_x
        vp_y = self.vp_y
        screen_height = self.screen_height

        # Adjust for camera position
        x = x - cam_x
        y = y - cam_y
        z = z - cam_z

        if z == 0:
            z = 0.000001 # avoid division by zero

        # Apply perspective projection
        screen_x = (x * self.focal_length) / z
        screen_y = (y * self.focal_length) / z

        # Apply aspect ratio correction
        screen_x *= self.aspect_ratio

        # Convert to screen coordinates
        screen_x = screen_x + self.half_width
        screen_y = screen_height - (screen_y + self.half_height) - vp_y

        # Apply vanishing point adjustment
        y_factor = (screen_y - vp_y) / (screen_height - vp_y)
        screen_x = screen_x - (vp_x * y_factor)

        # print(f"x/y : {screen_x} {screen_y}")

        return int(screen_x), int(screen_y)

    def set_camera_position(self, x, y, z):
        self.camera_x = x
        self.camera_y = y
        self.camera_z = z

    #@timed
    def to_2d_y(self, x: int, y: int, z: int):
        """Like the avove, but simplified to only calculate the Y coordinate"""
        z = int(z - self.cam_z)
        if z == 0:
            z = 0.0001 # avoid division by zero

        camera_y = self.cam_y
        screen_y = (((y - camera_y) * self.fov_y) / (z)) + self.half_height
        screen_y = self.screen_height - screen_y - self.vp_y

        return screen_y

