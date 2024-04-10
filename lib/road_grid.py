import math
import utime
import color_old as colors

class RoadGrid:
 
    def __init__(self, camera, display):
        self.width = camera.width
        self.height = camera.height
        self.last_horiz_line_ts = 0
        self.vert_points = []
        self.display = display

        self.sway = 0
        self.sway_dir = 1
        self.sway_max = 20

        self.camera = camera
        self.horiz_y = camera.vp['y'] # 16
        print(f"Horizon Y: {self.horiz_y}")

        # For vertical road lines only
        self.min_spacing = 4
        self.max_spacing = 25
        
        self.field_width = 96
        self.vert_line_start_x = -round((self.field_width - self.width) / 2 )
    
        self.last_horiz_line_ts = round(utime.ticks_ms())
        self.max_z = 4000
        
        num_horiz_lines = 100
        print(f"Creating {num_horiz_lines} hlines")
        # red1 = Color('red')
        # red = Color('#ff0000')
        # mag = Color('#ff0064')
        # cyan = Color('#42f2f5')
        # blue = Color('#1450ff')

        red = [100,0,0]
        mag = [255,0,50]
        cyan = [0,255,255]
        blue = [20,80,255]
        horiz_far = [82, 0, 20]
        horiz_near = [0, 238, 255]

        self.num_horiz_colors = 48
        self.color_default = colors.rgb_to_565((0,255,255))
        self.horiz_palette = colors.make_palette(horiz_far, horiz_near, self.num_horiz_colors)
        #self.horiz_palette.insert(0, [0,0,0])

        #self.horiz_palette = list(blue.range_to(cyan, self.num_horiz_colors))

        self.horiz_lines_data = []
        self.create_horiz_lines(num_horiz_lines)

        points1, points2 = self.create_vert_points()
        num_vert_colors = int(len(points1)/2)
        print(f"Making a vertical palette of {num_vert_colors}")
        
        palette_1 = colors.make_palette(red, cyan, num_vert_colors)
        palette_2 = palette_1[::-1]
        
        self.vert_palette = palette_1 + palette_2

            
    def create_horiz_lines(self, num_lines):
        max_z = self.max_z
        line_separation = (max_z) / num_lines
        
        for i in range(num_lines):
            #grid = FineTileGrid(bitmap, pixel_shader=palette,  y=math.ceil(self.start_y + i*i))
            #line = {'fine_y': self.horiz_y, 'y':math.ceil(self.horiz_y + i * i)}
            line = {'z' : ((i+1) * line_separation) + 1}

            self.horiz_lines_data.append(line)

    def draw_horiz_lines(self):
        global_speed = 8
        elapsed_ms = round(utime.ticks_ms() - self.last_horiz_line_ts)
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
            
            #print(f"For Z: {my_line['z']}, Calculated y as {y}")

            if y != self.horiz_y:
                rel_y = (y - self.horiz_y) / (self.display.height - self.horiz_y)
                rel_y = max(0.0, min(1.0, rel_y))  # Clamp rel_y between 0 and 1
            else:
                rel_y = 1.0 
            
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
        self.field_width
        self.min_spacing
        self.max_spacing

        num_lines = self.field_width // self.min_spacing

        # Calculate maximum X of the bottom points, to center both sets of points
        max_x_top = num_lines * self.min_spacing
        max_x_bottom = num_lines * self.max_spacing
        x_offset_top = int((max_x_top / 2) - (self.width/2) + (self.min_spacing))
        x_offset_bottom = int((max_x_bottom / 2) - (self.width/2) - (self.max_spacing/2))

        points_start = []
        # [[(i * self.min_spacing) - x_offset_top, self.horiz_y] for i in range(num_lines)]
        points_end = []
        #[[(i * self.max_spacing) - x_offset_bottom, self.height] for i in range(num_lines)]
        
        for i in range(num_lines):
            start_x = (i * self.min_spacing) - x_offset_top
            end_x = (i * self.max_spacing) - x_offset_bottom
            points_start.append([start_x, self.horiz_y])
            points_end.append([end_x, self.height])
            

        self.vert_points = [points_start, points_end]
        return self.vert_points
    
    def draw_vert_lines(self):
        top_points, bottom_points = self.vert_points
        start_x = 0
        rel_y = 0
        start_x_offset = int(self.camera.vp['x']*1.7) - 7
        end_x_offset = self.camera.vp['x']

        for index, (start, end) in enumerate(zip(top_points, bottom_points)):

            ratio_start = (rel_y+self.min_spacing)/(self.height - self.horiz_y)
            ratio_end = (rel_y+self.min_spacing)/(self.height)
            
            x_offset_start = round(start_x-(self.max_spacing*(ratio_start)/2)) # Apply 3d perspective to x offset of each 1px slice
            x_offset_end = round(start_x-(self.max_spacing*(ratio_end)/2))
            x_offset_start = self.vert_line_start_x
            
            start_x = start[0] - start_x_offset
            end_x = end[0] - end_x_offset
            
            self.display.line(start_x, start[1], end_x, end[1], self.vert_palette[index])

    def update_sway(self):
        self.sway = self.sway + (1 * self.sway_dir)
        if abs(self.sway) > self.sway_max:
            self.sway_dir = self.sway_dir * -1

    def create_vert_lines(self):

        # Create vertical lines as a series of 1px tall sprites, each with a pattern of
        # dots equally spaced out to simulate one vertical scanline of the vertical
        # road lines
        
        start_x = self.vert_line_start_x
        palette = []
        palette[0] = 0x000000
        palette[1] = 0xff00c1
        palette[2] = 0xff0000 # red
        palette[3] = 0x00ff00 # green
        palette[4] = 0x00ffff # cyan
        min_spacing = self.min_spacing
        
        for y in range(self.horiz_y, self.height):
            rel_y = y - self.horiz_y
            ratio = (rel_y+min_spacing)/(self.height - self.horiz_y)
            scan = lv.img(self.field_width, 1, 5)
            line_spacing = round(self.max_spacing * ratio)
            x_offset = round(start_x-(self.max_spacing*(ratio)/2)) # Apply 3d perspective to x offset of each 1px slice
            dot_offset = round(self.field_width / 2) % line_spacing
            
            col = 0
            for x in range(0,scan.width,line_spacing):
                # print(f"Col {col} - LS: {line_spacing}")
                
                
                if (x + dot_offset) < scan.width:
                    scan[x + dot_offset,0] = 1
                    
