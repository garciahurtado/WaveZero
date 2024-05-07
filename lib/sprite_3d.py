import math

import framebuf
from spritesheet import Spritesheet

class Sprite3D(Spritesheet):
    """ A Sprite which has an x,y,z location in 3D space, and that can be rendered in a 2D screen with the help
    of a camera."""

    z: int = 0
    horiz_z = 2000
    draw_x: int = 0
    draw_y: int = 0
    lane_num = None
    lane_width = 0

    half_scale_one_dist = 0

    def __init__(self, z=0, camera=None, lane_width=None, *args, **kwargs):

        self.lane_width = lane_width
        self.z = z
        self.camera = camera
        super().__init__(*args, **kwargs)

    def set_camera(self, camera):
        self.camera = camera
        scale_adj = 8 # Increase this value to see bigger sprites when closer to the screen
        self.half_scale_one_dist = abs(self.camera.pos['z']-scale_adj) / 2

    def get_draw_xy(self, display: framebuf.FrameBuffer):
        """ Overrides parent """
        x, y = self.draw_x, self.draw_y
        return x, y

    def show(self, display: framebuf.FrameBuffer):
        if self.z > self.horiz_z:
            return False

        return super().show(display, self.draw_x, self.draw_y)

    def update(self, ellapsed):
        if not self.active:
            return False

        if self.speed:
            self.z = self.z + (self.speed * ellapsed)

        draw_x, draw_y = self.pos()
        self.draw_x, self.draw_y = draw_x, draw_y

        self.update_frame()

    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer):
        # Overrides parent for some performance hacks
        # offset: int = 0
        # if 3 > self.image.height > 2:
        #     offset = int(self.image.height / 2)
        #     display.fill_rect(x + offset, y + offset, self.image.height, self.image.width, self.dot_color)
        #     return True
        # if self.image.height <= 2:
        #     offset = int(self.image.height / 2)
        #     display.pixel(x + offset, y + offset, self.dot_color)
        #     return True

        return super().do_blit(x, y, display)

    def pos(self):
        """Returns the 2D coordinates of the object, calculated from the internal x,y (if 2D) or x,y,z
        (if 3D with perspective camera)
        """
        x_offset = 0
        camera = self.camera

        if camera:
            x_offset = self.x - camera.pos["x"]
            x, y = camera.to_2d(self.x, self.y + self.frame_height, self.z)

            return x, y
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
        if lane_num == self.lane_num:
            return False
        lane_width = self.lane_width # perspective adjust

        self.lane_num = lane_num
        lane = lane_num - 2 # [-2,-1,0,1,2]
        new_x = (lane * (lane_width)) - (self.frame_width/2)
        self.x = round(new_x)

