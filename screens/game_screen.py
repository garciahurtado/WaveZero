import random

import micropython

from debug.mem_logging import log_mem, log_new_frame
from mpdb.mpdb import Mpdb
from scaler.const import DEBUG_INST, DEBUG, INK_MAGENTA, DEBUG_POOL, INK_BRIGHT_RED, INK_RED, DEBUG_MEM, INK_CYAN
from scaler.scaler_debugger import printc
from scaler.sprite_scaler import SpriteScaler
from perspective_camera import PerspectiveCamera
from death_anim import DeathAnim
from sprites.renderer_scaler import RendererScaler
from stages.stage_1 import Stage1
from ui_elements import ui_screen

from anim.anim_attr import AnimAttr
from images.image_loader import ImageLoader
from sprites_old.player_sprite import PlayerSprite
from road_grid import RoadGrid

from input.game_input import make_input_handler
from screens.screen import Screen
import uasyncio as asyncio
import utime

from sprites.sprite_manager_3d import SpriteManager3D
from collider import Collider
from sprites.sprite_types import *
from sprites_old.sprite import Sprite

from profiler import Profiler as prof
from micropython import const
from sprites.renderer_prescaled import RendererPrescaled
class GameScreen(Screen):
    fps_enabled = True
    ground_speed: int = 0
    max_ground_speed: int = const(-3000)
    grid: RoadGrid = None
    sun: Sprite = None
    sun_start_x = None
    camera: PerspectiveCamera
    enemies: SpriteManager3D = None
    max_sprites: int = 100
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = 4
    total_frames = 0
    last_update_ms = 0
    fps_every_n_frames = 30
    player = None
    last_perf_dump_ms = 0
    input_task = None
    input = None
    crash_y_start = const(52)  # Screen start Y of Sprites which will collide with the player
    crash_y_end = const(100)  # Screen end Y
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
        self.check_gc_mem()

        print("-- Preloading images...")
        self.preload_images()
        self.check_gc_mem()

        print("-- Creating UI...")
        self.ui = ui_screen(display, self.num_lives)

        self.check_gc_mem()
        print("-- Creating player sprite...")
        self.player = PlayerSprite(camera=self.camera)

        self.collider = Collider(self.player, self.enemies, self.crash_y_start, self.crash_y_end)
        self.collider.add_callback(self.do_crash)

        print("-- Creating road grid...")
        self.grid = RoadGrid(self.camera, display, lane_width=self.lane_width)

        self.check_gc_mem()
        print("-- Creating Enemy Sprite Manager...")

        # renderer = RendererPrescaled(display)
        renderer = RendererScaler(display)

        self.enemies = SpriteManager3D(
            display,
            renderer,
            max_sprites=self.max_sprites,
            camera=self.camera,
            grid=self.grid
        )

        # @refactor
        renderer.sprite_images = self.enemies.sprite_images
        renderer.sprite_palettes = self.enemies.sprite_palettes

        # DEBUG
        # mp_dbg = Mpdb()
        # mp_dbg.add_break('/lib/stages/stage.py:77', _self=self)
        # mp_dbg.add_break('/lib/sprites/sprite_manager_2d.py:77', _self=self)
        # mp_dbg.add_break('/lib/sprites/sprite_manager_3d.py:258', _self=self)
        # mp_dbg.set_trace()

        self.death_anim = DeathAnim(display)
        self.death_anim.callback = self.after_death

        self.check_gc_mem()
        self.display.fps = self.fps

        self.stage = Stage1(self.enemies)

        self.check_gc_mem()

        sun = Sprite("/img/sunset.bmp")
        sun.x = self.sun_start_x = 39
        sun.y = 11
        self.add_sprite(sun)
        self.add_sprite(self.enemies) # this is a sprite manager, but it knows how to render its own sprites

        self.sun = sun

    async def mock_update_score(self):
        while True:
            self.score += random.randrange(0, 100000)
            self.ui.update_score(self.score)
            await asyncio.sleep(1)

    def preload_images(self):
        images = [
            {"name": "bike_sprite.bmp", "width": 32, "height": 22, "color_depth": 4},
            # {"name": "laser_wall.bmp", "width": 24, "height": 10, "color_depth": 4},
            # {"name": "alien_fighter.bmp", "width": 24, "height": 16, "color_depth": 4},
            # {"name": "road_barrier_yellow.bmp", "width": 24, "height": 15, "color_depth": 4},
            # {"name": "road_barrier_yellow_inv.bmp", "width": 24, "height": 15, "color_depth": 4},
            {"name": "sunset.bmp", "width": 20, "height": 10, "color_depth": 8},
            {"name": "life.bmp", "width": 12, "height": 8},
            {"name": "debris_bits.bmp", "width": 4, "height": 4, "color_depth": 1},
            {"name": "debris_large.bmp", "width": 8, "height": 6, "color_depth": 1},
            # {"name": "test_white_line.bmp", "width": 24, "height": 2},
            {"name": "test_white_line_vert.bmp", "width": 2, "height": 24},
        ]

        ImageLoader.load_images(images, self.display)

    def _run(self):
        print("-- Starting update_loop...")
        asyncio.run(self.start_main_loop())

    def run(self):
        log_new_frame()

        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())
