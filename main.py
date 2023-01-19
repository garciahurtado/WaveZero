from display_ssd1331 import SSD1331Display
from displayio import Group, Bitmap, TileGrid, Palette

import gc
import time
import math
import board
import analogio
import adafruit_imageload
from adafruit_display_shapes.line import Line
import adafruit_fancyled.adafruit_fancyled as fancy
import bitmaptools
import ulab.numpy as np
import bitops

from fine_tile_grid import FineTileGrid
from title_screen import show_title
import ui_elements as ui


SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64
start_time_ms = 0
line_cache = {}

def main():
    #temp_sensor = analogio.AnalogIn(board.A4) 
    #conversion_factor = 3.3 / (65535)

    display = SSD1331Display(auto_refresh=False)
    
    #palette = make_palette_from_img()
    
    bike_anim = 8
    bike_bitmap, bike_palette = adafruit_imageload.load(
        "/img/bike_sprite.bmp")
    
    bike_palette.make_transparent(172) # index of #333333
    bike = TileGrid(bike_bitmap, pixel_shader=bike_palette, x=32, y=42, tile_width=37, tile_height=22)
    bike[0] = bike_anim
    
    root = Group()
    root.scale = 1
    
    #show_title(display, root)
    gc.collect()
    print("Free memory at before loop: {} bytes".format(gc.mem_free()) )

    loop(display, root, make_palette(8), bike, bike_anim)

    
def loop(display, root, horiz_palette, bike, bike_anim, speed=1):
    global line_start_time
    start_time_ms = line_start_time = round(time.monotonic() * 1000)
    print(f"Start time: {start_time_ms}")
    
    score = 0
    score_text = ui.init_score(root)
    ui.draw_lives(root)
    ui.draw_score(score, score_text)
    draw_sun(root)
    
    
    horiz_y = 16
    
    # Set up vertical lines
    spacing = 25 
    field_width = 128
    line_group = Group()
  
    #line_layer = draw_vert_lines(line_group, horiz_y, field_width, spacing)
    
    create_vert_lines(line_group, horiz_y, field_width, spacing)
    root.append(line_group)
    
    # Set up horizontal road lines
    lines = []
    num_lines = 22
    lines = create_horiz_lines(root, num_lines, horiz_y, horiz_palette)
   
    
    root.append(bike)
  
    display.show(root)
    
    x1_offset = 0
    x1_max = math.floor(field_width/8)
    x2_offset = 0
    x2_max = spacing
    half_field = int(field_width/2)
    
    
    bike_angle = 0
    fps_list = []
    
    last_frame_ms = round(time.monotonic() * 1000)
    
    
    # Loop to update position of lines
    while True:
        #gc.collect()
        #print("Free memory: {} bytes".format(gc.mem_free()) )
        
        # score += 1
        now = time.monotonic() * 1000
        elapsed_ms = now - last_frame_ms
        last_frame_ms = now
        if elapsed_ms:
            fps = 1000 / elapsed_ms
            fps_list.append(fps)
            
        if len(fps_list) > 20:
            fps_list.pop(0)
            
        if len(fps_list):
            avg_fps = sum(fps_list) / len(fps_list)
            score = round(avg_fps)
        
        line_offset = turn_bike(bike, bike_angle)
        bike_angle = math.sin(now / 1000)
        
        x1_offset = line_offset * 40       
        x2_offset = -line_offset * 10
        bike.x = math.floor((line_offset * 30)) + round(SCREEN_WIDTH / 2) - 18
                 
        update_vert_lines(line_group, horiz_y, field_width, spacing, turn_offset=x2_offset)
        draw_horiz_lines(horiz_y, lines, horiz_palette)
        ui.draw_score(score, score_text)
        display.refresh()
        
        # time.sleep(0.5)
            
    # Wait for next update

def create_horiz_lines(root, num_lines, horiz_y, palette):
    lines = []
    horiz_lines = Group()
    
    for i in range(num_lines):
        bitmap = Bitmap(SCREEN_WIDTH, 1, 34)
        bitmap.fill(0)
        
        grid = FineTileGrid(bitmap, pixel_shader=palette,  y=math.ceil(horiz_y + i*i))
        grid.fine_y = horiz_y
        
        lines.append(grid)
        horiz_lines.append(grid)
        
    root.append(horiz_lines)
    return lines
        
def draw_sun(root):
    sunset_bitmap, sunset_palette = adafruit_imageload.load(
    "/img/sunset.bmp", bitmap=Bitmap, palette=Palette
)
    
    #sunset_palette.make_transparent(0)
    grid = TileGrid(sunset_bitmap, pixel_shader=sunset_palette, x=39, y=5)
    root.append(grid)
    
