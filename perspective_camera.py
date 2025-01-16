import framebuf
import math

import micropython
import sys

from profiler import Profiler as prof

class PerspectiveCamera():
    def __init__(self, display: framebuf.FrameBuffer, pos_x: int = 0, pos_y: int = 0, pos_z: int = 0, vp_x: int = 0,
                 vp_y: int = 0, min_y:int = 0, max_y:int = 0, fov=90.0) -> object:

        # Use display dimensions
        self.screen_width = display.width
        self.screen_height = display.height
        self.display = display

        # Calculate aspect ratio
        self.aspect_ratio = self.screen_width / self.screen_height

        # Near / far clipping planes
        self.near = -20
        self.far = 1500  # past this point all sprites are considered to be in the horizon line

        self.cam_x = pos_x
        self.cam_y = pos_y
        self.cam_z = pos_z

        self.min_y = min_y
        self.max_y = max_y

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
        self.max_vp_scale = 3.7 # Tweak amount of parallax effect (so that )close objects move faster when the VP moves

        self._y_factor_cache = {}

        self._cache_index = 0
        self._cache_full = False
        self._scale_cache_z = []
        self._scale_cache_y = []
        self._scale_cache_scale = []
        self.min_scale = 0.0001

        """ Use an unbalanced list: more dense towards the camera, less dense away from the camera """
        self._cache_steps = [
            [0, 99, 1],  # z=(0/100), Y every 1 z
            [100, 390, 10],  # z=(100/400), Y every 10 zs
            [400, 1400, 100],  # z=(400/1500), Y every 100 zs
        ]

        self.min_z = self.near
        self.max_z = self.far
        self.near_plus_epsilon = self.near + 0.000001

        self._precalculate_scale_cache()
        # self.to_2d_test(self.min_z, self.max_z)


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
        cam_x = self.cam_x
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
        if z == 0:
            z = 0.0001

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
        whole_list = range(self.min_z, self.max_z)
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
        """ min_y and max_y are from 2D space """

        if self.min_y >= self.max_y:
            raise ArithmeticError("Min Y cannot be higher than Max Y")

        y_range = self.max_y - self.min_y

        self._scale_cache = []
        self._scale_cache_z = []
        self._scale_cache_y = []

        for start, end, step in self._cache_steps:
            for z in range(start, end + step, step):
                """ Takes a Z value from the 0/max_z range and converts it to a scale, which converts to a Y coord, and gets added as the index
                of a new entry into the cache array"""

                if z <= self.min_z:
                    scale = 1
                elif z >= self.max_z:
                    scale = self.min_scale
                else:
                    scale = self.calculate_scale(z)

                if scale < self.min_scale:
                    scale = self.min_scale

                # scale = scale * self.aspect_ratio

                # Adjust Y for camera height
                ground_y = self.calculate_ground_y(scale, y_range - 1)
                screen_y = ground_y

                if scale > 1:
                    scale = 1
                scale = abs(scale)

                # screen_y = screen_y - self.vp_y
                screen_y = int(screen_y)

                if screen_y > self.max_y:
                    scale = 1

                # if screen_y < 0:
                #     screen_y = 0
                # elif screen_y > self.screen_height:
                #     screen_y = self.screen_height

                self._scale_cache.append(scale)
                self._scale_cache_z.append(int(z))
                self._scale_cache_y.append(int(screen_y))

        # Add a last entry for the furthest objects
        # self._scale_cache.append(0.001)
        # self._scale_cache_z.append(self.far)
        # self._scale_cache_y.append(0)

    def get_scale(self, z):
        """ For a given Z coordinate, return the 2D Y coordinate, as well as the scale at which the sprite
        should be drawn. """
        if type(z) is not int:
            raise ArithmeticError("Z must be an integer")

        z = z + abs(self.near) # moves the point of 1-scale further away from the camera

        prof.start_profile('cam.get_scale.cache_search')
        # Find the closest z value in the cache
        idx = self._find_closest(self._scale_cache_z, z)
        prof.end_profile('cam.get_scale.cache_search')

        prof.start_profile('cam.get_scale.dict_lookup_and_sum')

        # Ensure idx is within bounds
        idx = max(0, min(idx, len(self._scale_cache_z)-1))
        y = self._scale_cache_y[idx]

        y = y + self.min_y # This is how we end up with the range "vp Y - screen height"

        scale = self._scale_cache[idx]

        prof.end_profile('cam.get_scale.dict_lookup_and_sum')

        return y, scale


    def calculate_scale(self, z):
        if z > self.max_z:
            return 0.0001

        relative_z = z - self.cam_z
        if relative_z == 0:
            relative_z = 0.0001
        scale = self.focal_length_aspect * (1.0 / relative_z)

        return scale

    def calculate_ground_y(self, scale, y_range):
        y = y_range * scale
        return y

    def _find_closest(self, arr, z):
        """
        Find the index of the closest value to z in a sparse array arr.
        Optimized for a fixed range of 0-1500 in asc order.

        Args:
        arr (list): A list of numbers in descending order from 1500 to 0, potentially sparse
        z (float): The target value to find the closest match for

        Returns:
        int: The index of the closest value to z in arr
        """

        starts = []
        stops = []
        steps = []

        for _start, _stop, _step in self._cache_steps:
            starts.append(_start)
            stops.append(_stop)
            steps.append(_step)

        start1 = starts[1]
        start2 = starts[2]
        start3 = ((stops[2] - starts[2] + steps[2]) / steps[2]) + start2

        stop1 = stops[1] + steps[1]
        stop2 = stops[2] + steps[2]

        step1 = steps[1]
        step2 = steps[2]

        # print(f"STARTS: {start1} / {start2} / {start3}")

        if z < 0:
            idx = 0
        elif z < start1:
            """ z < 100 : First 100 indices """
            idx = z
            # print(f"({idx} IDX) LIKE Z: [{z}] / start: 0")
        elif z < stop1:
            """ z < 400 :  100-130 indices """
            range = z - start1
            idx = int(range / steps[1]) + start1
            # print(f"({idx} IDX) [{start1} / {stop1}] : Z: {z} / start1: {start1}")
        elif z <= stop2 + step2:
            """ z < 1500 : 130-141 indices """
            range = z - start2
            idx = int( (range / steps[2]) + (start1 + ((start2 - start1) / step1)) )
            # print(f"({idx} IDX) [{stop1} / {stop2}] : Z: {z} / start2: {start2}")
        else:
            """ z > 1500 """
            idx = len(arr) - 1
            # print(f"({idx} IDX) MAX (len arr:{len(arr)}) : Z: {z} / start: {start3}")

        # print(f"IDX: {idx}")
        return idx

    def to_2d_test(self, start_z, end_z, x=0, y=0, num_frames=20):
        """ Take a range of z values, run them through to2d() and show the results, in order to provide a reference
        for other methods of calculation."""
        # print("TO_2D PROJECTION")
        # print("----------------")

        from sprites2.sprite_manager import SpriteManager as mgr
        my_mgr = mgr(self.display, 1)
        # #
        # print("----- to_2d Method ----")
        # print("Z\t Y\t SCALE\t FR IDX:")

        prof.start_profile('cam.to_2d_test.classic')

        for z in range(0, end_z + 1):
            screen_x, screen_y = self.to_2d(x, y, z)
            scale = self.calculate_scale(z)
            idx = my_mgr.get_frame_idx(scale, num_frames)

            print(f"{z}\t{screen_y}\t{scale:.04f}\t{idx}")
        prof.end_profile('cam.to_2d_test.classic')
        #
        # print("----- CACHE Method ----")
        # print("Z\t Y\t SCALE\t FR IDX:")

        prof.start_profile('cam.to_2d_test.cache')

        for z in range(0, end_z + 1):
            screen_y, scale = self.get_scale(z)
            screen_x = x * scale
            screen_x -= self.vp_x * self.max_vp_scale * scale * 1.2  # magic number
            screen_x += self.half_width

            idx = my_mgr.get_frame_idx(scale, num_frames)

            # print(f"{z}\t{screen_y}\t{scale:.04f}\t{idx}")

        prof.end_profile('cam.to_2d_test.cache')

