import gc
import utime
from micropython import const
import struct
from ulab import numpy as np

import color_util as colors
from framebuffer_palette import FramebufferPalette

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

    # horizon_palette = [
    #     0x0118,
    #     0x0130,
    #     0x2128,
    #     0x2140,
    #     0xc939,
    #     0xc939,
    # ]

    # horizon_palette = [
    #     0xc939,
    #     0xc939,
    #     0xc939,
    #     0xc939,
    #     0xc939,
    #     0xc939,
    #     0xc939,
    # ]


    #
    #

    #
    horizon_palette = [0x000000,
                       0x1D0308,
                       0x290408,
                       0x37030A,
                       0x44050A,
                       0x51040B,
                       0x5F050C,]



    vert_palette = [0x610070,
                    0x5f0083,
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
    bright_lines = [7, 12]
    bright_color = None
    display_width = const(96)
    display_height = const(64)

    def __init__(self, camera, display, lane_width=None):

        self.width = camera.screen_width
        self.height = camera.screen_height
        self.last_horiz_line_ts = 0
        num_horiz_lines = 40
        self.num_vert_lines = 20
        self.vert_points = []
        self.display = display

        self.camera = camera
        self.horiz_y = camera.vp['y']  # 16
        print(f"Horizon Y: {self.horiz_y}")

        self.far_z_vert = 1000
        self.near_z = 1

        self.lane_width = lane_width  # width in 3D space
        self.lane_height = lane_width * 2  # length of a grid square along the Z axis

        # For vertical road lines only
        self.max_spacing = self.lane_width

        self.field_width = 96
        self.vert_line_start_x = -round((self.field_width - self.width) / 2)
        self.last_horiz_line_ts = round(utime.ticks_ms())

        self.x_start_top = 0
        self.x_start_bottom = 0

        self.speed = 0
        self.ground_height = camera.screen_height - self.horiz_y
        self.init_palettes()

        self.horiz_lines_data = [None] * num_horiz_lines

        print(f"Creating {num_horiz_lines} hlines")
        self.check_mem()

        self.create_horiz_lines(num_horiz_lines)
        gc.collect()

        self.create_vert_points()

    def init_palettes(self):
        self.num_horiz_colors = len(self.horiz_palette)
        new_palette = []

        for i, hex_color in enumerate(self.horiz_palette):
            new_col = list(colors.hex_to_rgb(hex_color))
            new_palette.append(new_col)

        palette = FramebufferPalette(new_palette)
        #
        # for i, hex_color in enumerate(self.horiz_palette):
        #     new_color = colors.hex_to_rgb(hex_color)
        #     new_color = [new_color[0], new_color[1], new_color[2]]
        #     palette.set_rgb(i, new_color)

        self.horiz_palette = palette

        print(f"Adding horizon palette")
        self.check_mem()

        new_palette = []

        for i, hex_color in enumerate(self.horizon_palette):
            new_palette.append(colors.hex_to_rgb(hex_color))

        for color in new_palette:
            print(color)

        self.horizon_palette = FramebufferPalette(new_palette)


        """ set up the palettes for line colors """

        red = [97, 0, 112]
        # mag = [255, 0, 50]
        cyan = [0, 255, 255]
        # cyan = MIDDLE_BLUE
        # blue = [20, 80, 255]
        horiz_far = [82, 0, 20]
        horiz_near = [0, 238, 255]

        print(f"Adding horiz colors palette")
        self.check_mem()


        """ Make vertical palette """

        num_vert_colors = self.num_vert_lines // 2
        print(f"Making a vertical palette of {num_vert_colors}")
        # color1 = red
        # color2 = colors.hex_to_rgb(MIDDLE_CYAN)
        # self.vert_palette = colors.make_gradient(color1, color2, num_vert_colors)
        #
        # # Color last 3 lines cyan & blue (x2: 6 lines total)
        # self.vert_palette[num_vert_colors-3] = MIDDLE_CYAN
        # self.vert_palette[num_vert_colors-2] = MIDDLE_BLUE
        # self.vert_palette[num_vert_colors-1] = MIDDLE_BLUE
        #
        #
        # for i in range(num_vert_colors):
        #     hex_color = self.vert_palette[i]
        #     print(f"{hex_color:06x}")

            # new_palette.append(colors.hex_to_rgb(hex_color))

        new_palette = []
        for i, hex_color in enumerate(self.vert_palette):
            new_palette.append(colors.hex_to_rgb(hex_color))

        vert_palette = FramebufferPalette(new_palette)
        vert_palette_2 = vert_palette.mirror()

        # Concatenate the two mirrored palettes into one
        final_palette = vert_palette + vert_palette_2
        self.vert_palette = final_palette

        print("After vertical palette")
        self.check_mem()

        self.bright_color = colors.hex_to_565(0x00ffff)

        print("After both palettes combined")
        self.check_mem()


    def show(self):
        self.update_horiz_lines()
        self.draw_horizon()
        self.update_vert_lines()
        self.last_tick = utime.ticks_ms()


    def create_horiz_lines(self, num_lines):
        for i in range(num_lines):
            self.horiz_lines_data[i] = {'z': (i * self.lane_height)}

        self.far_z_horiz = (num_lines-2) * self.lane_height


    def create_vert_points(self):
        """ Calculates the x,y start and end points for the vertical lines of the road grid """

        num_vert_lines = self.num_vert_lines

        lane_width_far, _ = self.camera.to_2d(self.lane_width, 0, self.far_z_vert // 2) # used to measure the lane width in screen space
        lane_width_far = lane_width_far - self.camera.half_width

        lane_width_near, _ = self.camera.to_2d(self.lane_width, 0, self.near_z) # used to measure the lane width in screen space
        lane_width_near = int(lane_width_near - self.camera.half_width)

        self.x_start_top = - ((num_vert_lines) * lane_width_far // 2) + (lane_width_far // 2)
        self.x_start_bottom = - ((num_vert_lines) * lane_width_near // 2) + (lane_width_near // 2)

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

    def update_horiz_lines(self):
        # self.check_mem()
        # print(".")

        horiz_y_adj = 1
        last_y: int = 0
        far_z = 0 # Keep track of the furthest line, to see if we need new ones
        delete_lines = []
        ellapsed_ticks = utime.ticks_ms() - self.last_tick

        for i, my_line in enumerate(self.horiz_lines_data):
            if not my_line['z']:
                my_line['z'] = 0

            my_line['z'] = my_line['z'] - (self.speed * ellapsed_ticks / 1000)

            if my_line['z'] > far_z:
                far_z = my_line['z']

            _, y = self.camera.to_2d(0, 0, my_line['z'])

            my_line['y'] = round(y)

            # Reached the bottom of the screen, this line is done
            if my_line['y'] > self.display_height:
                del self.horiz_lines_data[i]
                continue

            # Avoid writing a line on the same Y coordinate as the last one we draw
            if my_line['y'] == last_y:
                continue

            last_y = my_line['y']

            color_idx = self.horiz_palette.pick_from_value(my_line['y'], self.height, self.horiz_y)

            num_colors = len(self.horiz_palette)
            if color_idx >= num_colors:
                color_idx = num_colors - 1

            rgb565 = self.horiz_palette.get_bytes(color_idx)
            rgb = self.horiz_palette.get_rgb(color_idx)

            # print(f"RGB: {rgb[0]}, {rgb[1]}, {rgb[2]}")

            self.display.hline(0, my_line['y'], self.width, rgb565)
            # self.display.rect(0, my_line['y'], self.width - 1, 1, rgb565)

        # print("RGBEND----------RGBEND")


        """ Remove out of bounds lines """
        for line in delete_lines:
            self.horiz_lines_data.remove(line)

        dist_to_horiz = self.far_z_horiz - far_z

        if dist_to_horiz > self.lane_height:
            """ Time to spawn a new line in the horizon"""
            new_line = {'z': far_z + self.lane_height}
            self.horiz_lines_data.insert(0, new_line)

    def update_vert_lines(self):
        # Calculate the reference points just once
        start_x_far, _ = self.camera.to_2d(0, 0, self.far_z_vert)
        start_x_near, _ = self.camera.to_2d(0, 0, self.near_z)
        bright_lines = self.bright_lines
        bright_color = self.bright_color

        top_points, bottom_points = self.vert_points[0], self.vert_points[1]

        # print("COLORS:")
        # for color in self.vert_palette.palette:
        #     print(f"{colors.rgb565_to_rgb(color)}")
        index = 0

        horiz_y_offset = 0  # Manual adjustment for the start.y of the vertical lines
        start_y = self.horiz_y + horiz_y_offset
        end_y = self.height

        for start, end in zip(top_points, bottom_points):
            # start = top_points[index]
            # end = bottom_points[index]
            start_x = int(start + start_x_far)
            end_x = int(end + start_x_near)

            # color = self.vert_palette.get_bytes(index)
            # color = self.vert_palette[index]
            color = self.vert_palette.get_bytes(index)

            # color = 0xFF
            # rgb = colors.rgb_to_hex(rgb)
            # color = colors.rgb_to_565(color)
            # print(f"Color {rgb}")
            # print(f"Color {colors.rgb565_to_rgb(rgb)}")
            # print(f"Coords: {start_x},{start_y},{end_x},{end_y}")
            self.display.line(start_x, start_y, end_x, end_y, color)

            if index in bright_lines:
                if index == bright_lines[0]:
                    self.display.line(start_x, start_y, end_x-1, end_y, bright_color)
                else:
                    self.display.line(start_x, start_y, end_x+1, end_y, bright_color)

            index += 1

    def draw_horizon(self):
        """Draw some static horizontal lines to cover up the seam between vertical and horiz road lines"""
        color: int = 0

        for i in range(0, len(self.horizon_palette) - 2):
            color = self.horizon_palette.get_bytes(i)
            start_y = self.horiz_y - 2 + (i*2)
            self.display.hline(0, start_y, self.display_width, color)
            self.display.hline(0, start_y + 1, self.display_width, BLACK)

    def check_mem(self):
        print(f"Free memory:  {gc.mem_free():,} bytes")
