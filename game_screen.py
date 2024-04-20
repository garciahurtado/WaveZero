import gc
import random

import utime as time
import math
import uasyncio as asyncio

from asyncio_stoppable import Stoppable
from crash_effect import DeathEffect
from player_sprite import PlayerSprite
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

class GameScreen(Screen):
    display: None
    grid: None
    camera: None
    sprites: []
    enemies: []
    ui: ui_screen
    crash_fx: None
    sprite_max_z = 2000
    ground_speed = 0
    max_ground_speed = 10

    # Bike movement
    bike: PlayerSprite
    current_enemy_lane = 0


    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        gc.collect()
        print(f"Free memory __init__: {gc.mem_free():,} bytes")
        self.ground_speed = self.max_ground_speed
        self.preload_images()

    def preload_images(self):
        self.bike = PlayerSprite()
        self.crash_fx = DeathEffect(self.display, self.bike)

    def run(self):
        gc.collect()
        print(f"Free memory before main loop:  {gc.mem_free():,} bytes")

        self.ui = ui_screen(self.display)
        asyncio.run(self.main_async())

    async def main_async(self):
        sun_x_start = 39
        sun = Sprite("/img/sunset.bmp")
        sun.x = 39
        sun.y = 7
        self.add(sun)

        # show_title(display, root)

        encoder = Encoder(27, 26)
        last_pos = {'pos': 0}

        # Camera
        horiz_y = 16
        camera_z = 72

        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=64,
            pos_z=-camera_z,
            focal_length=camera_z,
            vp_x=0,
            vp_y=horiz_y)
        self.camera.horiz_z = self.sprite_max_z

        self.grid = RoadGrid(self.camera, self.display, lane_width=22)

        loop = asyncio.get_event_loop()

        self.update_task = loop.create_task(self.update_loop(sun, sun_x_start))
        self.display_task = loop.create_task(self.refresh_display())

        await asyncio.gather(
            self.update_fps(),
            self.get_input(encoder, last_pos))

    async def update_loop(self, sun, sun_x_start):
        lane_width = self.grid.lane_width
        loop = asyncio.get_event_loop()

        start_time_ms = round(time.ticks_ms())
        print(f"Start time: {start_time_ms}")

        # 2D Y coordinate at which obstacles will crash with the player
        crash_y = 70
        lane_width = 20

        # Create road obstacles
        self.enemies = []
        num_enemies = 30

        enemy = Spritesheet("/img/road_wall.bmp", 10, 20)
        enemy.set_camera(self.camera)
        enemy.set_alpha(1)
        enemy.x = -16
        enemy.y = 0
        enemy.z = self.sprite_max_z
        enemy.is3d = True
        enemy.speed = -self.ground_speed
        enemy.set_frame(0)
        enemy.lane_width = lane_width

        obs_colors = [0x00f6ff, 0x00dff9, 0x00c8f1, 0x00b1e8, 0x009add, 0x0083cf, 0x006cbf, 0x0055ac, 0x003e96,
                      0x00267d]

        # Create a number of road obstacles by cloning
        for i in range(num_enemies):
            new_enemy = enemy.clone()
            new_enemy.z = 1000 + (int(i/2) * 50)
            # new_enemy.x = int(new_enemy.x + (random.randrange(0,5) * 16))
            my_x = self.current_enemy_lane * lane_width
            new_enemy.x = my_x
            palette_len = len(obs_colors)
            new_enemy.palette.set_color(0, colors.hex_to_rgb(obs_colors[i%palette_len]))

            self.enemies.insert(0, new_enemy)  # prepend, so they will be drawn in the right order

        for one_sprite in self.enemies:
            self.add(one_sprite)

        self.add(self.bike) # Add after the obstacles, to it appears on top
        bike_angle = 0
        turn_incr = 0.2  # turning speed
        half_width = int(self.camera.half_width)

        # Draw loop - will run until program exit
        while True:
            #self.camera.yaw = self.camera.yaw + 1

            # print("Free memory: {} bytes".format(gc.mem_free()) )

            # Turn the bike automatically
            # bike_angle = math.sin(now / 1000) # (-1,1)

            # Handle bike swerving
            target_lane = self.bike.target_lane
            current_lane = self.bike.current_lane
            target_angle = (target_lane * (2 / 4)) - 1

            if target_lane < current_lane:
                bike_angle = bike_angle - turn_incr
                if bike_angle < target_angle:
                    self.bike.current_lane = target_lane
                    bike_angle = target_angle

                bike_angle = max(bike_angle, -1)  # Clamp the input between -1 and 1

            elif target_lane > current_lane:
                bike_angle = bike_angle + turn_incr
                if bike_angle > target_angle:
                    self.bike.current_lane = target_lane
                    bike_angle = target_angle

                bike_angle = min(bike_angle, 1)  # Clamp the input between -1 and 1

            line_offset = self.bike.turn(bike_angle)  # range(-1,1)
            self.bike.x = int((line_offset * 30) + half_width - 18)
            self.bike.update()

            # REFACTOR
            self.camera.vp["x"] = int(bike_angle * 10)  # So that 3D sprites will follow the movement of the road
            self.camera.pos["x"] = int(bike_angle * 5)
            sun.x = sun_x_start - self.camera.pos["x"]

            for sprite in self.sprites:
                sprite.update()

            # Move the road sprites
            for sprite in self.enemies:

                # Check collisions
                if (    (sprite.draw_y >= crash_y) and
                        (sprite.get_lane() == self.bike.current_lane) and
                        not self.bike.invisible and
                        not self.bike.blink):

                    self.do_crash()
                    self.ui.remove_life()
                    self.bike.blink = True
                    await loop.create_task(self.bike.stop_blink()) # Will run after a few seconds


            await asyncio.sleep(1 / 90)

        # Wait for next update

    def do_refresh(self):
        """ Overrides parent method """
        self.display.fill(0)
        self.grid.show()
        self.draw_sprites()
        super().do_refresh()

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
                self.bike.move_left()
                last_pos['pos'] = position
            elif position < last_pos['pos']:
                self.bike.move_right()
                last_pos['pos'] = position

            await asyncio.sleep(0.01)


    def create_road_sprite(self, x, y, z, bitmap=None, palette=None, camera=None, i=0):
        # self.enemies

        palette.make_transparent(2)
        grid = TileGrid(bitmap, pixel_shader=palette, x=0, y=0, tile_width=10, tile_height=20)
        grid[0] = 8

        # Will be used by displayio to render the bitmap
        sprite = PerspectiveSprite(grid, x=x, y=y, z=z, camera=camera)
        road_sprites.append(sprite)  # Will be used to update sprite coordinates

        return grid

    def make_palette_from_img(self):
        bitmap, palette = adafruit_imageload.load(
            "/img/horizon_gradient.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)
        print(palette.__version__)
        palette._colors.sort()

        return palette

    def draw_sprites(self):
        super().draw_sprites()
        self.ui.draw_sprites()


if __name__ == "__main__":
    # scr = GameScreen()
    scr = TitleScreen()
    scr.run()
