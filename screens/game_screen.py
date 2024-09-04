import math
import random

from death_anim import DeathAnim
from sprites.sprite import Sprite
from sprites2.warning_wall import WarningWall
from stages.stage_1 import Stage1
from ui_elements import ui_screen
import color_util as colors

from anim.anim_attr import AnimAttr
from images.image_loader import ImageLoader
from sprites.player_sprite import PlayerSprite
from road_grid import RoadGrid

from input import make_input_handler
from perspective_camera import PerspectiveCamera
from screens.screen import Screen
import uasyncio as asyncio
import utime

from sprites2.sprite_manager import SpriteManager
from collider import Collider
from sprites2.sprite_types import *
from sprites2.laser_wall import LaserWall

from profiler import Profiler as prof

class GameScreen(Screen):
    ground_speed: int = const(-0)
    max_ground_speed: int = const(-2000)
    grid: RoadGrid = None
    sun: Sprite = None
    sun_start_x = None
    camera: PerspectiveCamera
    enemies: SpriteManager = None
    max_sprites: int = 200
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = const(2)
    total_frames = 0
    last_update_ms = 0
    fps_every_n_frames = 30
    player = None
    last_perf_dump_ms = 0
    input_task = None
    crash_y_start = const(46)  # Screen start Y of Sprites which will collide with the player
    crash_y_end = const(62)  # Screen end Y
    death_task = None
    paused = False
    fx_callback = None
    ui = None
    collider = None
    score = 0
    stage = None

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        display.fill(0x0000)
        display.show()

        self.init_camera()
        self.check_mem()

        print("-- Creating UI...")
        self.ui = ui_screen(display, self.num_lives)

        print("-- Preloading images...")
        self.preload_images()
        self.check_mem()

        self.check_mem()
        print("-- Creating player sprite...")
        self.player = PlayerSprite(camera=self.camera)

        self.collider = Collider(self.player, self.enemies, self.crash_y_start, self.crash_y_end)
        self.collider.add_callback(self.do_crash)

        print("-- Creating road grid...")
        self.grid = RoadGrid(self.camera, display, lane_width=self.lane_width)

        self.check_mem()
        print("-- Creating Sprite Manager...")
        self.enemies = SpriteManager(display, self.max_sprites, self.camera, self.lane_width, grid=self.grid)
        self.add(self.enemies)

        self.death_anim = DeathAnim(display)
        self.death_anim.callback = self.after_death

        self.check_mem()
        self.display.fps = self.fps

        self.stage = Stage1(self.enemies)

        self.check_mem()

    async def mock_update_score(self):
        while True:
            self.score += random.randrange(0, 100000)
            self.ui.update_score(self.score)
            await asyncio.sleep(1)

    def preload_images(self):
        images = [
            {"name": "bike_sprite.bmp", "width": 32, "height": 22, "color_depth": 4},
            # {"name": "holo_tri.bmp", "width": 20, "height": 20, "color_depth": 4},
            # {"name": "laser_wall.bmp", "width": 22, "height": 10, "color_depth": 4},
            {"name": "sunset.bmp", "width": 20, "height": 10, "color_depth": 8},
            {"name": "life.bmp", "width": 12, "height": 8},
            {"name": "debris_bits.bmp", "width": 4, "height": 4, "color_depth": 1},
            {"name": "debris_large.bmp", "width": 8, "height": 6, "color_depth": 1},
        ]

        ImageLoader.load_images(images, self.display)

    def run(self):
        self.display.fill(0x9999)
        utime.sleep_ms(1000)
        self.display.fill(0x0)

        barrier_speed = self.max_ground_speed / 200
        print(f"Sprite speed: {barrier_speed}")

        self.check_mem()

        sun = Sprite("/img/sunset.bmp")
        sun.x = self.sun_start_x = 39
        sun.y = 10
        self.add(sun)
        self.sun = sun

        self.check_mem()

        self.check_mem()
        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())

        self.input_task = make_input_handler(self.player)
        self.update_score_task = loop.create_task(self.mock_update_score())

        # Start the road speed-up task
        self.speed_anim = AnimAttr(self, 'ground_speed', self.max_ground_speed, 1500, easing=AnimAttr.ease_in_out_sine)
        loop.create_task(self.speed_anim.run(fps=60))

        self.player.has_physics = False
        self.player.visible = False

        print("-- Starting stage")
        self.stage.start()

        print("-- Starting update_loop")
        asyncio.run(self.start_main_loop())


    async def update_loop(self):
        start_time_ms = self.last_update_ms = round(utime.ticks_ms())
        self.last_perf_dump_ms = start_time_ms

        print(f"--- Update loop Start time: {start_time_ms}ms ---")
        self.check_mem()
        num_lanes = 5

        # update loop - will run until task cancellation
        try:
            while True:
                # Optimize: precompute num_lanes * bike_angle when bike_angle is being set
                self.camera.vp_x = round(self.player.turn_angle * num_lanes)
                self.camera.cam_x = round(self.player.turn_angle * num_lanes)

                self.grid.speed = self.ground_speed
                self.grid.speed_ms = self.ground_speed / 10
                self.total_frames += 1

                if not self.total_frames % self.fps_every_n_frames:
                    print(f"FPS: {self.fps.fps()}")

                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms)
                elapsed = elapsed / 1000 # @TODO change to MS?
                self.last_update_ms = now

                if not self.paused:
                    self.stage.update(elapsed)
                    self.grid.update_horiz_lines(elapsed)
                    self.player.update(elapsed)
                    self.sun.x = self.sun_start_x - round(self.player.turn_angle * 4)

                    for sprite in self.sprites:
                        sprite.update(elapsed)

                    self.collider.check_collisions(self.enemies.pool.active_sprites)

                # await self.show_perf()
                await asyncio.sleep(1/160)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """

        self.display.fill(0x0000)
        self.grid.show()
        self.show_all()
        self.player.show(self.display)
        self.show_fx()
        self.ui.show()

        self.display.show()

        self.fps.tick()

    def show_all(self):
        for sprite in self.sprites:
            sprite.show(self.display)

    def show_fx(self):
        self.death_anim.update_and_draw()

    def pause(self):
        self.paused = True
        self.player.active = False
        self.grid.stop()

    def start(self):
        self.paused = False
        self.player.visible = True
        self.player.start_blink()
        self.grid.start()

        loop = asyncio.get_event_loop()
        loop.create_task(self.player.stop_blink())

    def do_crash(self):
        # self.display_task.cancel()

        for i in range(2):
            self.display.fill(0xFFFF)
            self.display.show()
            self.do_refresh()

        self.pause()
        self.player.visible = False
        self.death_anim.start_animation(self.player.x, self.player.y)


    async def death_loop(self):
        while self.death_anim.running:
            await asyncio.sleep_ms(50)

    def after_death(self):
        loop = asyncio.get_event_loop()

        if self.num_lives == 0:
            self.player.visible = False
            self.ui.show_game_over()
        else:
            self.num_lives = self.num_lives - 1
            self.ui.update_lives(self.num_lives)
            self.start()

            return False

    def init_camera(self):
        # Camera
        horiz_y: int = 18
        camera_z: int = -40
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=60,
            pos_z=camera_z,
            vp_x=0,
            vp_y=horiz_y-6)

    async def show_perf(self):
        interval = 5000 # Every 5 secs

        now = int(utime.ticks_ms())
        elapsed = now - self.last_perf_dump_ms

        if elapsed > interval:
            prof.dump_profile()
            self.last_perf_dump_ms = int(utime.ticks_ms())