#                     if (col == 3):
#                         start_x = x - x_offset
#                         for xx in range(start_x, start_x + dot_offset):
#                             if (xx < scan.width) and (xx > 0):
#                                 # print(f"paint at {xx}")
#                                 scan[xx,0] = 3
                
                
                col = math.ceil(x / line_spacing) - round((x_offset / line_spacing)) # correct
                            
                    
         

            scan_layer = TileGrid(scan, pixel_shader=palette, x=x_offset, y=y)
            self.vert_lines.append(scan_layer)
            
    def get_x_offset(self, turn_offset=0):
        min_spacing = 4
        ratio = (self.horiz_y + min_spacing) / self.height
        x_offset = round(self.vert_line_start_x - (self.max_spacing * ratio) / 2 - (turn_offset * ratio))
        self.vert_line_start_x = x_offset
        return x_offset
            
    def update_vert_lines(self, turn_offset = 0):
        start_x = self.vert_line_start_x
        min_spacing = 4
        
        for i, line  in enumerate(self.vert_lines):
            ratio = (line.y+min_spacing)/(self.height)
            x_offset = round(start_x-(self.max_spacing*(ratio)/2) - (turn_offset*ratio))
            if (i == 0):
                # We want to return the first offset calculated, because it will be used
                # in the return value, so that we can influence the 3D camera vanishing point
                ret_x_offset = x_offset
 
            layer = self.vert_lines[i]
            if layer.x != x_offset:
                layer.x = x_offset
               
               
        return ret_x_offset 


    def calculate_screen_y(self, z):
        # Adjust the horizon a little
        horiz_y = self.horiz_y

        focal_length = 150
        if z <= 0:
            raise ValueError("Z coordinate must be greater than 0")

        vertical_offset = (self.height / 2 - horiz_y) * focal_length / z

        # Calculate the perspective-accurate screen Y coordinate
        screen_y = horiz_y + vertical_offset 

        # Adjust a little for the horizon we want
        # screen_y = screen_y - 10

        return round(screen_y)
