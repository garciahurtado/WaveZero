import math
import time
from displayio import Group, Bitmap, TileGrid, Palette
import adafruit_fancyled.adafruit_fancyled as fancy
from fine_tile_grid import FineTileGrid
import bitmaptools

class RoadGrid:
 
    def __init__(self, camera):
        self.width = camera.width
        self.height = camera.height
        self.last_horiz_line_ts = 0
        self.vert_lines = []

        self.horiz_y = camera.vp['y'] # 16
        print(f"Horizon Y: {self.horiz_y}")
        self.max_spacing = 25
        self.field_width = 128
        self.vert_line_start_x = -round((self.field_width - self.width) / 2 )
    
        self.last_horiz_line_ts = round(time.monotonic() * 1000)
        self.max_z = 100000
        
        num_horiz_lines = 100
        num_colors = 4
        self.horiz_palette = self.make_palette(num_colors)
        self.horiz_lines = Group()
        self.horiz_lines_data = []
        self.horiz_lines_bmp = Bitmap( self.width, self.height, len(self.horiz_palette))
        self.horiz_lines_grid = TileGrid(self.horiz_lines_bmp, pixel_shader=self.horiz_palette, x=0, y=0)
        #self.horiz_lines.append(self.horiz_lines_grid)

        self.create_horiz_lines(num_horiz_lines)
        self.create_vert_lines()
            
    def create_horiz_lines(self, num_lines):
        max_z = self.max_z
        line_separation = 50
        
        for i in range(num_lines):
            #grid = FineTileGrid(bitmap, pixel_shader=palette,  y=math.ceil(self.start_y + i*i))
            #line = {'fine_y': self.horiz_y, 'y':math.ceil(self.horiz_y + i * i)}
            line = {'z' : ((i+1) * line_separation) + 1}

            self.horiz_lines_data.append(line)

    def draw_horiz_lines(self):
        global_speed = 100
        line_freq = 20
        elapsed_ms = round((time.monotonic() * 1000) - self.last_horiz_line_ts)
        max_z = self.max_z
        min_z = 10

        self.horiz_lines_bmp.fill(0)
       
        # Time to spawn a new line in the horizon
        if elapsed_ms > line_freq:
            self.last_horiz_line_ts = round(time.monotonic() * 1000) # reset timer
            
            for line in self.horiz_lines_data:
                # find a line which is not active
                if line['z'] < min_z:
                    line['z'] = max_z # this activates the line
                    break
             
        for my_line in self.horiz_lines_data:
            # The lines at the very start are in "standby" until its their time to move
            if my_line['z'] < min_z:
                continue

            y = self.calculate_screen_y(my_line['z'])
            #print(f"For Z: {my_line['z']}, Calculated y as {y}")

            #Pick the color
            max_y = self.height - self.horiz_y
            my_color = y - self.horiz_y
            my_color = round((my_color / max_y) * (len(self.horiz_palette) - 1) )
            if my_color >= len(self.horiz_palette):
                my_color = len(self.horiz_palette) - 1

            bitmaptools.draw_line(self.horiz_lines_bmp, 0, y, self.width, y, my_color)

            #
            # # my_line.bitmap.fill(color)
            # #y = math.floor(my_line['y'] if my_line['y'] <= SCREEN_HEIGHT else SCREEN_HEIGHT)
            # y = my_line['y']
            # y = y - 8
            #
            # if (y < SCREEN_HEIGHT):
            #     # print(f"y:{y} / c:{my_color} / colors: {len(self.horiz_palette)}")
            #     bitmaptools.draw_line(self.horiz_lines_bmp, 0, y, SCREEN_WIDTH, y, my_color)
            #
            # line_speed = abs((math.sin((my_line['fine_y'] - self.horiz_y) / (SCREEN_HEIGHT - self.horiz_y)))) + 0.01
            # # print(f"Line speed: {line_speed}")
            # my_line['fine_y'] += line_speed * global_speed
            #
            # # Calculate the new value for the Y coordinate
            # # new_y = round(my_line['fine_y'])
            # # if my_line['y'] != new_y:
            # #     my_line['y'] = new_y

            my_line['z'] = my_line['z'] - global_speed

        self.horiz_lines_bmp.dirty()
        return

    def create_vert_lines(self):
        # Create vertical lines as a series of 1px tall sprites, each with a pattern of
        # dots equally spaced out to simulate one vertical scanline of the vertical
        # road lines
        
        start_x = self.vert_line_start_x
        palette = Palette(5)
        palette[0] = 0x000000
        palette[1] = 0xff00c1
        palette[2] = 0xff0000 # red
        palette[3] = 0x00ff00 # green
        palette[4] = 0x00ffff # cyan
        palette.make_transparent(0)
        min_spacing = 4
        half_field = self.field_width / 2
        
        for y in range(self.horiz_y, self.height):
            rel_y = y - self.horiz_y
            ratio = (rel_y+min_spacing)/(self.height - self.horiz_y)
            scan = Bitmap(self.field_width, 1, 5)
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

    def make_palette(self, num_colors):
        # Set up color palette
        palette = Palette(num_colors+1)

        palette[0] = 0x000000 # black

        # Set starting and ending colors
        start_color = fancy.CHSV(303,1.00,0.99)
        end_color = fancy.CHSV(179,1.00,1.00)

        # Add colors to palette
        for i in range(1,num_colors+1):
            # Calculate color value
            newcolor = fancy.mix(start_color, end_color, (i/num_colors) * 100) 
            palette[i] = newcolor.pack()

        return palette

    def calculate_screen_y(self, z):
        focal_length = 150
        if z <= 0:
            raise ValueError("Z coordinate must be greater than 0")

        # Calculate the field of view (FOV) based on the screen width and focal distance
        # fov = 2 * math.atan(SCREEN_WIDTH / (2 * focal_length))

        # Calculate the perspective-accurate screen Y coordinate
        #screen_y = (self.horiz_y - focal_length * (self.horiz_y - (SCREEN_HEIGHT / 2)) / z)

        vertical_offset = (self.height / 2 - self.horiz_y) * focal_length / z

        # Calculate the perspective-accurate screen Y coordinate
        screen_y = self.horiz_y + vertical_offset

        return int(screen_y)
