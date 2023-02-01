from display_ssd1331 import SSD1331Display
from displayio import Group, Bitmap, TileGrid, Palette

import gc
import time
import math
import random
import board
import adafruit_imageload
from adafruit_datetime import datetime
from adafruit_display_shapes.rect import Rect

import bitmaptools
import framebufferio
import ulab.numpy as np
import bitops
import asyncio

from fine_tile_grid import FineTileGrid
from title_screen import show_title
import ui_elements as ui
from road_grid import RoadGrid
from perspective_sprite import PerspectiveSprite
from fps_counter import FpsCounter

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64
start_time_ms = 0
line_cache = {}
road_sprites = []

def main():
    asyncio.run(main_async())
    
async def main_async():
    display = SSD1331Display(auto_refresh=False)
    
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
    
    fps = FpsCounter()
    await asyncio.gather(update_loop(display, root, bike, bike_anim, fps=fps), refresh_display(display, fps=fps))

    
async def update_loop(display, root, bike, bike_anim, speed=1, fps=None):
    start_time_ms = round(time.monotonic() * 1000)
    print(f"Start time: {start_time_ms}")
    
    score = 0
    score_text = ui.init_score(root)
    ui.draw_lives(root)
    ui.draw_score(score, score_text)
    draw_sun(root)
    

    # Set up vertical and horizontal lines
    horiz_y = 16
    grid = RoadGrid(horiz_y)
    root.append(grid.vert_lines)
    root.append(grid.horiz_lines)
    
    root.append(bike)  
    
    x1_offset = 0
    x2_offset = 0

    bike_angle = 0
    
    fps_list_max = 30
    fps_list = np.zeros(fps_list_max, dtype=np.uint16)
    fps_list_index = 0
    
    last_frame_ms = round(time.monotonic() * 1000)
    
    # Some fake obstacles 
    bitmap, palette = adafruit_imageload.load("/img/road_wall.bmp")
    for j in range (0,1):
        for i in range(100, 0, -10):
            x = i
            road_sprite = create_road_sprite(x=20, y=0+(j*30), z=1500+ (i*2), horiz_y=horiz_y, bitmap=bitmap, palette=palette)
            root.append(road_sprite)
    
    display.show(root)
    
    
    # Loop to update position of lines
    while True:
        #gc.collect()
        #print("Free memory: {} bytes".format(gc.mem_free()) )

        now = time.monotonic() * 1000
        score = round(fps.fps())
        
        line_offset = turn_bike(bike, bike_angle)
        bike_angle = math.sin(now / 1000)
        
        x1_offset = line_offset * 40       
        x2_offset = -line_offset * 12

        bike.x = math.floor((line_offset * 30)) + round(SCREEN_WIDTH / 2) - 18
                 
        grid.update_vert_lines(turn_offset=x2_offset)
        grid.draw_horiz_lines()
        
        for sprite in road_sprites:
            sprite.z = sprite.z - 20
            # print(f"x: {sprite.x} y: {sprite.y} z: {sprite.z}")
        
        ui.draw_score(score, score_text)
        
        await asyncio.sleep(0.0001)
            
    # Wait for next update

      
async def refresh_display(display, fps):
    while True:
        display.refresh(target_frames_per_second=20)
        fps.tick()
        await asyncio.sleep(0.001)
    
    
def create_road_sprite(x, y, z, horiz_y, bitmap=None, palette=None):
    global road_sprites

    rand_colors = [0xFF0000, 0x00FF00, 0x0000FF, 0xFFFF00, 0x00FFFF, 0xFF00FF]
    # palette[1] = rand_colors[random.randrange(len(rand_colors))]
    
    palette.make_transparent(2)
    grid = TileGrid(bitmap, pixel_shader=palette, x=0, y=0, tile_width=10, tile_height=10)
    grid[0] = 8

    # Will be used by displayio to render the bitmap
    sprite = PerspectiveSprite(grid, x=x, y=y, z=z, horiz_y=horiz_y)
    road_sprites.append(sprite) # Will be used to update sprite coordinates 
    
    return grid
    
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


def make_palette_from_img():

    bitmap, palette = adafruit_imageload.load(
    "/img/horizon_gradient.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)
    print(palette.__version__)
    palette._colors.sort()
    
    return palette

if __name__ == "__main__":
    main()