#
        log_mem(f"game_screen_run_START")

        """ Quick flash of white"""
        self.display.fill(0xBBBBBB)
        self.display.show()
        utime.sleep_ms(10)
        self.display.fill(0x0)
        self.display.show()

        barrier_speed = self.max_ground_speed / 200
        print(f"Sprite speed: {barrier_speed}")

        self.input = make_input_handler(self.player)

        if self.fps_enabled:
            self.fps_counter_task = asyncio.create_task(self.start_fps_counter(self.enemies.pool))

        self.update_score_task = loop.create_task(self.mock_update_score())
#        log_mem(f"game_screen_run_END")

        # Start the road speed-up task
        self.speed_anim = AnimAttr(self, 'ground_speed', self.max_ground_speed, 3000, easing=AnimAttr.ease_in_out_sine)
        loop.create_task(self.speed_anim.run(fps=60))
#
        log_mem(f"game_screen_start_START")
        self.start()
#        log_mem(f"game_screen_start_END")

        print("-- Starting update_loop...")
        asyncio.run(self.start_main_loop())

    async def update_loop(self):
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        print(f"--- (game screen) Update loop Start time: {start_time_ms}ms ---")
        self.check_gc_mem()
        num_lanes = 5

        # update loop - will run until task cancellation
        try:
            while True:
                if DEBUG_MEM:
                    print(micropython.mem_info())

                # Optimize: precompute num_lanes * bike_angle when bike_angle is being set
                self.camera.vp_x = round(self.player.turn_angle * num_lanes)
                self.camera.cam_x = round(self.player.turn_angle * num_lanes)

                self.grid.speed = self.ground_speed
                self.grid.speed_ms = self.ground_speed / 10
                self.total_frames += 1

                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms)
                elapsed = elapsed / 1000 # @TODO change to MS?
                self.last_update_ms = now

                if not self.paused:
                    self.stage.update(elapsed)
                    self.grid.update_horiz_lines(elapsed)
                    self.enemies.update(elapsed)
                    self.player.update(elapsed)
                    self.sun.x = self.sun_start_x - round(self.player.turn_angle * 4)

                    for sprite in self.instances:
                        sprite.update(elapsed)

                    self.collider.check_collisions(self.enemies.pool.active_sprites)

                await asyncio.sleep(1/60)   # Tweaking this number can improve FPS

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """
        log_new_frame()
#
        log_mem(f"game_screen_refresh_START")

        self.display.fill(0x0000)
        self.grid.show()
#
        log_mem(f"game_screen_refresh_BEFORE_SHOW_ALL")
        self.show_all()
#
        log_mem(f"game_screen_refresh_BEFORE_PLAYER_SHOW")
        self.player.show(self.display)
#
        log_mem(f"game_screen_refresh_BEFORE_FX")
        self.show_fx()
#
        log_mem(f"game_screen_refresh_UI_SHOW")
        self.ui.show()
#
        log_mem(f"game_screen_refresh_BEFORE_DISPLAY_SHOW")
        self.display.show()
#
        log_mem(f"game_screen_refresh_AFTER_DISPLAY_SHOW")

        if DEBUG_POOL:
            num_active = self.enemies.pool.active_count
            num_avail = len(self.enemies.pool.ready_indices)
            printc(f"*** POOL ACTIVE COUNT: {num_active} ***", INK_RED)
            printc(f"*** POOL AVAIL. COUNT: {num_avail} ***", INK_BRIGHT_RED)
        self.fps.tick()
#
        log_mem(f"game_screen_refresh_END")

    def show_all(self):
        for sprite in self.instances:
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

        print("-- Starting stage...")
        self.stage.start()

        loop = asyncio.get_event_loop()
        # loop.create_task(self.player.stop_blink())

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
        horiz_y: int = 16
        pos_y = 50
        max_sprite_height = -6

        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=pos_y,
            pos_z=-int(pos_y/2),
            vp_x=0,
            vp_y=horiz_y,
            min_y=horiz_y+4,
            max_y=self.display.height + max_sprite_height,
            fov=90.0)

        # self.camera = PerspectiveCamera(
        #     self.display,
        #     pos_x=0,
        #     pos_y=20,
        #     pos_z=camera_z,
        #     vp_x=0,
        #     vp_y=20,
        #     min_y=20,
        #     max_y=self.display.height)

    async def show_perf(self):
        if not prof.enabled:
            return False

        interval = 5000 # Every 5 secs

        now = utime.ticks_ms()
        delta = utime.ticks_diff(now, self.last_perf_dump_ms)
        if delta > interval:
            prof.dump_profile()
            self.last_perf_dump_ms = utime.ticks_ms()
