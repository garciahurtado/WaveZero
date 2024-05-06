import gc
import math
import utime
from ulab import numpy as np

import color_util as colors
from framebuffer_palette import FramebufferPalette
from ssd1331_16bit import SSD1331

MIDDLE_CYAN = colors.hex_to_rgb(0x217eff)
MIDDLE_CYAN2 = colors.hex_to_rgb(0xff7e21)
MIDDLE_BLUE = colors.hex_to_rgb(0x00697F)
BLACK = colors.rgb_to_565([0,0,0])

class RoadGrid():
    horiz_palette = [0x000000,
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
                    0x01E8F9]

    horizon_palette = [0x000000,
                        0x5F050C,
                        0x51040B,
                        0x44050A,
                        0x37030A,
                        0x290408,
                        0x1D0308]

    vert_palette = [0x000c00,
                    0x8c0c21,
                    0x1010c6,
                    0xa510a5,
                    0xad0c42,
                    0xef04c6,
                    0x310042,
                    0x18e7ff,
                    0x005DC6,
                    0xFFFFFF,
                    ]



    def __init__(self, camera, display, lane_width=30):
        self.width = camera.screen_width
        self.height = camera.screen_height
        self.last_horiz_line_ts = 0
        self.num_vert_lines = 20
        self.vert_points = []
        self.display = display

        self.camera = camera
        self.horiz_y = camera.vp['y']  # 16
        print(f"Horizon Y: {self.horiz_y}")

        self.far_z_horiz = 600
        self.far_z_vert = 1500
        self.near_z = 1

        self.lane_width = lane_width # width in 3D space
        self.lane_height = lane_width * 2 # length of a grid square along the Z axis

        # For vertical road lines only
        self.max_spacing = self.lane_width


        self.field_width = 96
        self.half_field = self.field_width / 2

        self.vert_line_start_x = -round((self.field_width - self.width) / 2)

        self.last_horiz_line_ts = round(utime.ticks_ms())

        self.x_start_top = 0
        self.x_start_bottom = 0

        self.speed = 0
        self.ground_height = camera.screen_height - self.horiz_y

        num_horiz_lines = 20


        """ set up the palettes for line colors """

        red = [97, 0, 112]
        # mag = [255, 0, 50]
        cyan = [0, 255, 255]
        # blue = [20, 80, 255]
        horiz_far = [82, 0, 20]
        horiz_near = [0, 238, 255]

        print(f"Adding horiz colors palette")
        self.check_mem()

        #self.num_horiz_colors = int( ( self.height - self.horiz_y) / 2)
        #self.horiz_palette = colors.make_gradient(horiz_far, horiz_near, self.num_horiz_colors)
        #self.horiz_palette.set_rgb(0, [0, 0, 255])


        self.num_horiz_colors = len(self.horiz_palette)
        # Convert to RGB565
        for i, hex_color in enumerate(self.horiz_palette):
            self.horiz_palette[i] = colors.hex_to_rgb(hex_color)

        self.horiz_palette = FramebufferPalette(self.horiz_palette)

        print(f"Adding horizon palette")
        self.check_mem()


        # self.horizon_palette = colors.make_gradient([21,3,8], [105,5,12], 7)
        # self.horizon_palette.set_rgb(0, [0,0,0]) # Make the first color black

        for i, hex_color in enumerate(self.horizon_palette):
            self.horizon_palette[i] = colors.hex_to_rgb(hex_color)

        self.horizon_palette = FramebufferPalette(self.horizon_palette)

        self.horiz_lines_data = [None] * num_horiz_lines

        print(f"Creating {num_horiz_lines} hlines")
        self.check_mem()

        self.create_horiz_lines(num_horiz_lines)
        self.create_vert_points()

        """ Make vertical palette """

        num_vert_colors = math.ceil(self.num_vert_lines / 2)
        print(f"Making a vertical palette of {num_vert_colors}")

        self.vert_palette = colors.make_gradient(red, cyan, num_vert_colors)

        # new_palette = []

        # for i, hex_color in enumerate(vert_palette_1):
        #     new_palette.append(colors.hex_to_rgb(hex_color))

        # self.vert_palette = FramebufferPalette(new_palette)


        print("After vertical palette")
        self.check_mem()

        # Color last 3 lines cyan & blue (x2: 6 lines total)

        # vert_palette_1.set_rgb(num_vert_colors-3, MIDDLE_CYAN)
        # vert_palette_1.set_rgb(num_vert_colors-2, MIDDLE_BLUE)
        # vert_palette_1.set_rgb(num_vert_colors-1, MIDDLE_BLUE)


        # for idx in range(vert_palette_1.num_colors):
        #     color = vert_palette_1.get_rgb(idx)
        #     color = list(color)
        #     color.reverse()
        #     color = colors.rgb_to_hex(color)

        # Color conversion to RGB
        # palette_1 = [colors.rgb565_to_rgb(color) for color in palette_1]

        vert_palette_2 = self.vert_palette.mirror()


        # Concatenate the two mirrored palettes into one
        self.vert_palette = self.vert_palette + vert_palette_2

        # add_palette = FramebufferPalette(2)
        # add_palette.set_rgb(0, MIDDLE_CYAN)
        # add_palette.set_rgb(1, MIDDLE_CYAN)
        #
        # self.vert_palette = self.vert_palette + add_palette

        # Recolor the added road boundary lines
        # self.vert_palette.num_colors += 2
        # self.vert_palette.palette.append(0x0000)
        # self.vert_palette.palette.append(0x0000)
        #self.vert_palette = self.vert_palette + add_palette
        # for i in range(self.vert_palette.num_colors):
        #     print(self.vert_palette.get_rgb(i))

        # self.vert_palette.set_rgb((num_vert_colors*2), MIDDLE_CYAN)
        # self.vert_palette.set_rgb((num_vert_colors*2) - 1, MIDDLE_CYAN)
        #self.vert_palette = vert_palette_2
        print("After both palettes combined")
        self.check_mem()

    def show(self):
        self.update_horiz_lines()
        self.draw_horizon()
        self.update_vert_lines()


    def create_horiz_lines(self, num_lines):
        for i in range(num_lines):
            self.horiz_lines_data[i] = {'z': (i * self.lane_height)}

        self.far_z_horiz = num_lines * self.lane_height


    def create_vert_points(self):
        """ Calculates the x,y start and end points for the vertical lines of the road grid """

        num_vert_lines = self.num_vert_lines

        lane_width_far, _ = self.camera.to_2d(self.lane_width, 0, self.far_z_vert / 2) # used to measure the lane width in screen space
        lane_width_far = lane_width_far - self.camera.half_width

        lane_width_near, _ = self.camera.to_2d(self.lane_width, 0, self.near_z) # used to measure the lane width in screen space
        lane_width_near = lane_width_near - self.camera.half_width

        self.x_start_top = - ((num_vert_lines-1) * lane_width_far / 2) - 2
        self.x_start_bottom = - ((num_vert_lines-1) * lane_width_near / 2) - 2

        horiz_y_offset = 4 # Manual adjustment for the start.y of the vertical lines
        horiz_y = self.horiz_y + horiz_y_offset

        points_start = [None] * num_vert_lines
        for i in range(num_vert_lines):
            x = (i * lane_width_far) +  self.x_start_top
            points_start[i] = [round(x), horiz_y]

        points_end = [None] * num_vert_lines
        for j in range(num_vert_lines):
            x = (j * lane_width_near) + self.x_start_bottom
            points_end[j] = [round(x), self.height]

        # reinforce the edges of the road
        # lane_start, lane_end = 6, 11
        #
        # idx_1 = lane_start
        # x_1 = (idx_1 * lane_width_far) + self.x_start_top
        #
        # idx_2 = lane_end
        # x_2 = (idx_2 * lane_width_far) + self.x_start_top
        #
        # points_start.insert(idx_1, [x_1-1, horiz_y])
        # points_start.insert(idx_2, [x_2+1, horiz_y])
        #
        # idx_1 = lane_start
        # x_1 = (idx_1 * lane_width_near)+ self.x_start_bottom
        #
        # idx_2 = lane_end
        # x_2 = (idx_2 * lane_width_near)+ self.x_start_bottom
        #
        # points_end.insert(idx_1, [round(x_1-1), self.height])
        # points_end.insert(idx_2+1, [round(x_2+1), self.height])

        print(f"points_Start: {len(points_start)} / points end: {len(points_end)}")
        self.vert_points = [points_start, points_end]

    def update_horiz_lines(self):
        far_z = 0
        last_y = 0
        far_z = 0 # Keep track of the furthest line, to see if we need new ones
        delete_lines = []

        for i, my_line in enumerate(self.horiz_lines_data):
            my_line['z'] = my_line['z'] - self.speed

            if my_line['z'] > far_z:
                far_z = my_line['z']

            _, y = self.camera.to_2d(0, 0, my_line['z'])

            my_line['y'] = y

            # Reached the bottom of the screen, this line is done
            if y > self.display.height:
                delete_lines.append(my_line)
                continue

            # Avoid writing a line on the same Y coordinate as the last one we draw
            if y == last_y:
                continue

            last_y = y

            # Avoid drawing out of bounds
            if my_line['y'] > self.display.height:
                continue

            color_idx = self.horiz_palette.pick_from_value(my_line['y'], self.height, self.horiz_y)

            if color_idx >= self.horiz_palette.num_colors:
                color_idx = self.horiz_palette.num_colors - 1

            rgb565 = self.horiz_palette.get_bytes(color_idx)
            # self.display.hline(0, my_line['y'], self.width, rgb565)
            self.display.rect(0, my_line['y'], self.width - 1, 1, rgb565)

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
        screen_x_far, _ = self.camera.to_2d(0, 0, self.far_z_vert)
        screen_x_near, _ = self.camera.to_2d(0, 0, self.near_z)

        # screen_x_far = 34
        # screen_x_near = 34

        top_points, bottom_points = self.vert_points[0], self.vert_points[1]

        half_width = self.camera.half_width

        # print("COLORS:")
        # for color in self.vert_palette.palette:
        #     print(f"{colors.rgb565_to_rgb(color)}")

        for index in range(len(top_points)):
            start = top_points[index]
            end = bottom_points[index]
            start_x = round(start[0] + screen_x_far)
            end_x = round(end[0] + screen_x_near)
            start_y = start[1]
            end_y = end[1]

            color = self.vert_palette.get_bytes(index)
            # rgb = colors.rgb_to_hex(rgb)
            # rgb = colors.rgb_to_565(rgb)
            # print(f"Color {rgb}")
            # print(f"Color {colors.rgb565_to_rgb(rgb)}")
            # print(f"Coords: {start_x},{start_y},{end_x},{end_y}")
            self.display.line(start_x, start_y, end_x, end_y, color)


    def draw_horizon(self):
        """Draw some static horizontal lines to cover up the seam between vertical and horiz road lines"""
        color: int = 0

        for i in range(0, self.horizon_palette.num_colors-4):
            color = self.horizon_palette.get_bytes(i)
            start_y = self.horiz_y - 2 + (i*2)
            self.display.hline(0, start_y, self.display.width, BLACK)
            self.display.hline(0, start_y + 1, self.display.width,  color)


    def check_mem(self):
        print(f"Free memory:  {gc.mem_free():,} bytes")
