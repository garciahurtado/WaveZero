from display_ssd1331 import SSD1331Display
import displayio
import time
import math
import board
import analogio
import adafruit_imageload.bmp.indexed
import bitmaptools
from title_screen import show_title

from adafruit_display_shapes.line import Line
from fine_tile_grid import FineTileGrid

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64
start_time_ms = 0

def main():
    #temp_sensor = analogio.AnalogIn(board.A4)
    #conversion_factor = 3.3 / (65535)

    display = SSD1331Display(auto_refresh=False)
    
    #palette = make_palette(32)
    palette = make_palette_from_img()
    
    
    bike_bitmap, bike_palette = adafruit_imageload.load(
    "/bike.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette
)
       
    bike_palette.make_transparent(2)
    bike = displayio.TileGrid(bike_bitmap, pixel_shader=bike_palette, x=43, y=34)
    
    
    root = displayio.Group()
    
    show_title(display, root)
    loop(display, root, palette, bike)

    
def loop(display, root, palette, bike, speed=1):
    global start_time_ms
    start_time_ms = round(time.monotonic() * 1000)
    print(f"Start time: {start_time_ms}")
    
  
    
    # Set up moving lines
    lines = []
    num_lines = 24
    half_height = round(SCREEN_HEIGHT / 2) - 10
    
    horiz = displayio.Bitmap(SCREEN_WIDTH, 1, 34)
    horiz.fill(0)
    horiz_lines = displayio.Group()
    
    for i in range(num_lines):
        bitmap = displayio.Bitmap(SCREEN_WIDTH, 1, 34)
        bitmap.fill(0)
        start_y = half_height
        
        grid = FineTileGrid(bitmap, pixel_shader=palette,  y=start_y)
        grid.fine_y = start_y
        
        lines.append(grid)
        horiz_lines.append(grid)
        
    
    # Set starting position for lines
    line_y = SCREEN_HEIGHT

    # show root Display group 
    
    # print(dir(display))
    spacing = 20
    field_width = 384
    vert_lines = draw_vert_lines(root, half_height, field_width=field_width, spacing=spacing)
    
    root.append(horiz_lines)
    root.append(bike)
  
    display.show(root)
    x1_offset = 0
    x1_max = math.floor(field_width/8)
    x2_offset = 0
    x2_max = spacing
        
    # Loop to update position of lines
    while True:
        
        elapsed_ms = round((time.monotonic() * 1000) - start_time_ms)
        
        # vertical lines
        update_vert_lines(vert_lines, int(field_width/2), half_height, spacing, x1_offset, x2_offset)
        freq = 30
        elapsed = (elapsed_ms / 1000) % freq
        # x1_offset += math.sin(elapsed) * x1_max 
        #x1_offset = x1_offset % (x1_max * 2)
        if x1_offset > x1_max:
            x1_offset = x1_max
            
        #x2_offset += 2
        if x2_offset > x2_max:
            x2_offset = 0
         
        draw_horiz_lines(half_height, lines)
        
        display.refresh()
        
        #time.sleep(0.01)
            
    # Wait for next update
    
def draw_horiz_lines(half_height, lines):
    global start_time_ms
    global_speed = 4
    
    line_freq = 150
    
    
    elapsed_ms = round((time.monotonic() * 1000) - start_time_ms)
    # print(f"Elapsed time: {elapsed_ms}")
            
    num_lines = len(lines)
    
    # Time to spawn a new line in the horizon
    if elapsed_ms > line_freq:
        start_time_ms = round(time.monotonic() * 1000) # reset timer
        
        for line in lines:
                
            # find a line which is not active
            if line.fine_y <= half_height:
                
                line.y = line.fine_y = half_height + 1 # this activates the line
                break
         
    for i in range(num_lines):
        # The lines at the very start are in "standby" until its their time to move
        if lines[i].fine_y == half_height:
            continue
        
        # line_speed = (lines[i].fine_y * lines[i].fine_y) / 511
        line_speed = abs((math.sin( (lines[i].fine_y - half_height)  / (SCREEN_HEIGHT - half_height)))) + 0.01
        #print(f"Line speed: {line_speed}")
        lines[i].fine_y += line_speed * global_speed
        
        # Reached the bottom
        if lines[i].fine_y >= SCREEN_HEIGHT:
            lines[i].y = lines[i].fine_y = half_height - 1           
        elif lines[i].fine_y < half_height:
            lines[i].y = lines[i].fine_y = half_height
        else:
        
            #Pick the color
            color = math.ceil(lines[i].y - half_height) + 1
            # print(f"color: {color}")
            max_y = SCREEN_HEIGHT - half_height
            color = (color / max_y) * 34

            lines[i].bitmap.fill(round(color))
            lines[i].y = round(lines[i].fine_y)
        
    return
    
def draw_vert_lines(root, half_height, field_width, spacing):
    
    half_field = round(field_width/2)
    
    line_bmp = displayio.Bitmap(field_width, SCREEN_HEIGHT - half_height + 1, 2)
    palette = displayio.Palette(2)
    palette[0] = 0x000000
    palette[1] = 0xff00c1
    
    start_x = round(SCREEN_WIDTH/2) - half_field
    line_layer = displayio.TileGrid(line_bmp, pixel_shader=palette, x=start_x, y=half_height)
    root.append(line_layer)
    
    draw_vert_lines_bmp(line_bmp, half_field, half_height, spacing)
    

    return line_bmp

def draw_vert_lines_bmp(line_bmp, half_field, half_height, spacing, x1_offset=0, x2_offset=0):
    
    for i in range(-int(half_field/spacing),int(half_field/spacing)):
        x1 = round(half_field + i - x1_offset)
        y1 = 0
        x2 = round(half_field + (i * spacing) + x2_offset)
        y2 = SCREEN_HEIGHT - half_height
        
        #print(f"{x1} {y1} {x2} {y2}")
        bitmaptools.draw_line(dest_bitmap=line_bmp, x1=x1, y1=y1, x2=x2, y2=y2, value=1)
        
        
def update_vert_lines(lines_bmp, half_field, half_height, spacing, x1_offset=0, x2_offset=0):
    lines_bmp.fill(0)
    draw_vert_lines_bmp(lines_bmp, half_field, half_height, spacing, x1_offset=x1_offset, x2_offset=x2_offset)
    lines_bmp.dirty()
    
    
def make_palette(num_colors):
    # Set up color palette
    palette = displayio.Palette(num_colors)

    # Set starting and ending colors
    start_color = 0x00FFFF 
    end_color = 0xFF00FF

    # Calculate color increments
    red_increment = ((end_color & 0xFF0000) - (start_color & 0xFF0000)) / num_colors
    green_increment = ((end_color & 0x00FF00) - (start_color & 0x00FF00)) / num_colors
    blue_increment = ((end_color & 0x0000FF) - (start_color & 0x0000FF)) / num_colors
    
    print(f"Red: {red_increment}")
    print(f"Green: {green_increment}")
    print(f"Blue: {blue_increment}")

    # Add colors to palette
    for i in range(num_colors):
        # Calculate color value
        red = (start_color & 0xFF0000) + (i * red_increment)
        green = (start_color & 0x00FF00) + (i * green_increment)
        blue = (start_color & 0x0000FF) + (i * blue_increment)
        color = (int(red) & 0xFF0000) + (int(green) & 0x00FF00) + (int(blue) & 0x0000FF)
      
        palette[i] = color
        
    return palette

    
def make_palette_from_img():

    bitmap, palette = adafruit_imageload.load(
    "/horizon_gradient.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)
    return palette


if __name__ == "__main__":
    main()
