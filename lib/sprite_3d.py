from sprite import Sprite
import framebuf

class Sprite3D(Sprite):
    """ A Sprite which has an x,y,z location in 3D space, and that can be rendered in a 2D screen with the help
    of a camera."""

    z: int = 0
    horiz_z = 1500
    draw_x: int = 0
    draw_y: int = 0
    lane_num = None
    lane_width = 0

    def __init__(self, z=0, camera=None, lane_width=0, *args, **kwargs):
        self.lane_width = lane_width
        self.z = z
        self.camera = camera
        super().__init__(*args, **kwargs)


    def set_camera(self, camera):
        self.camera = camera
        scale_adj = 10 # Increase this value to see bigger sprites when closer to the screen
        self.half_scale_one_dist = abs(self.camera.pos['z']-scale_adj) / 2

    def get_draw_xy(self, display: framebuf.FrameBuffer):
        """ Overrides parent """
        x, y = self.draw_x, self.draw_y
        return x, y

    def show(self, display: framebuf.FrameBuffer):
        if self.z > self.horiz_z:
            return False

        return super().show(display)

    def update(self):
        if not self.active:
            return False

        if self.speed:
            self.z = self.z + self.speed

        draw_x, draw_y = self.pos()
        self.draw_x, self.draw_y = draw_x, draw_y

    def pos(self):
        """Returns the 2D coordinates of the object, calculated from the internal x,y (if 2D) or x,y,z
        (if 3D with perspective camera)
        """
        if self.camera:
            x_offset = self.x - self.camera.pos["x"]
            x, y = self.camera.to_2d(x_offset, self.y + self.height, self.z)

            #x = int(x - (self.width_2d / 2))  # Draw the object so that it is horizontally centered

            return int(x), int(y)
        else:
            return self.x, self.y



    def get_lane(self):
        """
        Returns the lane number which this sprite occupies in 3D space:
        [-2,-1,0,1,2]
        """
        return self.lane_num
        # if self.x == 0:
        #     lane = 0
        # else:
        #     x = self.x + self.half_field
        #     lane = int(x / self.lane_width)
        #
        # return lane

    def set_lane(self, lane_num):
        self.lane_num = lane_num
        lane = lane_num - 2 # [-2,-1,0,1,2]
        res = (lane * self.lane_width) - (self.frame_width/2)
        self.x = int(res)

    def _clone(self):
        copy = Sprite()
        copy.x = self.x
        copy.y = self.y

        copy.pixels = self.pixels
        copy.palette = self.palette
        copy.width = self.width
        copy.height = self.height

        copy.has_alpha = self.has_alpha
        copy.alpha_color = self.alpha_color
        copy.alpha_index = self.alpha_index

        return copy

