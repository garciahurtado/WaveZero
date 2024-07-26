import framebuf
import math

import micropython
from profiler import Profiler as prof, timed
from ulab import numpy as np

class PerspectiveCamera():
    def __init__(self, display: framebuf.FrameBuffer, pos_x: int = 0, pos_y: int = 0, pos_z: int = 0, vp_x: int = 0,
                 vp_y: int = 0,
                 focal_length: float = 100) -> object:
        # Use display dimensions
        self.screen_width = display.width
        self.screen_height = display.height

        # Rest of the initialization remains the same
        self.fov = 120
        self.near = 40
        self.far = 2000
        self.horizon = vp_y

        self.aspect_ratio = self.screen_width / self.screen_height
        self.fov = np.radians(self.fov)

        self.fov_factor = 1 / math.tan(self.fov / 2)

        self.camera_x = 0
        self.camera_y = 0
        self.camera_z = 0

        self.half_width = int(self.screen_width / 2)
        self.half_height = int(self.screen_height / 2)

        self.pos: dict[str, int] = {"x": pos_x, "y": pos_y, "z": pos_z}  # location of camera in 3D space
        self.vp = {"x": vp_x, "y": vp_y}  # vanishing point
        self.focal_length = focal_length  # Distance from the camera to the projection plane in pixels
        self.fov_x, self.fov_y = self.calculate_fov(focal_length)

        self.horiz_z = 4000  # past this point all sprites are considered to be in the horizon line
        self.min_z = pos_z - 40
        self._z_factor_cache = {}

        self.min_yaw = 0
        self.max_yaw = -100

    def calculate_fov(self, focal_length):
        # Calculate the horizontal and vertical FOV
        h_fov = 2 * math.atan(self.screen_width / (2 * focal_length))
        v_fov = 2 * math.atan(self.screen_height / (2 * focal_length))

        # Convert to degrees
        h_fov_deg = math.degrees(h_fov)
        v_fov_deg = math.degrees(v_fov)

        return round(h_fov_deg), round(v_fov_deg)

    def _calculate_z_factor(self, z):
        # Adjust z relative to camera position
        relative_z = z - self.camera_y

        # Avoid division by zero
        if relative_z == 0:
            return None  # or handle this case as appropriate for your application

        # Calculate z_factor
        # The factor should increase as z increases (objects further away appear smaller)
        z_factor = self.focal_length / relative_z

        return z_factor

    def get_z_factor(self, z):
        if z not in self._z_factor_cache:
            self._z_factor_cache[z] = self._calculate_z_factor(z)
        return self._z_factor_cache[z]

    def to_2d(self, x: int=0, y: int=0, z: int=0):
        """Based on:
        https://forum.gamemaker.io/index.php?threads/basic-pseudo-3d-in-gamemaker.105242/"""
        pos_x = self.pos['x']
        pos_y = self.pos['y']
        pos_z = self.pos['z']

        vp_x = self.vp['x']
        vp_y = self.vp['y']

        z = int(z - pos_z)
        if z == 0:
            z = 0.000001 # avoid division by zero

        camera_y = pos_y
        screen_x = ((x * self.fov_x) / z) + self.half_width
        screen_y = (((y - camera_y) * self.fov_y) / z) + self.half_height
        screen_x = screen_x - pos_x
        screen_y = self.screen_height - screen_y - vp_y

        y_factor = (screen_y - vp_y) / (self.screen_height - vp_y)
        screen_x = screen_x - (vp_x * y_factor)

        # print(f"x/y : {screen_x} {screen_y}")

        return screen_x, screen_y

    def to_2d_v2(self, x, y, z):
        """
        Convert 3D coordinates to 2D screen coordinates.

        Coordinate system:
        - x+ is right
        - y+ is deep into the screen (away from the camera)
        - z+ is up

        The horizon is at z = self.horizon
        """
        # Translate point relative to camera
        x -= self.camera_x
        y -= self.camera_y
        z -= self.camera_z

        # Perspective projection for x
        if y != 0:
            screen_x = x / y * self.fov_factor
        else:
            screen_x = x * self.fov_factor * 1e6  # Arbitrarily large number

        # Adjust x for aspect ratio
        # screen_x = x / self.aspect_ratio


        # Convert x to screen coordinates
        # screen_x = screen_x + self.screen_width / 2
        #
        # z_factor_x = self.get_z_factor(x)
        # z_factor_y = self.get_z_factor(y)
        # print(f"z_factor: {z_factor}")

        screen_y = self.vp['y']
        # Apply perspective projection
        # screen_x = x * z_factor_x
        # screen_y = y * z_factor_y

        # Calculate vertical position based on fixed horizon
        if y != 0:
            # Calculate the projected z position
            projected_z = z / y * self.fov_factor

            # Map the projected z to screen coordinates with fixed horizon and vanishing point
            # screen_y = self.horizon  # Start at the horizon level
            screen_y += (projected_z + (self.horizon - self.vp['y']) / (y * self.fov_factor)) * self.horizon / (
                        2 * self.fov_factor)
        else:
            # Handle case when y is 0 (point at infinity)
            screen_y = self.screen_height / 2 if z >= self.horizon else self.screen_height

        # Apply vanishing point offset to y
        screen_y += self.vp['y']
        screen_x += self.half_width

        # Clamp screen_y to be within the screen bounds
        screen_y = max(0, min(self.screen_height, screen_y))

        screen_x, screen_y = int(screen_x), int(screen_y)

        return screen_x, screen_y

    def set_camera_position(self, x, y, z):
        self.camera_x = x
        self.camera_y = y
        self.camera_z = z

    def to_2d_y(self, x: int, y: int, z: int):
        """Based on:
        https://forum.gamemaker.io/index.php?threads/basic-pseudo-3d-in-gamemaker.105242/"""
        pos = self.pos
        z = int(z - pos['z'])
        if z == 0:
            z = 0.0001 # avoid division by zero

        camera_y = pos['y']
        screen_y = (((y - camera_y) * self.fov_y) / (z)) + self.half_height
        screen_y = self.screen_height - screen_y - self.vp['y']

        return screen_y

