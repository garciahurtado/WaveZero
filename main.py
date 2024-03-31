from display_ssd1331 import SSD1331Display
from displayio import Group, Bitmap, TileGrid, Palette

import gc
import time
import math
import random
import board
import adafruit_imageload
from adafruit_display_shapes.rect import Rect

import bitmaptools
import framebufferio
import ulab.numpy as np
import bitops
import asyncio
import rotaryio

from fine_tile_grid import FineTileGrid
from title_screen import show_title
import ui_elements as ui
from road_grid import RoadGrid
from perspective_sprite import PerspectiveSprite
from perspective_camera import PerspectiveCamera
from fps_counter import FpsCounter
import death_effect as death

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64
start_time_ms = 0
line_cache = {}
road_sprites = []

# Bike movement
current_lane = 2
target_lane = 2

def main():
    asyncio.run(main_async())
    
async def main_async():
    display = SSD1331Display()
    
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
    
    encoder = rotaryio.IncrementalEncoder(board.GP27, board.GP26)
    last_pos = {'pos':0}
    
    fps = FpsCounter()
    await asyncio.gather(
        update_loop(display, root, bike, bike_anim, last_pos, fps=fps),
        refresh_display(display, fps=fps),
        get_input(encoder, last_pos))

async def get_input(encoder, last_pos):
    while True:
        position = encoder.position
        if position < last_pos['pos']:
            move_left()
        elif position > last_pos['pos']:
            move_right()
            
        last_pos['pos'] = position
        
        await asyncio.sleep(0.0001)

def move_left():
    global current_lane, target_lane
    
    if current_lane == 0:
        return
    
    if current_lane == target_lane:
        target_lane = current_lane - 1
    else:
        if target_lane > 0:
            target_lane -= 1
        
def move_right():
    global current_lane, target_lane
    
    if current_lane == 4:
        return
    
    if current_lane == target_lane:
        target_lane = current_lane + 1
    else:
        if target_lane < 4:
            target_lane += 1
        
    
async def update_loop(display, root, bike, bike_anim, rot_input, speed=1, fps=None):
    global target_lane, current_lane
    
    start_time_ms = round(time.monotonic() * 1000)
    print(f"Start time: {start_time_ms}")

    
    # Sunset
    sun = draw_sun()
    sun_x = sun.x

    # 2D Y coordinate at which obstacles will crash with the player
    crash_y = 50
    
    # Camera
    horiz_y = 16
    camera = PerspectiveCamera(SCREEN_WIDTH, SCREEN_HEIGHT, vp_x=round(SCREEN_WIDTH / 2), vp_y=horiz_y)

    # Set up vertical and horizontal lines
    
    grid = RoadGrid(camera)
    vert_lines = Group()
    for line in grid.vert_lines:
        vert_lines.append(line)

    root.append(grid.horiz_lines_grid)
    root.append(vert_lines)
    root.append(sun)

    root.append(bike)

    # Score
    score = 0
    score_text = ui.init_score(root)
    ui.draw_lives(root)
    ui.draw_score(score, score_text)

    
    fps_list_max = 30
    fps_list = np.zeros(fps_list_max, dtype=np.uint16)
    fps_list_index = 0
    
    last_frame_ms = round(time.monotonic() * 1000)
    
    # Some fake obstacles 
    bitmap, palette = adafruit_imageload.load("/img/road_wall.bmp")
    
    for i in range(5, 0, -1):
        
        all_colors = [0x00f6ff,0x00dff9,0x00c8f1,0x00b1e8,0x009add,0x0083cf,0x006cbf,0x0055ac,0x003e96,0x00267d]
        
        # clone the base palette
        palette_colors = [color for color in palette] 
        new_palette = Palette(len(palette_colors))
        for ii, color in enumerate(palette_colors):
            new_palette[ii] = color
    
            
        # Unique color to this sprite
        new_palette[1] = all_colors[i - 1]
    
        road_sprite = create_road_sprite(
            x=20,
            y=0,
            z=1500 + (i*25),
            bitmap=bitmap,
            palette=new_palette,
            camera=camera)
        root.append(road_sprite)
    
    #display.show(root)
    display.root_group = root
    vp_x = camera.vp["x"]
    bike_angle = 0
    x_offset_3d = 16
    turn_incr = 0.3  # turning speed
    
    # Loop to update position of lines
    while True:
        #gc.collect()
        #print("Free memory: {} bytes".format(gc.mem_free()) )

        now = time.monotonic() * 1000
        score = round(fps.fps())
  
        # Turn the bike automatically
        #bike_angle = math.sin(now / 1000) # (-1,1)

        # Handle bike swerving

        target_angle = (target_lane * (2/4)) - 1
        
        if target_lane < current_lane:
            bike_angle = bike_angle - turn_incr
            if bike_angle < target_angle:
                current_lane = target_lane
                bike_angle = target_angle
        elif target_lane > current_lane:
            bike_angle = bike_angle + turn_incr
            if bike_angle > target_angle:
                current_lane = target_lane
                bike_angle = target_angle
            
        bike_angle = sorted((-1, bike_angle, 1))[1] # Clamp the input
  
        line_offset = turn_bike(bike, bike_angle) # range(-1,1)
        bike.x = math.floor((line_offset * 30)) + round(SCREEN_WIDTH / 2) - 18
                 
            
        horiz_offset = grid.update_vert_lines(turn_offset=line_offset * 12)
        camera.vp["x"] = vp_x + (horiz_offset + x_offset_3d) # So that 3D sprites will follow the movement of the road
        sun.x = sun_x - round(bike_angle * 8)
        grid.draw_horiz_lines()
        
        for sprite in road_sprites:
            sprite.z = sprite.z - 15
            
            # Check collisions
            #print(f"x: {sprite.x} y: {sprite.y} z: {sprite.z}")
            
            if (sprite.sprite_grid.y > crash_y) and (sprite.get_lane(x_offset_3d) == current_lane):
                particles, grid = death.create_particles(bike.bitmap, root)
                death.anim_particles(particles, display, grid)

        
        ui.draw_score(score, score_text)
        
        await asyncio.sleep(0.00001)
            
    # Wait for next update

      
async def refresh_display(display, fps):
    while True:
        display.refresh(target_frames_per_second=60)
        fps.tick()
        await asyncio.sleep(0.00001)
    
    
def create_road_sprite(x, y, z, bitmap=None, palette=None, camera=None, i=0):
    global road_sprites
    
    palette.make_transparent(2)
    grid = TileGrid(bitmap, pixel_shader=palette, x=0, y=0, tile_width=10, tile_height=20)
    grid[0] = 8

    # Will be used by displayio to render the bitmap
    sprite = PerspectiveSprite(grid, x=x, y=y, z=z, camera=camera)
    road_sprites.append(sprite) # Will be used to update sprite coordinates 
    
    return grid
    
def draw_sun():
    sunset_bitmap, sunset_palette = adafruit_imageload.load(
    "/img/sunset.bmp", bitmap=Bitmap, palette=Palette
)
    
    #sunset_palette.make_transparent(0)
    grid = TileGrid(sunset_bitmap, pixel_shader=sunset_palette, x=39, y=5)
    
    return grid
    
def turn_bike(bike, angle):
    new_frame = round(((angle * 16) + 17) / 2)
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
