import framebuf
import math

class PerspectiveCamera():
    def __init__(self, display: framebuf.FrameBuffer, pos_x: float = 0, pos_y: float = 0, pos_z: float = 0, vp_x: float = 0, vp_y: float = 0,
                 focal_length: float = 100) -> object:

        self.screen_width = display.width
        self.screen_height = display.height

        self.half_width = self.screen_width / 2
        self.half_height = self.screen_height / 2

        self.pos = {"x":pos_x, "y":pos_y, "z":pos_z} # location of camera in 3D space
        self.vp = {"x": vp_x, "y":vp_y} # vanishing point
        self.focal_length = focal_length # Distance from the camera to the projection plane in pixels

        self.focal_length_x, self.focal_length_y = self.calculate_fov(focal_length)

        self.horiz_z = 5000 # past this point all sprites are considered to be in the horizon line
        self.min_z = pos_z

        """In order to simulate yaw of the camera, we will shift objects horizontally between a max and a min"""
        self.min_yaw = 0
        self.max_yaw = -100

    def calculate_fov(self, focal_length):
        # Calculate the horizontal and vertical FOV
        h_fov = 2 * math.atan(self.screen_width / (2 * focal_length))
        v_fov = 2 * math.atan(self.screen_height / (2 * focal_length))

        # Convert to degrees
        h_fov_deg = math.degrees(h_fov)
        v_fov_deg = math.degrees(v_fov)

        return h_fov_deg, v_fov_deg


    def to_2d(self, x, y, z):
        """Based on:
        https://forum.gamemaker.io/index.php?threads/basic-pseudo-3d-in-gamemaker.105242/"""
        z = z - self.pos['z']
        if z == 0:
            z = 0.0001 # avoid division by zero

        camera_y = self.pos['y']
        screen_x = ((x * self.focal_length_x) / (z)) + self.half_width
        screen_y = (((y - camera_y) * self.focal_length_y) / (z)) + self.half_height

        screen_y = self.screen_height - screen_y - self.vp['y']
        screen_x = screen_x - self.pos["x"]

        y_factor = (screen_y - self.vp['y']) / (self.screen_height - self.vp['y'])
        screen_x = screen_x - (self.vp['x'] * y_factor)

        return round(screen_x), round(screen_y)

