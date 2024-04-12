import gc
import utime as time
import math

# from ulab import numpy as np
# import bitops
import uasyncio as asyncio

# from fine_tile_grid import FineTileGrid
# from title_screen import show_title
from ui_elements import ui
from road_grid import RoadGrid
from perspective_sprite import PerspectiveSprite
from perspective_camera import PerspectiveCamera
from fps_counter import FpsCounter
# import death_effect as death
from encoder import Encoder
from sprite import Sprite, Spritesheet, ImageLoader
import machine
from machine import Pin
from lib.ssd1331_16bit import SSD1331 as SSD

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64
start_time_ms = 0
line_cache = {}
line_cache = {}
road_sprites = []

# Bike movement
current_lane = 2
target_lane = 2


class GameScreen():
    display: None

    def __init__(self):
        print(f"Free memory __init__: {gc.mem_free():,} bytes")

        self.preload_images()

    def preload_images(self):
        pass

    def run(self):
        asyncio.run(self.main_async())

    async def main_async(self):
        self.preload_images()

        display = self.setup_display()
        screen = ui(self.display)

        bike_anim = 8
        bike = Spritesheet("/img/bike_sprite.bmp", 37, 22)
        bike.set_alpha()
        bike.set_frame(8)  # middle frame
        bike.x = 25
        bike.y = 42
        screen.add(bike)

        # bike_img = None

        # bike_palette.make_transparent(172) # index of #333333
        # bike = TileGrid(bike_bitmap, pixel_shader=bike_palette, x=32, y=42, tile_width=37, tile_height=22)
        # bike[0] = bike_anim

        sun_img = Sprite("/img/sunset.bmp")
        sun_img.x = 39
        sun_img.y = 5
        sun_x_start = 39

        # show_title(display, root)
        gc.collect()
        print(f"Free memory before main loop:  {gc.mem_free():,} bytes")

        encoder = Encoder(27, 26)
        last_pos = {'pos': 0}

        fps = FpsCounter()
        await asyncio.gather(
            self.update_loop(screen, bike, sun_img, sun_x_start, last_pos, fps=fps),
            self.refresh_display(display, fps=fps),
            self.get_input(encoder, last_pos))


    def setup_display(self):
        # Pin layout for SSD1331 64x48 OLED display on Raspberry Pi Pico (SPI0)
        # GPIO1 (SPI0 CS)       CS
        # GPIO2 (SPI0 SCK)      SCL
        # GPIO3 (SPI0 TX)       SDA
        # GPIO4 (or any)        RES
        # GPIO5 (or any)        DC

        pin_cs = Pin(1, Pin.OUT)
        pin_sck = Pin(2, Pin.OUT)
        pin_sda = Pin(3, Pin.OUT)
        pin_rst = Pin(4, Pin.OUT, value=0)
        pin_dc = Pin(5, Pin.OUT, value=0)

        spi = machine.SPI(0, baudrate=24_000_000, sck=pin_sck, mosi=pin_sda, miso=None)
        ssd = SSD(spi, pin_cs, pin_dc, pin_rst, height=64, width=96)  # Create a display instance

        self.display = ssd
        return ssd


    async def get_input(self, encoder, last_pos):
        while True:
            position = encoder.value
            if position > last_pos['pos']:
                self.move_left()
                last_pos['pos'] = position
            elif position < last_pos['pos']:
                self.move_right()
                last_pos['pos'] = position

            await asyncio.sleep(0.0001)


    def move_left(self):
        global current_lane, target_lane

        if current_lane == 0:
            return

        if current_lane == target_lane:
            target_lane = current_lane - 1
        else:
            if target_lane > 0:
                target_lane -= 1


    def move_right(self):
        global current_lane, target_lane

        if current_lane == 4:
            return

        if current_lane == target_lane:
            target_lane = current_lane + 1
        else:
            if target_lane < 4:
                target_lane += 1


    async def update_loop(self, screen, bike, sun_image, sun_x_start, rot_input, speed=1, fps=None):
        global target_lane, current_lane
        BLACK = self.display.rgb(0, 0, 0)
        speed = 2
        sprite_max_z = 3000
        screen.add(sun_image)

        start_time_ms = round(time.ticks_ms())
        print(f"Start time: {start_time_ms}")

        # 2D Y coordinate at which obstacles will crash with the player
        crash_y = 50

        # Camera
        horiz_y = 16
        camera = PerspectiveCamera(
            SCREEN_WIDTH,
            SCREEN_HEIGHT,
            pos_x=0,
            pos_y=64,
            pos_z=-64,
            vp_x=0,
            vp_y=horiz_y)
        camera.horiz_z = sprite_max_z

        grid = RoadGrid(camera, screen.display)

        # Score
        score = 0
        screen.init_score()
        screen.draw_lives()

        fps_list_max = 30
        # fps_list = np.zeros(fps_list_max, dtype=np.uint16)
        fps_list = []
        fps_list_index = 0

        last_frame_ms = time.ticks_ms()

        # Some fake obstacles
        # bitmap, palette = adafruit_imageload.load("/img/road_wall.bmp")
        obstacle = Sprite("/img/road_wall.bmp")
        road_sprites = []
        num_obstacles = 6

        obstacle = Spritesheet("/img/road_wall.bmp", 10, 20)
        obstacle.camera = camera
        obstacle.set_alpha(1)
        obstacle.x = 0
        obstacle.y = 0
        obstacle.z = sprite_max_z
        obstacle.set_frame(0)

        # Create a number of road obstacles by cloning
        for i in range(num_obstacles):
            new_obs = obstacle.clone()
            new_obs.z = 500 + (i * 50)

            road_sprites.insert(0, new_obs) # prepend, so they will be drawn in the right order

            # all_colors = [0x00f6ff,0x00dff9,0x00c8f1,0x00b1e8,0x009add,0x0083cf,0x006cbf,0x0055ac,0x003e96,0x00267d]

            # clone the base palette
            #          palette_colors = [color for color in palette]
            #          new_palette = []
            #          for ii, color in enumerate(palette_colors):
            #              new_palette[ii] = color

            # Unique color to this sprite
            # new_palette[1] = all_colors[i - 1]

        for one_sprite in road_sprites:
            screen.add(one_sprite)

        vp_x = camera.vp["x"]
        bike_angle = 0
        x_offset_3d = -27  # correct perspective manually to make sure center position is simetrical
        turn_incr = 0.3  # turning speed

        # Draw loop - will run until program exit
        while True:
            # gc.collect()
            # print("Free memory: {} bytes".format(gc.mem_free()) )
            self.display.fill(BLACK)

            now = time.ticks_ms()
            # score = round(fps.fps())

            # Turn the bike automatically
            # bike_angle = math.sin(now / 1000) # (-1,1)

            screen.draw_lives()
            grid.draw_horiz_lines()
            grid.draw_vert_lines()

            # Handle bike swerving
            target_angle = (target_lane * (2 / 4)) - 1

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

            bike_angle = sorted((-1, bike_angle, 1))[1]  # Clamp the input

            line_offset = self.turn_bike(bike, bike_angle)  # range(-1,1)
            bike.x = math.floor((line_offset * 30)) + round(SCREEN_WIDTH / 2) - 18

            # REFACTOR
            camera.vp["x"] = round(bike_angle * 12)  # So that 3D sprites will follow the movement of the road
            camera.pos["x"] = round(bike_angle * 30)

            # Move the road sprites
            for sprite in road_sprites:
                sprite.z = sprite.z - 10 * speed
                x, y = sprite.pos()

                if y < 0 or sprite.z <= sprite.camera.pos['z']:
                    sprite.z = sprite_max_z


                sprite.update_frame()

                # Check collisions
                # print(f"x: {sprite.x} y: {sprite.y} z: {sprite.z}")

                # if (sprite.sprite_grid.y > crash_y) and (sprite.get_lane(x_offset_3d) == current_lane):
                #     particles, grid = death.create_particles(bike.bitmap, root)
                #     death.anim_particles(particles, display, grid)

            # Show the FPS in the score label
            screen.draw_score(int(fps.fps()))
            screen.draw_sprites()
            sun_image.x = sun_x_start - int(camera.pos["x"] * 1)

            await asyncio.sleep(1 / 60)

        # Wait for next update


    async def refresh_display(self, display, fps):
        while True:
            display.show()
            fps.tick()
            await asyncio.sleep(0.001)


    def create_road_sprite(self, x, y, z, bitmap=None, palette=None, camera=None, i=0):
        global road_sprites

        palette.make_transparent(2)
        grid = TileGrid(bitmap, pixel_shader=palette, x=0, y=0, tile_width=10, tile_height=20)
        grid[0] = 8

        # Will be used by displayio to render the bitmap
        sprite = PerspectiveSprite(grid, x=x, y=y, z=z, camera=camera)
        road_sprites.append(sprite)  # Will be used to update sprite coordinates

        return grid


    def turn_bike(self, bike: Spritesheet, angle):
        new_frame = round(((angle * 16) + 17) / 2)
        if bike.current_frame != new_frame:
            bike.set_frame(new_frame)

        line_offset = angle
        return line_offset


    def make_palette_from_img(self):
        bitmap, palette = adafruit_imageload.load(
            "/img/horizon_gradient.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)
        print(palette.__version__)
        palette._colors.sort()

        return palette

if __name__ == "__main__":
    scr = GameScreen()
    scr.run()
