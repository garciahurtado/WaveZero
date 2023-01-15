from display_ssd1331 import SSD1331Display
from displayio import Group, Bitmap, TileGrid, Palette

import time
import math
import board
import analogio
import adafruit_imageload
import bitmaptools
import adafruit_fancyled.adafruit_fancyled as fancy

from title_screen import show_title

from adafruit_display_shapes.line import Line
from fine_tile_grid import FineTileGrid
import ui_elements as ui

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64
start_time_ms = 0

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
    
    show_title(display, root)
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
    
    
    horiz_y = 15
    
    # Set up vertical lines
    spacing = 25 
    field_width = 384
    vert_lines = draw_vert_lines(root, horiz_y, field_width=field_width, spacing=spacing)
    
    
    # Set up horizontal road lines
    lines = []
    num_lines = 18
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
        
        # vertical lines
        draw_vert_lines_bmp(
            vert_lines,
            half_field,
            horiz_y,
            spacing,
            x1_offset=x1_offset,
            x2_offset=x2_offset)
        
        # lines_bmp = Bitmap(field_width, SCREEN_HEIGHT - half_height + 1, 3)
    
    
        x1_offset = line_offset * 40       
        x2_offset = -line_offset * 10
        bike.x = math.floor((line_offset * 30)) + round(SCREEN_WIDTH / 2) - 18
                 
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
    
def draw_vert_lines(root, half_height, field_width, spacing):
    
    half_field = round(field_width/2)
    
    line_bmp = Bitmap(field_width, SCREEN_HEIGHT - half_height + 1, 3)
    palette = Palette(3)
    palette[0] = 0x000000
    palette[1] = 0xff00c1
    palette[2] = 0x00aaaa
    
    start_x = round(SCREEN_WIDTH/2) - half_field
    line_layer = TileGrid(line_bmp, pixel_shader=palette, x=start_x, y=half_height)
    root.append(line_layer)
    
    draw_vert_lines_bmp(line_bmp, half_field, half_height, spacing)
    

    return line_bmp

def draw_vert_lines_bmp(line_bmp, half_field, half_height, spacing, x1_offset=0, x2_offset=0):
    bitmaptools.fill_region(line_bmp, 0, 0, line_bmp.width, line_bmp.height, value=0)
    half_field = int(half_field)
    max_x = int(half_field/spacing)
    x1_offset = int(x1_offset)
    x2_offset = int(x2_offset)
    
    top_spacing = 3
    y2 = SCREEN_HEIGHT - half_height
    #print(f"{x1_offset} : {x2_offset} - {half_field}")
    for i in range(-max_x,max_x):
        x1 = half_field + (i * top_spacing) - x1_offset
        y1 = 0
        x2 = half_field + (i * spacing) + x2_offset
        
        # Color the sidelines of the road
        if i == 2 or i == -2:
            color = 2
            bitmaptools.draw_line(dest_bitmap=line_bmp, x1=x1, y1=y1, x2=x2-2, y2=y2, value=color)
            bitmaptools.draw_line(dest_bitmap=line_bmp, x1=x1, y1=y1, x2=x2, y2=y2, value=color)
            bitmaptools.draw_line(dest_bitmap=line_bmp, x1=x1, y1=y1, x2=x2+2, y2=y2, value=color)
        else:
            color = 1
            bitmaptools.draw_line(dest_bitmap=line_bmp, x1=x1, y1=y1, x2=x2, y2=y2, value=color)

    
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


if __name__ == "__main__":
    main()
