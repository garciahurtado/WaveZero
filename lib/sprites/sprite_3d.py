import framebuf
from sprites.spritesheet import Spritesheet
from profiler import Profiler as prof, timed


class Sprite3D(Spritesheet):
    """ A Sprite which has an x,y,z location in 3D space, and that can be rendered in a 2D screen with the help
    of a camera."""

    z: int = 0
    max_z: int = 4000
    min_z: int = -40
    draw_x: int = 0
    draw_y: int = 0
    lane_num: int = None
    lane_width: int = 0

    half_scale_one_dist = 0

    def __init__(self, z=0, camera=None, lane_width=None, horiz_z=0, *args, **kwargs):

        self.lane_width = lane_width
        self.z = z
        self.camera = camera
        self.draw_x = 0
        self.draw_y = 0
        self.lane_num = 0
        self.horiz_z = horiz_z

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
        if not self.visible or not self.image:
            return False

        return super().show(display, self.draw_x, self.draw_y)

    def update(self, elapsed):
        if not self.active:
            return False

        super().update()

        if self.speed:
            self.z = self.z + (self.speed * elapsed)

        if self.z > self.max_z or self.z < self.min_z:
            self.active = False
            self.visible = False
            return False

        draw_x, draw_y = self.pos()
        self.draw_x, self.draw_y = int(draw_x), int(draw_y)

    def pos(self):
        """Returns the 2D coordinates of the object, calculated from the internal x,y (if 2D) or x,y,z
        (if 3D with perspective camera)
        """
        camera = self.camera

        if camera:
            int_x: int = int(self.x)
            # int_y: int = int(self.y + self.frame_height) # only needed because the display draws from top to bottom
            int_y: int = int(self.y)
            int_z: int = int(self.z)

            return camera.to_2d(int_x, int_y, int_z)
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

        lane_width = self.lane_width

        lane = lane_num - 2 # [-2,-1,0,1,2]
        new_x = (lane * (lane_width)) - (self.frame_width/2)
        self.x = round(new_x)

