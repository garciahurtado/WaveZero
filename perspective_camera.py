import framebuf
import math

import micropython
from profiler import Profiler as prof, timed
from ulab import numpy as np
from uarray import array

class PerspectiveCamera():
    def __init__(self, display: framebuf.FrameBuffer, pos_x: int = 0, pos_y: int = 0, pos_z: int = 0, vp_x: int = 0,
                 vp_y: int = 0, min_y:int = 0, max_y:int = 0, fov=90.0) -> object:

        # Use display dimensions
        self.screen_width = display.width
        self.screen_height = display.height


        # Calculate aspect ratio
        self.aspect_ratio = self.screen_width / self.screen_height

        # Near / far clipping planes
        self.near = 0
        self.far = 1500  # past this point all sprites are considered to be in the horizon line

        self.cam_x = pos_x
        self.cam_y = pos_y
        self.cam_z = pos_z

        self.min_y = min_y
        self.max_y = max_y

        print(f"max+y ; {max_y}")
        print(f"min+y ; {min_y}")

        self.half_width = int(self.screen_width / 2)
        self.half_height = int(self.screen_height / 2)

        self.vp = {"x": vp_x, "y": vp_y}  # vanishing point
        self.vp_x = int(vp_x)
        self.vp_y = int(vp_y)
        # self.focal_length = focal_length  # Distance from the camera to the projection plane in pixels
        # Pre-multiply focal_length and aspect_ratio

        # PreCalculate some values based on constants that will not change


        # NEW WAY
        self.focal_length = self.calculate_focal_length(fov)
        # self.fov_y = self.calculate_fov(focal_length)
        self.fov_y = fov
        self.fov_x = self.fov_y * self.aspect_ratio
        self.focal_length_aspect = self.focal_length * self.aspect_ratio


        self.y_offset = self.half_height - vp_y
        self.vp_factor = self.vp_x / (self.screen_height - self.vp_y)
        self.vp_factor_y = 1 / (self.screen_height - self.vp_y)
        self.max_vp_scale = 3.5 # Allows parallax effect so that close objects move faster when the VP moves

        self.min_z = pos_z
        self._y_factor_cache = {}

        self._cache_index = 0
        self._cache_full = False
        self._cache_size = 200  # Adjust based on your needs
        self._scale_cache_z = None
        self._scale_cache_scale = None

        self.z_min = self.near - 20
        self.z_max = self.far
        self.near_plus_epsilon = self.near + 0.000001
        self.integer_factor = 65000

        self._precalculate_scale_cache()


    def calculate_fov(self, focal_length: float) -> float:
        # Calculate the vertical FOV
        v_fov = 2 * math.atan(self.screen_height / (2 * focal_length))

        # Convert to degrees
        return math.degrees(v_fov)

    def calculate_focal_length(self, fov: float) -> float:
        # Convert FOV to radians
        fov_rad = math.radians(fov)
        # Calculate focal length
        return (self.screen_height / 2) / math.tan(fov_rad / 2)

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
        #prof.end_profile('cam.pos_assign')

        #prof.start_profile('cam.vp_assign')
        vp_x = self.vp_x
        #prof.end_profile('cam.vp_assign')

        # Adjust for camera position
        #prof.start_profile('cam.pos_adjust')
        orig_y = y
        orig_z = z
        y = orig_y - cam_y
        z = orig_z - cam_z
        #prof.end_profile('cam.pos_adjust')

        #prof.start_profile('cam.apply_persp_proj')
        # Apply perspective projection
        screen_x = (x * focal_length) / z
        screen_y = (y * focal_length) / z
        #prof.end_profile('cam.apply_persp_proj')

        #prof.start_profile('cam.apply_asp_ratio')
        # Apply aspect ratio correction
        screen_x = screen_x * self.aspect_ratio
        #prof.end_profile('cam.apply_asp_ratio')

        #prof.start_profile('cam.convert_to_screen')
        # Convert to screen coordinates
        screen_x = screen_x + half_width
        screen_y = int(self.y_offset - screen_y)
        #prof.end_profile('cam.convert_to_screen')

        #prof.start_profile('cam.apply_vp')
        # Apply vanishing point adjustment
        screen_x = int(screen_x - (vp_x * vp_scale))
        #prof.end_profile('cam.apply_vp')

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

    def _precalculate_scale_cache(self):
        # Calculate the start and stop values for logspace
        # start = np.log10(self.near)
        # stop = np.log10(self.far)
        # start = self.near
        # stop = self.far

        # min_y and max_y are from 2D space

        if self.min_y  >= self.max_y:
            raise ArithmeticError("Min Y cannot be higher than Max Y")

        self._cache_size = self.max_y - self.min_y
        _new_cache_size = self._cache_size + 4
        print(f"CREATING A CACHE OF {_new_cache_size} elements")

        # Calculate logarithmically spaced values manually
        # ratio = (stop / start)
        # z_values = []
        # for i in range(self._cache_size):
        #     z_values.append(int(start * (ratio ** i)))
        #
        # # Remove duplicates and sort
        # z_values = sorted(set(z_values))
        #
        # print(f"Z VALUES: (count {len(z_values)}")
        # print(z_values)
        cache_size = (self.max_y - self.min_y) + 10 # Make room for negative Z, or > 1 scale


        # Recalculate cache_size based on unique integer z values
        # self._cache_size = len(self._scale_cache_z)
        current_z = 1500

        # size = self.max_y - self.min_y
        # print(f"rANGE: {self.z_min} / {self.z_max}")
        z_range = self.z_max - self.z_min
        y_range_orig = self.max_y - self.min_y

        # Adjust the 20 below to control at which Z you get scale = 1
        y_range = y_range_orig

        self._scale_cache = np.array([1*self.integer_factor] * (y_range+1), dtype=np.uint16)
        self._scale_cache_z = np.array([0] * (y_range+1), dtype=np.uint16)

        for z in range(z_range, 0, -1):
            """ Takes a Z value and converts it to a scale, which converts to a Y coord, and gets added as the index
            of a new entry into the cache array"""

            # print(f"Z iter: {z}")

            if z <= self.min_z:
                scale = 1
            elif z >= self.z_max:
                scale = 0.0001
            else:
                scale = self.calculate_scale(z)

            if scale == 0:
                scale = 0.0001

            if scale > 1:
                scale = 1
            scale = abs(scale)

            screen_y = int(scale * y_range_orig)
            if screen_y < 0:
                screen_y = 0

            # print(f"Screen Y: {screen_y} / Scale:{scale} / z: {z}")

            self._scale_cache[screen_y] = scale * self.integer_factor
            self._scale_cache_z[screen_y] = int(z)
            # last_y = screen_y

        # Convert scale cache to numpy array
        # self._scale_cache_scale = array('H', self._scale_cache_scale) # 2 bytes

        # print("*** SCALE CACHE ***")
        # for i, val in enumerate(self._scale_cache):
        #     print(f"[{i}] -> {val/self.integer_factor}")
        #
        # print("*** Z SCALE CACHE ***")
        # for i, val in enumerate(self._scale_cache_z):
        #     print(f"[{i}] -> {val}")

    def get_scale(self, z):
        """ Get the scale for the closest Z to ours in the scale cache"""

        if type(z) is not int:
            raise ArithmeticError("Z must be an integer")

        # Find the closest z value in the cache
        idx = self._find_closest(self._scale_cache_z, z)

        # Adjust for camera position
        y = idx
        scale = self._scale_cache[idx]
        scale = scale / self.integer_factor # unconvert
        y = idx + self.min_y

        return y, scale

        # return at original dimension
        # scale = scale / 10000
        #
        # scale = draw_y / (self.screen_height - self.vp_y)
        #
        # print(f"GET SC: z: {z} sc: {scale}")
        # return scale

    def get_y(self, z, scale=None):
        """ Get the Y coordinate given a Z"""
        if scale:
            my_scale = scale
        else:
            my_scale = self.get_scale(z)

        total_dist = self.screen_height - self.vp_y
        y = (my_scale * total_dist)
        return int(y)

    def calculate_scale(self, z):
        if z > self.z_max:
            return 0.0001
        elif z == 0:
            return 1

        relative_z = z - self.cam_z
        # relative_z = z

        if relative_z == 0:
            relative_z = self.near_plus_epsilon

        scale = self.focal_length_aspect * (1.0 / relative_z)

        # Optionally, you can invert the scale for negative z values
        # if relative_z < 0:
        #     scale = -scale

        return scale

    def _find_closest(self, arr, z):

        if len(arr) == 0:
            return None

        if z >= arr[0]:
            return 0

        last_non_zero = 0
        for i in range(len(arr) - 1, -1, -1):
            if arr[i] != 0:
                last_non_zero = i
                break

        if z <= arr[last_non_zero]:
            return last_non_zero

        left, right = 0, last_non_zero
        while left <= right:
            mid = (left + right) // 2
            if arr[mid] == z:
                return mid
            elif arr[mid] > z:
                left = mid + 1
            else:
                right = mid - 1

        if right < 0:
            return 0
        if left >= len(arr):
            return len(arr) - 1

        return right if abs(z - arr[right]) <= abs(z - arr[left]) else left