def turn_bike(bike, angle):
    new_frame = math.floor(((angle * 16) + 17) / 2)
    if bike[0] != new_frame:
        bike[0] = new_frame
        
    line_offset = angle
    return line_offset
     
def draw_horiz_lines(horiz_y, lines, palette):
    global line_start_time
    global_speed = 3
    
    line_freq = 200
    
    
    elapsed_ms = round((time.monotonic() * 1000) - line_start_time)
    # print(f"Elapsed time: {elapsed_ms}")
            
    num_lines = len(lines)
    
    # Time to spawn a new line in the horizon
    if elapsed_ms > line_freq:
        line_start_time = round(time.monotonic() * 1000) # reset timer
        
        for line in lines:
                
            # find a line which is not active
            if line.fine_y <= horiz_y:
                
                line.y = line.fine_y = horiz_y + 1 # this activates the line
                break
         
    for i in range(num_lines):
        # The lines at the very start are in "standby" until its their time to move
        if lines[i].fine_y <= horiz_y:
            continue
        
        line_speed = abs((math.sin( (lines[i].fine_y - horiz_y)  / (SCREEN_HEIGHT - horiz_y)))) + 0.01
        #print(f"Line speed: {line_speed}")
        lines[i].fine_y += line_speed * global_speed
        
        # Reached the bottom
        if lines[i].fine_y >= SCREEN_HEIGHT:
            lines[i].y = lines[i].fine_y = horiz_y - 1           
        elif lines[i].fine_y < horiz_y:
            lines[i].y = lines[i].fine_y = horiz_y
        else:
        
            #Pick the color
            max_y = SCREEN_HEIGHT - horiz_y
            color = math.ceil(lines[i].y - horiz_y)
            # print(f"color: {color}")
            color = (color / max_y) * len(palette)

            lines[i].bitmap.fill(round(color))
            lines[i].y = round(lines[i].fine_y)
        
    return

def create_vert_lines(line_group, start_y, field_width, spacing):
    # Create vertical lines as a series of 1px tall sprites, each with a pattern of
    # dots equally spaced out to simulate one vertical scanline of the vertical
    # road lines
    
    start_x = -round((field_width - SCREEN_WIDTH) / 2 )
    palette = Palette(2)
    palette[0] = 0x000000
    palette[1] = 0xff00c1
    #palette.make_transparent(0)
    min_spacing = 4
    half_field = field_width / 2
    
    for y in range(start_y, SCREEN_HEIGHT):
        rel_y = y - start_y
        ratio = (rel_y+min_spacing)/(SCREEN_HEIGHT-start_y)
        scan = Bitmap(field_width, 1, 2)
        line_spacing = round(spacing * ratio)
        
        dot_offset = round(field_width / 2) % line_spacing
        
        for x in range(0,scan.width,line_spacing):
            if (x + dot_offset) < scan.width:
                scan[x + dot_offset,0] = 1
     
        x_offset = round(start_x-(spacing*(ratio)/2))
        scan_layer = TileGrid(scan, pixel_shader=palette, x=x_offset, y=y)
        line_group.append(scan_layer)
 
def update_vert_lines(line_group, start_y, field_width, max_spacing, turn_offset = 0):
    start_x = -round((field_width - SCREEN_WIDTH) / 2 )
    min_spacing = 4
    half_field = field_width / 2
    
    for layer in line_group:
        rel_y = layer.y - start_y
        ratio = (rel_y+min_spacing)/(SCREEN_HEIGHT-start_y)
        dot_offset = round(field_width / 2) % max_spacing
        x_offset = round(start_x-(max_spacing*(ratio)/2) + (turn_offset*ratio)) 
        layer.x = x_offset
    
    
def make_palette(num_colors):
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

    
def make_palette_from_img():

    bitmap, palette = adafruit_imageload.load(
    "/img/horizon_gradient.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)
    print(palette.__version__)
    palette._colors.sort()
    
    return palette

def empty_group(dio_group):
        """Recursive depth first removal of anything in a Group.
           Intended to be used to clean-up a previous screen
           which may have elements in the new screen
           as elements cannot be in two Groups at once since this
           will cause "ValueError: Layer already in a group".
           This only deletes Groups, it does not del the non-Group content."""
        if dio_group is None:
            return

        ### Go through Group in reverse order
        
        
        for idx in range(len(dio_group) - 1, -1, -1):
           
            if dio_group[idx] is None:
                continue
            ### Avoiding isinstance here as Label is a sub-class of Group!
            ### pylint: disable=unidiomatic-typecheck
            if type(dio_group[idx]) == Group:
                empty_group(dio_group[idx])
            del dio_group[idx]

if __name__ == "__main__":
    main()
