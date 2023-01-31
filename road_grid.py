import math
import time
import ulab.numpy as np
from displayio import Group, Bitmap, TileGrid, Palette
import adafruit_fancyled.adafruit_fancyled as fancy
from fine_tile_grid import FineTileGrid

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64

class RoadGrid:
 
    def __init__(self, start_y):
        self.last_horiz_line_ts = 0
        self.vert_lines = Group()
        self.horiz_lines = Group()
        self.start_y = 0
        self.max_spacing = 25 
        self.field_width = 128
        self.vert_line_start_x = -round((self.field_width - SCREEN_WIDTH) / 2 )
    
        self.last_horiz_line_ts = round(time.monotonic() * 1000)
        self.start_y = start_y
        
        num_horiz_lines = 13
        self.horiz_palette = self.make_palette(8)
        self.create_horiz_lines(num_horiz_lines, self.horiz_palette)
        self.create_vert_lines()
            
    def create_horiz_lines(self, num_lines, palette):
        
        for i in range(num_lines):
            bitmap = Bitmap(SCREEN_WIDTH, 1, 34)
            bitmap.fill(0)
            
            grid = FineTileGrid(bitmap, pixel_shader=palette,  y=math.ceil(self.start_y + i*i))
            grid.fine_y = self.start_y
            
            self.horiz_lines.append(grid)
            

    def draw_horiz_lines(self):
        global_speed = 3
        line_freq = 300
        elapsed_ms = round((time.monotonic() * 1000) - self.last_horiz_line_ts)
       
        # Time to spawn a new line in the horizon
        if elapsed_ms > line_freq:
            self.last_horiz_line_ts = round(time.monotonic() * 1000) # reset timer
            
            for line in self.horiz_lines:              
                # find a line which is not active
                if line.fine_y <= self.start_y:                   
                    line.y = line.fine_y = self.start_y + 1 # this activates the line
                    break
             
        for my_line in self.horiz_lines:
            # The lines at the very start are in "standby" until its their time to move
            if my_line.fine_y <= self.start_y:
                continue
            
            line_speed = abs((math.sin( (my_line.fine_y - self.start_y)  / (SCREEN_HEIGHT - self.start_y)))) + 0.01
            #print(f"Line speed: {line_speed}")
            my_line.fine_y += line_speed * global_speed
            
            # Reached the bottom
            if my_line.fine_y >= SCREEN_HEIGHT:
                my_line.y = my_line.fine_y = self.start_y - 1           
            elif my_line.fine_y < self.start_y:
                my_line.y = my_line.fine_y = self.start_y
            else:
            
                #Pick the color
                max_y = SCREEN_HEIGHT - self.start_y
                color = math.ceil(my_line.y - self.start_y)
                # print(f"color: {color}")
                color = (color / max_y) * len(self.horiz_palette)

                my_line.bitmap.fill(round(color))
                
                # Calculate the new value for the Y coordinate
                new_y = round(my_line.fine_y)
                if my_line.y != new_y:
                    my_line.y = new_y
                
            
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
        
        print(f"Total width: {self.field_width}")
        
        for y in range(self.start_y, SCREEN_HEIGHT):
            rel_y = y - self.start_y
            ratio = (rel_y+min_spacing)/(SCREEN_HEIGHT-self.start_y)
            scan = Bitmap(self.field_width, 1, 5)
            line_spacing = round(self.max_spacing * ratio)
            x_offset = round(start_x-(self.max_spacing*(ratio)/2)) # Apply 3d perspective to x offset of each 1px slice
            dot_offset = round(self.field_width / 2) % line_spacing
            
            col = 0
            for x in range(0,scan.width,line_spacing):
                # print(f"Col {col} - LS: {line_spacing}")
                
                
                if (x + dot_offset) < scan.width:
                    scan[x + dot_offset,0] = 1
                    
                    if (col == 3):
                        start_x = x - x_offset
                        for xx in range(start_x, start_x + dot_offset):
                            if (xx < scan.width) and (xx > 0):
                                # print(f"paint at {xx}")
                                scan[xx,0] = 3
                
                
                col = math.ceil(x / line_spacing) - round((x_offset / line_spacing)) # correct
                            
                    
         

            scan_layer = TileGrid(scan, pixel_shader=palette, x=x_offset, y=y)
            self.vert_lines.append(scan_layer)
            
    def update_vert_lines(self, turn_offset = 0):
        start_x = self.vert_line_start_x
        min_spacing = 4
        
        for i, line  in enumerate(self.vert_lines):
            ratio = (line.y+min_spacing)/(SCREEN_HEIGHT)
            x_offset = round(start_x-(self.max_spacing*(ratio)/2) + (turn_offset*ratio))
 
            layer = self.vert_lines[i]
            if layer.x != x_offset:
                layer.x = x_offset
               
               
         

    def make_palette(self, num_colors):
        # Set up color palette
        palette = Palette(num_colors)

        # Set starting and ending colors
        start_color = fancy.CHSV(303,1.00,0.99)
        end_color = fancy.CHSV(179,1.00,1.00)

        # Add colors to palette
        for i in range(num_colors):
            # Calculate color value
            newcolor = fancy.mix(start_color, end_color, (i/num_colors) * 100) 
            palette[i] = newcolor.pack()
            
        return palette
