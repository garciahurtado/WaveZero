import gc
import random

import utime as time
import math
import uasyncio as asyncio

from asyncio_stoppable import Stoppable
from crash_effect import DeathEffect
from screen import Screen
from road_grid import RoadGrid
from perspective_sprite import PerspectiveSprite
from perspective_camera import PerspectiveCamera
from encoder import Encoder
from sprite import Sprite, Spritesheet
from title_screen import TitleScreen
import color_util as colors
from ui_elements import ui_screen

start_time_ms = 0
line_cache = {}
line_cache = {}
road_sprites = []

# Bike movement
current_lane = 2
target_lane = 2


class GameScreen(Screen):
    display: None
    grid: None
    camera: None
    sprites: []
    enemies: []
    ui: ui_screen
    bike: Sprite
    crash_fx: None
    sprite_max_z = 2000
    ground_speed = 0
    max_ground_speed = 20

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        gc.collect()
        print(f"Free memory __init__: {gc.mem_free():,} bytes")
        self.ground_speed = self.max_ground_speed
        self.preload_images()

    def preload_images(self):
        bike = Spritesheet("/img/bike_sprite.bmp", 37, 22)
        bike.set_alpha(0)
        bike.set_frame(8)  # middle frame
        bike.x = 25
        bike.y = 42
        self.bike = bike

        self.crash_fx = DeathEffect(self.display, self.bike)
        self.add(bike)

    def run(self):
        self.ui = ui_screen(self.display)
        asyncio.run(self.main_async())

    async def main_async(self):
        sun_x_start = 39
        sun_img = Sprite("/img/sunset.bmp")
        sun_img.x = 39
        sun_img.y = 5
        self.add(sun_img)

        # show_title(display, root)
        gc.collect()
        print(f"Free memory before main loop:  {gc.mem_free():,} bytes")

        encoder = Encoder(27, 26)
        last_pos = {'pos': 0}

        # Camera
        horiz_y = 16
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=64,
            pos_z=-64,
            vp_x=0,
            vp_y=horiz_y)
        self.camera.horiz_z = self.sprite_max_z

        self.grid = RoadGrid(self.camera, self.display)

        loop = asyncio.get_event_loop()

        self.display_task = loop.create_task(self.refresh_display())
        self.update_task = loop.create_task(self.update_loop(sun_img, sun_x_start))

        await asyncio.gather(
            self.update_fps(),
            self.get_input(encoder, last_pos))

    async def update_loop(self, sun_image, sun_x_start):
        global target_lane, current_lane
        BLACK = self.display.rgb(0, 0, 0)

        start_time_ms = round(time.ticks_ms())
        print(f"Start time: {start_time_ms}")

        # 2D Y coordinate at which obstacles will crash with the player
        crash_y = 70

        # Create road obstacles
        self.enemies = []
        num_obstacles = 20

        obstacle = Spritesheet("/img/road_wall.bmp", 10, 20)
        obstacle.set_camera(self.camera)
        obstacle.set_alpha(1)
        obstacle.x = -16
        obstacle.y = 0
        obstacle.z = self.sprite_max_z
        obstacle.is3d = True
        obstacle.speed = -self.ground_speed
        obstacle.set_frame(0)
        obstacle.lane_width = 8

        obs_colors = [0x00f6ff, 0x00dff9, 0x00c8f1, 0x00b1e8, 0x009add, 0x0083cf, 0x006cbf, 0x0055ac, 0x003e96,
                      0x00267d]

        # Create a number of road obstacles by cloning
        for i in range(num_obstacles):
            new_obs = obstacle.clone()
            new_obs.z = 1000 + (i * 50)
            new_obs.x = int(new_obs.x + (random.randrange(0,5) * 16))
            palette_len = len(obs_colors)
            new_obs.palette.set_color(0, colors.hex_to_rgb(obs_colors[i%palette_len]))

            self.enemies.insert(0, new_obs)  # prepend, so they will be drawn in the right order

        for one_sprite in self.enemies:
            self.add(one_sprite)

        bike_angle = 0
        turn_incr = 0.2  # turning speed
        half_width = int(self.camera.half_width)

        # Draw loop - will run until program exit
        while True:
            # gc.collect()
            # print("Free memory: {} bytes".format(gc.mem_free()) )

            # Turn the bike automatically
            # bike_angle = math.sin(now / 1000) # (-1,1)

            # Handle bike swerving
            target_angle = (target_lane * (2 / 4)) - 1

            if target_lane < current_lane:
                bike_angle = bike_angle - turn_incr
                if bike_angle < target_angle:
                    current_lane = target_lane
                    bike_angle = target_angle

                bike_angle = max(bike_angle, -1)  # Clamp the input between -1 and 1

            elif target_lane > current_lane:
                bike_angle = bike_angle + turn_incr
                if bike_angle > target_angle:
                    current_lane = target_lane
                    bike_angle = target_angle

                bike_angle = min(bike_angle, 1)  # Clamp the input between -1 and 1

            line_offset = self.turn_bike(self.bike, bike_angle)  # range(-1,1)
            self.bike.x = int((line_offset * 30) + half_width - 18)
            self.bike.update()

            # REFACTOR
            self.camera.vp["x"] = int(bike_angle * 10)  # So that 3D sprites will follow the movement of the road
            self.camera.pos["x"] = int(bike_angle * 5)
            sun_image.x = sun_x_start - self.camera.pos["x"]

            for sprite in self.sprites:
                sprite.update()

            # Move the road sprites
            for sprite in self.enemies:

                # Check collisions
                if (sprite.draw_y >= crash_y) and (sprite.get_lane() == current_lane):
                    self.do_crash()

            await asyncio.sleep(1 / 90)

        # Wait for next update

    def do_crash(self):
        print("CRASH")
        self.display_task.cancel()
        self.grid.global_speed = self.ground_speed = 0

        white = colors.rgb_to_565(colors.hex_to_rgb(0xFFFFFF))

        for i in range(3):
            self.display.fill(white)
            self.display.show()
            self.do_refresh()

        self.crash_fx.create_particles()

        self.crash_fx.anim_particles()

        print("Crash ended")
        self.reset_game()

        # Restart the game display
        self.display_task = asyncio.get_event_loop().create_task(self.refresh_display())

    def reset_game(self):
        """After losing a life, we reset all the obstacle sprites and the speed"""

        for sprite in self.enemies:
            sprite.z = self.sprite_max_z

        self.grid.global_speed = self.ground_speed = self.max_ground_speed

    async def update_fps(self):
        while True:
            # Show the FPS in the score label
            fps = int(self.fps.fps())
            self.ui.update_score(fps)

            await asyncio.sleep(0.2)

    async def get_input(self, encoder, last_pos):
        while True:
            position = encoder.value
            if position > last_pos['pos']:
                self.move_left()
                last_pos['pos'] = position
            elif position < last_pos['pos']:
                self.move_right()
                last_pos['pos'] = position

            await asyncio.sleep(0.01)

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
    def move_right(self):
        global current_lane, target_lane

        if current_lane == 4:
            return

        if current_lane == target_lane:
            target_lane = current_lane + 1
        else:
            if target_lane < 4:
                target_lane += 1

    def create_road_sprite(self, x, y, z, bitmap=None, palette=None, camera=None, i=0):
        # self.enemies

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
    # scr = GameScreen()
    scr = TitleScreen()
    scr.run()
