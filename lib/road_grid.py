import math
import utime
import color_util as colors
from ssd1331_16bit import SSD1331


class RoadGrid():

    def __init__(self, camera, display):
        self.width = camera.screen_width
        self.height = camera.screen_height
        self.last_horiz_line_ts = 0
        self.vert_points = []
        self.display = display


        self.camera = camera
        self.horiz_y = camera.vp['y']  # 16
        print(f"Horizon Y: {self.horiz_y}")

        self.far_z = 500
        self.near_z = 1

        # For vertical road lines only
        self.min_spacing = 4
        self.max_spacing = 8

        self.field_width = 96
        self.vert_line_start_x = -round((self.field_width - self.width) / 2)

        self.last_horiz_line_ts = round(utime.ticks_ms())
        self.max_z = self.far_z * 4

        self.offset_top = 0
        self.offset_bottom = 0



        num_horiz_lines = 50
        print(f"Creating {num_horiz_lines} hlines")
        # red1 = Color('red')
        # red = Color('#ff0000')
        # mag = Color('#ff0064')
        # cyan = Color('#42f2f5')
        # blue = Color('#1450ff')

        red = [100, 0, 0]
        mag = [255, 0, 50]
        cyan = [0, 255, 255]
        blue = [20, 80, 255]
        horiz_far = [82, 0, 20]
        horiz_near = [0, 238, 255]

        self.num_horiz_colors = 48
        self.color_default = colors.rgb_to_565([0, 255, 255])
        self.horiz_palette = colors.make_gradient(horiz_far, horiz_near, self.num_horiz_colors)
        self.horiz_palette.insert(0, colors.rgb_to_565([0, 0, 255]))

        # self.horiz_palette = list(blue.range_to(cyan, self.num_horiz_colors))

        self.horiz_lines_data = []
        self.create_horiz_lines(num_horiz_lines)

        points1, points2 = self.create_vert_points()
        num_vert_colors = math.ceil(len(points1) / 2)
        print(f"Making a vertical palette of {num_vert_colors}")

        palette_1 = colors.make_gradient(red, cyan, num_vert_colors)

        # The last 3 colors are different, since they mark the ridable lanes
        # hex: 0x217eff (pink) or 0xff7e21 (cyan)
        color = SSD1331.rgb(*colors.hex_to_rgb(0x217eff))
        palette_1[num_vert_colors-3:] = [color] * 3
        palette_2 = palette_1[::-1]

        self.vert_palette = palette_1 + palette_2

    def create_horiz_lines(self, num_lines):
        max_z = self.max_z
        line_separation = (max_z) / num_lines

        for i in range(num_lines):
            # grid = FineTileGrid(bitmap, pixel_shader=palette,  y=math.ceil(self.start_y + i*i))
            # line = {'fine_y': self.horiz_y, 'y':math.ceil(self.horiz_y + i * i)}
            line = {'z': ((i + 1) * line_separation) + 1}

            self.horiz_lines_data.append(line)

    def draw_horiz_lines(self):
        global_speed = 8
        max_z = self.max_z
        min_z = 1
        last_y = 0

        for i, my_line in enumerate(self.horiz_lines_data):

            # The lines at the very start are in "standby" until its their time to move
            my_line['z'] = my_line['z'] - global_speed
            y = self.calculate_screen_y(my_line['z'])

            # Reached the bottom of the screen, send the line back up to the horizon
            if y > self.display.height:
                my_line['z'] = max_z
                continue

            # Avoid writing a line on the same Y coordinate as the last one we draw
            if y == last_y:
                continue

            # print(f"For Z: {my_line['z']}, Calculated y as {y}")

            if y != self.horiz_y:
                rel_y = (y - self.horiz_y) / (self.display.height - self.horiz_y)
                rel_y = max(0.0, min(1.0, rel_y))  # Clamp rel_y between 0 and 1
            else:
                rel_y = 0

            my_color_index = int(rel_y * len(self.horiz_palette))
            # print(f"my_color_index: {my_color_index}")

            if my_color_index >= len(self.horiz_palette):
                my_color_index = len(self.horiz_palette) - 1

            # color_red = self.display.rgb(255,0,0)
            rgb565 = self.horiz_palette[my_color_index]
            self.display.hline(0, y, self.width, rgb565)
            last_y = y

        return


    def create_vert_points(self):
        """ Calculates the x,y start and end points for the vertical lines of the road grid """

        num_lines = 19
        lane_width = 20 # width in 3D space

        half_field = self.field_width / 2
        lane_width_far, _ = self.camera.to_2d(lane_width, 0, self.far_z) # used to measure the lane width in screen space
        lane_width_far = lane_width_far - self.camera.half_width

        print(f"Lane width far: {lane_width_far}")
        lane_width_near, _ = self.camera.to_2d(lane_width, 0, self.near_z) # used to measure the lane width in screen space
        lane_width_near = lane_width_near - self.camera.half_width

        print(f"Lane width near: {lane_width_near}")

        self.offset_top = - (num_lines * lane_width_far / 2)
        self.offset_bottom = - (num_lines * lane_width_near/ 2)

        points_start = []
        lane_edges = [7, 12]
        for i in range(num_lines):
            x = (i * lane_width_far) + self.camera.half_width
            # x = int(x -  (self.width / 2) )
            # x = int(x -  (self.width / 2) )
            points_start.append([int(x), self.horiz_y])

            if i in lane_edges:
                points_start.append([int(x-1), self.horiz_y])

        points_end = []
        for i in range(num_lines):
            x = (i * lane_width_near) + self.camera.half_width
            points_end.append([int(x), self.height])

            if i in lane_edges:
                points_end.append([int(x-1), self.height])

        self.vert_points = [points_start, points_end]
        return self.vert_points

    def draw_vert_lines(self):
        top_points, bottom_points = self.vert_points
        start_x = 0
        rel_y = 0
        start_x_offset = int(self.camera.vp['x'])
        end_x_offset = self.camera.vp['x']

        screen_x_far, _ = self.camera.to_2d(0, 0, self.far_z)
        screen_x_near, _ = self.camera.to_2d(0, 0, self.near_z)

        for index, (start, end) in enumerate(zip(top_points, bottom_points)):
            ratio_start = (rel_y + self.min_spacing) / (self.height - self.horiz_y)
            ratio_end = (rel_y + self.min_spacing) / (self.height)

            start_x = int(start[0] + self.offset_top + screen_x_far - self.camera.half_width)
            end_x = int(end[0] + self.offset_bottom + screen_x_near - self.camera.half_width)
            start_y = start[1]
            end_y = end[1]

            self.display.line(start_x, start_y, end_x, end_y, self.vert_palette[index])

    def create_vert_lines(self):

        # Create vertical lines as a series of 1px tall sprites, each with a pattern of
        # dots equally spaced out to simulate one vertical scanline of the vertical
        # road lines

        start_x = self.vert_line_start_x
        palette = []
        palette[0] = 0x000000
        palette[1] = 0xff00c1
        palette[2] = 0xff0000  # red
        palette[3] = 0x00ff00  # green
        palette[4] = 0x00ffff  # cyan
        min_spacing = self.min_spacing

    def update_vert_lines(self, turn_offset=0):
        start_x = self.vert_line_start_x
        min_spacing = 4

        for i, line in enumerate(self.vert_lines):
            ratio = (line.y + min_spacing) / (self.height)
            x_offset = round(start_x - (self.max_spacing * (ratio) / 2) - (turn_offset * ratio))
            if (i == 0):
                # We want to return the first offset calculated, because it will be used
                # in the return value, so that we can influence the 3D camera vanishing point
                ret_x_offset = x_offset

            layer = self.vert_lines[i]
            if layer.x != x_offset:
                layer.x = x_offset

        return ret_x_offset

    def calculate_screen_y(self, z):
        x = y = 0
        x, y = self.camera.to_2d(x, y, z)
        return y

        # Adjust the horizon a little
        horiz_y = self.horiz_y

        focal_length = 150
        if z <= 0:
            z = 0.5

        vertical_offset = (self.height / 2 - horiz_y) * focal_length / z

        # Calculate the perspective-accurate screen Y coordinate
        screen_y = horiz_y + vertical_offset

        # Adjust a little for the horizon we want
        # screen_y = screen_y - 10

        return round(screen_y)
