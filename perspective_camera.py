import framebuf
import math

import micropython
import sys

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
        self.near = -60
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

        # Calculate FOV and focal length
        self.fov_y = fov
        self.focal_length = self.calculate_focal_length(self.fov_y)
        self.fov_x = self.calculate_fov(self.focal_length)  # Horizontal FOV
        self.focal_length_aspect = self.focal_length * self.aspect_ratio

        self.y_offset = self.half_height - vp_y
        self.vp_factor = self.vp_x / (self.screen_height - self.vp_y)
        self.vp_factor_y = 1 / (self.screen_height - self.vp_y)
        self.max_vp_scale = 3 # Increase / decrease parallax effect (so that )close objects move faster when the VP moves

        self.min_z = pos_z
        self._y_factor_cache = {}

        self._cache_index = 0
        self._cache_full = False
        self._cache_size = 64  # Adjust based on your needs
        self._scale_cache_z = None
        self._scale_cache_scale = None

        self.z_min = self.near - 20
        self.z_max = self.far
        self.near_plus_epsilon = self.near + 0.000001

        # self.compare_methods()
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

        prof.start_profile('cam.pos_assign')
        cam_y = self.cam_y
        cam_z = self.cam_z
        prof.end_profile('cam.pos_assign')

        prof.start_profile('cam.vp_assign')
        vp_x = self.vp_x
        prof.end_profile('cam.vp_assign')

        # Adjust for camera position
        prof.start_profile('cam.pos_adjust')
        orig_y = y
        orig_z = z
        y = orig_y - cam_y
        z = orig_z - cam_z
        prof.end_profile('cam.pos_adjust')

        prof.start_profile('cam.apply_persp_proj')
        # Apply perspective projection
        screen_x = (x * focal_length) / z
        screen_y = (y * focal_length) / z
        prof.end_profile('cam.apply_persp_proj')

        prof.start_profile('cam.apply_asp_ratio')
        # Apply aspect ratio correction
        screen_x = screen_x * self.aspect_ratio
        prof.end_profile('cam.apply_asp_ratio')

        prof.start_profile('cam.convert_to_screen')
        # Convert to screen coordinates
        screen_x = screen_x + half_width
        screen_y = int(self.y_offset - screen_y)
        prof.end_profile('cam.convert_to_screen')

        prof.start_profile('cam.apply_vp')
        # Apply vanishing point adjustment
        screen_x = int(screen_x - (vp_x * vp_scale))
        prof.end_profile('cam.apply_vp')

        return screen_x, screen_y

    def compare_methods(self):
        whole_list = range(self.z_min, self.z_max)
        y_range = self.max_y - self.min_y

        print(f"--- COMPARING 2D and SCALE(z) --- ")
        y = 0
        for z in whole_list:
            _, screen_y_1 = self.to_2d(0, y, z, vp_scale=1)


            # Calculate scale_y for verification
            # scale_y = (self.max_y - self.min_y) * scale

            scale = self.calculate_scale(z)
            ground_y = self.calculate_ground_y(scale, y_range - 10)
            height_y = (y) * scale
            screen_y_2 = ground_y - height_y + self.min_y

            #            y = y + self.vp_y  ??

            # Calculate screen_y_2 using scale
            # adjusted_y = y - (self.vp_factor_y * scale)
            # screen_y_2 = int(self.y_offset - adjusted_y)
            #
            # y = y - self.cam_y
            # scaled_y = scale * y

            # Calculate screen_y_2 to match to_2d result
            # projected_y = (adjusted_y * self.focal_length) / (z - self.cam_z)
            # screen_y_2 = int(self.y_offset - projected_y)


            print(f"z: {z}/ screen_y_1: {screen_y_1} / screen_y_2: {screen_y_2} / scale: {scale:.4f}")

        sys.exit()


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
        _new_cache_size = self._cache_size + 2

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
        # cache_size = (self.max_y - self.min_y) + 10 # Make room for negative Z, or > 1 scale


        z_range = self.z_max - self.z_min
        y_range_orig = self.max_y - self.min_y
        y_range = y_range_orig
        cache_range = y_range+20 * 5

        self._scale_cache = np.array([0.0001] * cache_range)
        self._scale_cache_z = np.array([0] * cache_range, dtype=np.uint16)

        for z in range(0, z_range):
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

            # Adjust y for camera height
            y = 0 # @TODO
            adjusted_y = y - self.cam_y

            # Calculate screen_y_2 using the scale and adjusted y
            # screen_y_2 = self.y_offset - screen_y_2  # Invert and offset

            ground_y = self.calculate_ground_y(scale, y_range) + self.vp_y
            height_y = (y) * scale
            screen_y = ground_y - height_y

            if scale > 1:
                scale = 1
            scale = abs(scale)
            #
            # screen_y = int(scale * (y_range_orig - 1))

            screen_y = screen_y - self.vp_y
            screen_y = int(screen_y) - 2

            if screen_y < 0:
                screen_y = 0
            elif screen_y > self.screen_height:
                screen_y = self.screen_height

            # print(f"Z: {z} / Screen Y: {screen_y} / Scale:{scale} / ")

            """ Store scale as the integer version """
            self._scale_cache[screen_y] = scale
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
        if type(z) is not int:
            raise ArithmeticError("Z must be an integer")

        prof.start_profile('cam.get_scale.cache_search')
        # Find the closest z value in the cache
        idx = self._find_closest(self._scale_cache_z, z)
        prof.end_profile('cam.get_scale.cache_search')

        prof.start_profile('cam.get_scale.dict_lookup_and_sum')

        # Ensure idx is within bounds
        idx = max(0, min(idx, len(self._scale_cache) - 1))

        scale = self._scale_cache[idx]

        y = idx + self.min_y
        prof.end_profile('cam.get_scale.dict_lookup_and_sum')

        return y, scale


    def get_y(self, z, scale=None):
        """ Get the Y coordinate given a Z"""
        if scale:
            my_scale = scale
        else:
            my_scale = self.get_scale(z)

        total_dist = self.screen_height - self.vp_y
        y = (my_scale * total_dist)
        return int(y)

    def normalize(self, scale):
        """ normalize scale to 0-1 range """
        return scale / self.int_scale

    def denormalize(self, scale):
        """ DEnormalize 0-1 scale to 0-integer_factor range """
        return scale * self.int_scale


    def calculate_scale(self, z):
        if z > self.z_max:
            return 0.0001
        elif z == 0:
            z = 0.0001

        relative_z = z - self.cam_z
        if relative_z == 0:
            relative_z = self.near_plus_epsilon
        scale = self.focal_length_aspect * (1.0 / relative_z)

        # Optionally, you can invert the scale for negative z values
        # if relative_z < 0:
        #     scale = -scale

        return scale

    def calculate_ground_y(self, scale, y_range):
        y = y_range * scale
        return y

    def _find_closest(self, arr, z):
        """
        Find the index of the closest value to z in a sparse array arr.
        Optimized for a fixed range of 1500-0 in descending order.

        Args:
        arr (list): A list of numbers in descending order from 1500 to 0, potentially sparse
        z (float): The target value to find the closest match for

        Returns:
        int: The index of the closest value to z in arr
        """
        if not arr:
            return None
        if z >= arr[0]:
            return 0
        if z <= arr[-1]:
            return len(arr) - 1

        # Binary search to find the insertion point
        left, right = 0, len(arr) - 1
        while left <= right:
            mid = (left + right) // 2
            if arr[mid] == z:
                return mid
            elif arr[mid] > z:
                left = mid + 1
            else:
                right = mid - 1

        # At this point, 'right' is the index of the first element > z
        # and 'left' is the index of the first element < z

        # Check which adjacent value is closer
        if left >= len(arr):
            return right
        if right < 0:
            return left
        if abs(arr[right] - z) <= abs(arr[left] - z):
            return right
        else:
            return left