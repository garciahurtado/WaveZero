from display_ssd1331 import SSD1331Display
import displayio
import time
import math
import board
import analogio

from adafruit_display_shapes.line import Line
from fine_tile_grid import FineTileGrid

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64
start_time_ms = 0

def main():
    #temp_sensor = analogio.AnalogIn(board.A4)
    #conversion_factor = 3.3 / (65535)

    display = SSD1331Display(auto_refresh=False)
    
    palette = make_palette(32)
    bike = displayio.OnDiskBitmap("/bike.bmp")
    loop(display, palette, bike)
    
def loop(display, palette, bike, speed=1):
    global start_time_ms
    start_time_ms = round(time.monotonic() * 1000)
    print(f"Start time: {start_time_ms}")
    
    root = displayio.Group()
  
    
    # Set up moving lines
    lines = []
    num_lines = 18
    half_height = round(SCREEN_HEIGHT / 2) - 10
    
    horiz = displayio.Bitmap(SCREEN_WIDTH, 1, 32)
    horiz.fill(0)
    root.append(FineTileGrid(horiz, pixel_shader=palette, y=half_height))
    horiz_lines = displayio.Group()
    for i in range(num_lines):
        bitmap = displayio.Bitmap(SCREEN_WIDTH, 1, 32)
        bitmap.fill(i)
        # start_y = round((i ** 2) / 1.3) + half_height
        start_y = half_height
        
        grid = FineTileGrid(bitmap, pixel_shader=palette,  y=start_y)
        grid.fine_y = start_y
        
        lines.append(grid)
        horiz_lines.append(grid)
        
        
    # Add bike
    bike.pixel_shader.make_transparent(2)
    
    # Set starting position for lines
    line_y = SCREEN_HEIGHT

    # show root Display group 
    
    # print(dir(display))
    
    draw_vert_lines(root, half_height)
    
    root.append(horiz_lines)
    root.append(displayio.TileGrid(bike, pixel_shader=bike.pixel_shader, x=43, y=34))
  
    display.show(root)
        
    # Loop to update position of lines
    while True:        
        draw_horiz_lines(half_height, lines)
        display.refresh()
        # vertical lines
        
                
        #time.sleep(0.01)
            
    # Wait for next update
    
def draw_horiz_lines(half_height, lines):
    global start_time_ms
    global_speed = 1.437
    
    line_freq = 220
    
    
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
                
                # reorder array
                #newids = list(range(1,len(lines)))
                #newids.append(0)
                
                #lines = [lines[i] for i in newids]
                # lines[0], lines[i] = lines[i], lines[0]
         
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
            color = (color / max_y) * 32

            lines[i].bitmap.fill(round(color))
            lines[i].y = round(lines[i].fine_y)
        
    return
    
def draw_vert_lines(root, half_height):
    lineGroup = displayio.Group()

    spacing = 10
    for i in range(-16,16):
        line = Line(round(SCREEN_WIDTH/2) + i, half_height, round(SCREEN_WIDTH/2) + i * spacing, SCREEN_HEIGHT, 0x00FFFF)
        lineGroup.append(line)
        
    root.append(lineGroup)
    
def make_palette(num_colors):
    # Set up color palette
    palette = displayio.Palette(num_colors)

    # Set starting and ending colors
    start_color = 0xFF00FF
    end_color = 0x00FFFF

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
    
if __name__ == "__main__":
    main()
