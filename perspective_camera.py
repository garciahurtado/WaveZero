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
        self.far = 2000  # past this point all sprites are considered to be in the horizon line

        self.cam_x = pos_x
        self.cam_y = pos_y
        self.cam_z = pos_z

        self.half_width = int(self.screen_width / 2)
        self.half_height = int(self.screen_height / 2)

        self.vp = {"x": vp_x, "y": vp_y}  # vanishing point
        self.vp_x = int(vp_x)
        self.vp_y = int(vp_y)
        self.focal_length = focal_length  # Distance from the camera to the projection plane in pixels

        # Pre-multiply focal_length and aspect_ratio
        self.focal_length_aspect = self.focal_length * self.aspect_ratio

        # PreCalculate some values based on constants that will not change
        self.fov_y = self.calculate_fov(focal_length)
        self.fov_x = self.fov_y * self.aspect_ratio
        self.y_offset = self.half_height - vp_y
        self.vp_factor = self.vp_x / (self.screen_height - self.vp_y)
        self.vp_factor_y = 1 / (self.screen_height - self.vp_y)
        self.max_vp_scale = 2.2 # Allows parallax effect so that close objects move faster when the VP moves

        self.min_z = pos_z - 80
        self._y_factor_cache = {}

        self.vp_factor_y = 1 / (self.screen_height - vp_y)

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

    def to_2d(self, x: int=0, y: int=0, z: int=0, vp_scale=1):
        """
        Convert 3D coordinates to 2D screen coordinates, accounting for aspect ratio.
        In this 3D world, +z is up and +y is into the screen.

        Based on:
        https://forum.gamemaker.io/index.php?threads/basic-pseudo-3d-in-gamemaker.105242/
        """
        half_width = self.half_width
        focal_length = self.focal_length

        #prof.start_profile('cam.pos_assign')
        cam_y = self.cam_y
        cam_z = self.cam_z
        #prof.end_profile()

        #prof.start_profile('cam.vp_assign')
        vp_x = self.vp_x
        #prof.end_profile()

        # Adjust for camera position
        #prof.start_profile('cam.pos_adjust')
        orig_y = y
        orig_z = z
        y = orig_y - cam_y
        z = orig_z - cam_z
        #prof.end_profile()

        #prof.start_profile('cam.apply_persp_proj')
        # Apply perspective projection
        screen_x = (x * focal_length) / z
        screen_y = (y * focal_length) / z
        #prof.end_profile()

        #prof.start_profile('cam.apply_asp_ratio')
        # Apply aspect ratio correction
        screen_x = screen_x * self.aspect_ratio
        #prof.end_profile()

        #prof.start_profile('cam.convert_to_screen')
        # Convert to screen coordinates
        screen_x = int(screen_x + half_width)
        screen_y = int(self.y_offset - screen_y)

        #prof.end_profile()


        #prof.start_profile('cam.apply_vp')
        # Apply vanishing point adjustment
        # true_scale = (vp_scale * (self.max_vp_scale))
        screen_x = screen_x - (vp_x * vp_scale)
        # screen_x = screen_x - (vp_x)

        #prof.end_profile()

        return screen_x, screen_y


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

    def calculate_scale(self, z):
        relative_z = z - self.cam_z

        if relative_z <= self.near:
            relative_z = self.near + 0.000001

        # Use pre-multiplied focal_length_aspect
        scale = self.focal_length_aspect / relative_z

        return scale