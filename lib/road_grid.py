import gc
import utime
from micropython import const
import struct
from ulab import numpy as np

import color_util as colors
from framebuffer_palette import FramebufferPalette
from profiler import Profiler as prof, timed

MIDDLE_CYAN = 0x217eff
MIDDLE_BLUE = 0x008097
BLACK = 0x0000

class RoadGrid():
    horiz_palette = [
        0x000000,
        0x520014,
        0x500418,
        0x4C0E22,
        0x49192C,
        0x452337,
        0x422D41,
        0x3E384B,
        0x3B4255,
        0x374D60,
        0x33576A,
        0x306274,
        0x2C6C7E,
        0x297689,
        0x258093,
        0x228B9D,
        0x1E95A7,
        0x17AABC,
        0x13B5C6,
        0x10BFD0,
        0x0CC9DB,
        0x09D3E5,
        0x05DEEF,
        0x01E8F9
    ]

    horizon_palette = [0x000000,
                       0x1D0308,
                       0x290408,
                       0x37030A,
                       0x44050A,
                       0x51040B,
                       0x5F050C,]
    horiz_palette_len = len(horizon_palette) - 2

    vert_palette = [
                    # 0x610070,
                    # 0x5f0083,
                    0x570097,
                    0x4a00aa,
                    0x3800be,
                    0x1f00d1,
                    0x0200e5,
                    0x217eff,
                    0x008097,
                    0x008097]

    last_tick = 0

    # reinforce the edges of the road
    bright_lines = [5, 10]
    bright_color = None
    display_width = const(96)
    display_height = const(64)
    far_z = 0

    def __init__(self, camera, display, lane_width=None):

        self.width = camera.screen_width
        self.height = camera.screen_height
        self.num_horiz_lines = 20
        self.num_vert_lines = 16
        self.vert_points = []
        self.display = display

        self.camera = camera
        self.horiz_y = camera.vp['y']
        print(f"Horizon Y: {self.horiz_y}")

        self.far_z_vert = 2000
        self.near_z = 1
        self.min_z = -10

        self.lane_width = lane_width  # width in 3D space
        self.lane_height = lane_width * 2  # length of a grid square along the Z axis

        # For vertical road lines only
        self.max_spacing = self.lane_width

        self.field_width = 96

        self.x_start_top = 0
        self.x_start_bottom = 0

        self.speed = 0
        self.ground_height = camera.screen_height - self.horiz_y
        self.init_palettes()

        self.horiz_lines_data = []

        print(f"Creating {self.num_horiz_lines} hlines")
        self.check_mem()

        self.create_horiz_lines(self.num_horiz_lines)
        gc.collect()

        self.create_vert_points()

    def init_palettes(self):
        self.num_horiz_colors = len(self.horiz_palette)
        new_palette = []

        for i, hex_color in enumerate(self.horiz_palette):
            new_col = list(colors.hex_to_rgb(hex_color))
            new_palette.append(new_col)

        tmp_palette = FramebufferPalette(new_palette)

        color_list = []
        """ Make an look up table to quickly reference colors by Y coordinate"""
        for color_idx in range(len(tmp_palette)):
            # color_idx = self.horiz_palette.pick_from_value(i, total_height, 0)
            color = tmp_palette.get_bytes(color_idx)
            color_list.append(color)

        self.horiz_palette = color_list


        """ Make static horizon palette """
        self.check_mem()
        tmp_palette = FramebufferPalette(len(self.horizon_palette))
        color_list = []

        for i, hex_color in enumerate(self.horizon_palette):
            new_col = list(colors.hex_to_rgb(hex_color))
            tmp_palette.set_rgb(i, new_col)

        for color_idx in range(len(tmp_palette)):
            new_col = tmp_palette.get_bytes(color_idx)
            color_list.append(new_col)

        self.horizon_palette = color_list

        """ Make vertical palette """
        new_palette = []
        for i, hex_color in enumerate(self.vert_palette):
            new_palette.append(colors.hex_to_rgb(hex_color))

        vert_palette = FramebufferPalette(new_palette)
        vert_palette_2 = vert_palette.mirror()

        # Concatenate the two mirrored palettes into one
        final_palette = vert_palette + vert_palette_2
        tmp_palette = []

        for idx in range(final_palette.num_colors):
            tmp_palette.append(final_palette.get_bytes(idx, False))

        self.bright_color = colors.hex_to_565(0x00ffff, final_palette.color_mode)

        # Simplify palette to an array of rgb565 colors, for performance
        self.vert_palette = tmp_palette

        print("After vertical palette")
        self.check_mem()

        print("After both palettes combined")
        self.check_mem()


    def show(self):
        self.show_horiz_lines()
        self.show_vert_lines()
        self.draw_horizon()

        self.last_tick = utime.ticks_ms()


    def create_horiz_lines(self, num_lines):
        start_z = -50
        for i in range(num_lines - 1, 0, -1):
            self.horiz_lines_data.append( {'z': (i * self.lane_height) - start_z} )

        self.far_z_horiz = (num_lines) * self.lane_height


    def create_vert_points(self):
        """ Calculates the x,y start and end points for the vertical lines of the road grid """

        num_vert_lines = self.num_vert_lines

        lane_width_far, _ = self.camera.to_2d(self.lane_width, 0, self.far_z_vert // 2)  # used to measure the lane width in screen space
        lane_width_far = lane_width_far - self.camera.half_width + 1

        lane_width_near, _ = self.camera.to_2d(self.lane_width, 0, self.near_z) # used to measure the lane width in screen space
        lane_width_near = lane_width_near - self.camera.half_width

        half_top = (num_vert_lines * lane_width_far) // 2
        half_bottom = (num_vert_lines * lane_width_near) // 2

        self.x_start_top = int(-half_top + (lane_width_far/2))
        self.x_start_bottom = int(-half_bottom + (lane_width_near/2))

        horiz_y_offset = 4 # Manual adjustment for the start.y of the vertical lines
        self.horiz_y = self.horiz_y + horiz_y_offset

        # points_start = np.empty([num_vert_lines], dtype=np.int8)
        points_start = []

        for i in range(num_vert_lines):
            x = (i * lane_width_far) + self.x_start_top
            points_start.append(int(x)) # we only need the x coordinate

        points_end = []
        # points_end = points_end.reshape((-1, 2))

        for j in range(num_vert_lines):
            x = (j * lane_width_near) + self.x_start_bottom
            points_end.append(int(x))

        self.vert_points = [points_start, points_end]

        """ Trick the camera during update()"""
        # self.far_z_vert = 10000

    #@timed
    def update_horiz_lines(self, elapsed):
        self.far_z = 0 # Keep track of the furthest line, to see if we need new ones
        delete_lines = []

        for my_line in self.horiz_lines_data:
            if not my_line['z']:
                my_line['z'] = 0

            my_line['z'] = my_line['z'] + (self.speed * (elapsed / 1000))

            if my_line['z'] > self.far_z:
                self.far_z = my_line['z']
            elif my_line['z'] < self.min_z:
                delete_lines.append(my_line)
                continue


        """ Remove out of bounds lines """
        for line in delete_lines:
            self.horiz_lines_data.remove(line)

    #@timed
    def show_horiz_lines(self):
        last_y: int = 0

        for my_line in self.horiz_lines_data:
            y = self.camera.to_2d_y(0, 0, my_line['z'])
            my_line['y'] = int(y)

            # Avoid writing a line on the same Y coordinate as the last one we drew
            if my_line['y'] == last_y:
                continue

            last_y = my_line['y']

            """ Pick the color from the palette according to the distance"""
            rel_y = my_line['y'] - self.horiz_y + 1
            if rel_y >= len(self.horiz_palette):
                rel_y = len(self.horiz_palette) - 1
            elif rel_y < 0:
                rel_y = 0

            rgb565 = self.horiz_palette[rel_y]

            self.display.hline(0, my_line['y'], self.width, rgb565)


        dist_to_horiz = self.far_z_horiz - self.far_z

        if (dist_to_horiz > self.lane_height) and len(self.horiz_lines_data) < self.num_horiz_lines:
            """ Time to spawn a new line in the horizon"""
            new_line = {'z': self.far_z + self.lane_height}
            self.horiz_lines_data.append(new_line)


    #@timed
    def show_vert_lines(self):
        # Calculate the reference points just once
        start_x_far, _ = self.camera.to_2d(0, 0, self.far_z_vert)
        start_x_near, _ = self.camera.to_2d(0, 0, self.near_z)
        bright_lines = self.bright_lines
        bright_color = self.bright_color

        top_points, bottom_points = self.vert_points[0], self.vert_points[1]

        index = 0

        horiz_y_offset = 0  # Manual adjustment for the start.y of the vertical lines
        start_y = self.horiz_y + horiz_y_offset
        end_y = self.height

        for start, end in zip(top_points, bottom_points):
            start_x = int(start + start_x_far)
            end_x = int(end + start_x_near)

            color = self.vert_palette[index]
            self.display.line(start_x, start_y, end_x, end_y, color)

            if index in bright_lines:
                if index == bright_lines[0]:
                    self.display.line(start_x, start_y, end_x+1, end_y, bright_color)
                else:
                    self.display.line(start_x, start_y, end_x-1, end_y, bright_color)

            index += 1

    #@timed
    def draw_horizon(self):
        """Draw some static horizontal lines to cover up the seam between vertical and horiz road lines"""
        horizon_offset = -8

        for i in range(0, self.horiz_palette_len):
            color = self.horizon_palette[i]
            start_y = self.horiz_y + horizon_offset + (i*2)
            self.display.hline(0, start_y, self.display_width, color)
            self.display.hline(0, start_y + 1, self.display_width, BLACK)

    def check_mem(self):
        print(f"Free memory:  {gc.mem_free():,} bytes")
