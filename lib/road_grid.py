import gc
import math
import utime
import color_util as colors
from ssd1331_16bit import SSD1331
import micropython

class RoadGrid():

    def __init__(self, camera, display, lane_width=30):
        self.width = camera.screen_width
        self.height = camera.screen_height
        self.last_horiz_line_ts = 0
        self.num_vert_lines = 19
        self.vert_points = []
        self.display = display


        self.camera = camera
        self.horiz_y = camera.vp['y']  # 16
        print(f"Horizon Y: {self.horiz_y}")

        self.far_z_horiz = 600
        self.far_z_vert = 1500
        self.near_z = 1

        self.lane_width = lane_width # width in 3D space

        # For vertical road lines only
        self.max_spacing = self.lane_width


        self.field_width = 96
        self.half_field = self.field_width / 2

        self.vert_line_start_x = -round((self.field_width - self.width) / 2)

        self.last_horiz_line_ts = round(utime.ticks_ms())

        self.x_start_top = 0
        self.x_start_bottom = 0

        self.speed = 8
        self.ground_height = camera.screen_height - self.horiz_y

        num_horiz_lines = 20


        """ set up the palettes for line colors """

        red = [100, 0, 0]
        # mag = [255, 0, 50]
        cyan = [0, 255, 255]
        # blue = [20, 80, 255]
        horiz_far = [82, 0, 20]
        horiz_near = [0, 238, 255]

        print(f"Adding horiz colors palette")
        self.check_mem()

        self.num_horiz_colors = self.height - self.horiz_y
        self.color_default = colors.rgb_to_565([0, 255, 255])
        self.horiz_palette = colors.make_gradient(horiz_far, horiz_near, self.num_horiz_colors)
        self.horiz_palette.insert(0, colors.rgb_to_565([0, 0, 255]))

        print(f"Adding horizon palette")
        self.check_mem()

        self.horizon_palette = colors.make_gradient([21,3,8], [105,5,12], 5)
        self.horizon_palette.insert(0, 0) # Make the first color black
        self.horiz_lines_data = [None] * num_horiz_lines

        print(f"Creating {num_horiz_lines} hlines")
        self.check_mem()

        self.create_horiz_lines(num_horiz_lines)
        self.create_vert_points()

        num_vert_colors = math.ceil(self.num_vert_lines / 2)
        print(f"Making a vertical palette of {num_vert_colors}")

        palette_1 = colors.make_gradient(red, cyan, num_vert_colors)
        print("After vertical palette")
        self.check_mem()

        color = SSD1331.rgb(*colors.hex_to_rgb(0x217eff))
        palette_1[num_vert_colors-3:] = [color] * 3

        # Color conversion to RGB
        # palette_1 = [colors.rgb565_to_rgb(color) for color in palette_1]

        palette_2 = palette_1[::-1] # mirror palette 1


        # Concatenate the two mirrored palettes into one
        self.vert_palette = palette_1 + palette_2
        print("After both palettes combined")
        self.check_mem()

    def show(self):
        self.update_horiz_lines()
        self.draw_horizon()
        self.update_vert_lines()

    def create_horiz_lines(self, num_lines):
        max_z = self.far_z_horiz
        line_separation = max_z / num_lines

        for i in range(num_lines):
            self.horiz_lines_data[i] = {'z': ((i + 1) * line_separation) + 1}


    def create_vert_points(self):
        """ Calculates the x,y start and end points for the vertical lines of the road grid """

        num_lines = self.num_vert_lines

        lane_width_far, _ = self.camera.to_2d(self.lane_width, 0, self.far_z_vert) # used to measure the lane width in screen space
        lane_width_far = lane_width_far - self.camera.half_width

        lane_width_near, _ = self.camera.to_2d(self.lane_width, 0, self.near_z) # used to measure the lane width in screen space
        lane_width_near = lane_width_near - self.camera.half_width

        self.x_start_top = - (num_lines * lane_width_far / 2)
        self.x_start_bottom = - (num_lines * lane_width_near / 2)

        horiz_y_offset = +1; # Manual adjustment for the start.y of the vertical lines
        horiz_y = self.horiz_y + horiz_y_offset

        points_start = [None] * num_lines
        lane_start, lane_end = 7, 12
        for i in range(num_lines):
            x = (i * lane_width_far) + self.camera.half_width
            points_start[i] = [int(x), horiz_y]

            if i == lane_start:
                points_start[i] = [int(x-1), horiz_y]
            elif i == lane_end:
                points_start[i] = [int(x + 1), horiz_y]

        points_end = [None] * num_lines
        for i in range(num_lines):
            x = (i * lane_width_near) + self.camera.half_width
            points_end[i] = [int(x), self.height]

            if i == lane_start:
                points_end[i] = [int(x - 1), self.height]
            elif i == lane_end:
                points_end[i] = [int(x + 1), self.height]

        self.vert_points = [points_start, points_end]

    def update_horiz_lines(self):
        max_z = self.far_z_horiz
        last_y = 0

        for i, my_line in enumerate(self.horiz_lines_data):
            # The lines at the very start are in "standby" until its their time to move
            my_line['z'] = my_line['z'] - self.speed
            _, y = self.camera.to_2d(0, 0, my_line['z'])

            my_line['y'] = y
            self.horiz_lines_data[i] = my_line

            # Reached the bottom of the screen, send the line back up to the horizon
            if y > self.display.height:
                my_line['z'] = max_z
                continue

            # Avoid writing a line on the same Y coordinate as the last one we draw
            if y == last_y:
                continue

            last_y = y

            if my_line['y'] > self.display.height:
                continue

            color_idx = int(my_line['y'] - self.horiz_y)

            if color_idx >= len(self.horiz_palette):
                color_idx = len(self.horiz_palette) - 1

            rgb565 = self.horiz_palette[color_idx]
            self.display.hline(0, my_line['y'], self.width, rgb565)

    def update_vert_lines(self):
        screen_x_far, _ = self.camera.to_2d(0, 0, self.far_z_vert)
        screen_x_near, _ = self.camera.to_2d(0, 0, self.near_z)

        top_points, bottom_points = self.vert_points[0], self.vert_points[1]

        half_width = self.camera.half_width
        for index in range(len(top_points)):
            start = top_points[index]
            end = bottom_points[index]
            start_x = int(start[0] + self.x_start_top + screen_x_far - half_width)
            end_x = int(end[0] + self.x_start_bottom + screen_x_near - half_width)
            start_y = start[1]
            end_y = end[1]

            rgb = self.vert_palette[index]
            self.display.line(start_x, start_y, end_x, end_y, rgb)


    def draw_horizon(self):
        """Draw some static horizontal lines to cover up the seam between vertical and horiz road lines"""

        for i in range(0, len(self.horizon_palette) -2):
            start_y = self.horiz_y - 4 + (i*2)
            self.display.hline(0, start_y, self.display.width, self.horizon_palette[0])
            self.display.hline(0, start_y + 1, self.display.width,  self.horizon_palette[i])


    def check_mem(self):
        print(f"Free memory:  {gc.mem_free():,} bytes")
