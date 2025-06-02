import random

import micropython

from debug.mem_logging import log_mem, log_new_frame
from mpdb.mpdb import Mpdb
from scaler.const import DEBUG_INST, DEBUG, INK_MAGENTA, DEBUG_POOL, INK_BRIGHT_RED, INK_RED, DEBUG_MEM, INK_CYAN, \
    INK_BRIGHT_GREEN, INK_BRIGHT_BLUE, DEBUG_FRAME_ID
from scaler.scaler_debugger import printc
from scaler.sprite_scaler import SpriteScaler
from perspective_camera import PerspectiveCamera
from death_anim import DeathAnim
from sprites.renderer_scaler import RendererScaler
from sprites.types.test_skull import TestSkull
from sprites.types.warning_wall import WarningWall
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
from sprites.sprite_registry import registry
from sprites_old.sprite import Sprite

from profiler import Profiler as prof, Profiler
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
    mgr: SpriteManager3D = None
    max_sprites: int = 256
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
    num_lanes = 5

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)

        display.fill(0x0000)
        display.show()

        self.init_camera()
        renderer = RendererScaler(display)
        self.scaler = renderer.scaler

        print("-- Preloading images...")
        # self.preload_images()
        # self.check_mem()

        self.init_sprite_images()

        print("-- Creating UI...")
        self.ui = ui_screen(display, self.num_lives)
        self.check_gc_mem()

        print("-- Creating player sprite...")
        self.player = PlayerSprite(camera=self.camera)

        self.collider = Collider(self.player, self.mgr, self.crash_y_start, self.crash_y_end)
        self.collider.add_callback(self.do_crash)

        print("-- Creating road grid...")
        self.grid = RoadGrid(self.camera, display, lane_width=self.lane_width)
        self.check_gc_mem()

        print("-- Creating Enemy Sprite Manager...")
        self.mgr = SpriteManager3D(
            self.display,
            renderer,
            max_sprites=self.max_sprites,
            camera=self.camera,
            grid=self.grid
        )
        self.phy = self.mgr.phy

        self.death_anim = DeathAnim(display)
        self.death_anim.callback = self.after_death

        self.display.fps = self.fps

        self.stage = Stage1(self.mgr)
        self.check_gc_mem()

        # Create the Sun Sprite
        # The old Sprite class might need adaptation if it expected direct image loading.
        # It's better if game objects like the sun are also defined via a SpriteType
        # and then their instances are created.
        # For now, let's assume you'll refactor generic Sprites to use the registry too.
        # If 'sun' is just a simple image, we ensure its type (SPRITE_SUNSET) is loaded.
        # The actual creation of the sun sprite instance might change depending on
        # how you manage general game objects vs. pooled enemy sprites.
        # If Sprite("/img/sunset.bmp") directly loads, that's outside the registry.
        # Ideal way:
        # self.sun = create_game_object_sprite(SPRITE_SUNSET, x=39, y=11)
        # For now, let's assume the old way for sun, but its image must be in registry if drawn by a new renderer.
        # The `add_sprite` method on Screen would also need to be aware if it's rendering via registry.

        # If you had a generic Sprite class that directly loaded images:
        # sun = Sprite("/img/sunset.bmp")
        # You'd want to change this to:
        # sun_meta = sprite_registry.get_metadata(SPRITE_SUNSET)
        # sun = YourGameObjectClass(SPRITE_SUNSET, x=39, y=11) # or similar
        # For now, let's assume you have a way to create this sprite.
        # The main point is that its assets (image, palette) are in the registry.

        # Let's create a placeholder for the sun using its type ID
        # This part depends on how you instantiate non-pooled sprites.
        # For simplicity, let's assume self.sun is an object that has .x, .y, .sprite_type
        self.sun = type('SunSprite', (object,),
                        {'x': 39, 'y': 11, 'sprite_type': SPRITE_SUNSET, 'update': lambda s, e: None,
                         'show': lambda s, d: self._draw_sun(d)})()
        self.sun_start_x = 39

        # If self.sun needs to be drawn by the Screen's show_all, ensure add_sprite can handle it.
        # self.add_sprite(self.sun) # If you want screen to draw it.

        sun = Sprite("/img/sunset.bmp")
        sun.x = self.sun_start_x = 39
        sun.y = 11
        self.sun = sun

        self.add_sprite(sun)
        self.add_sprite(self.mgr)

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

    def run(self):
        """ Quick flash of white"""
        self.display.fill(0xBBBBBB)
        self.display.show()
        utime.sleep_ms(10)
        self.display.fill(0x0)
        self.display.show()

        barrier_speed = self.max_ground_speed / 200
        print(f"Sprite speed: {barrier_speed}")

        self.input = make_input_handler(self.player)
        loop = asyncio.get_event_loop()

        if self.fps_enabled:
            self.fps_counter_task = loop.create_task(self.start_fps_counter(self.mgr.pool))

        if Profiler.enabled:
            loop.create_task(self.update_profiler())

        self.display_task = loop.create_task(self.start_display_loop())
        self.update_score_task = loop.create_task(self.mock_update_score())

        # Start the road speed-up task
        self.speed_anim = AnimAttr(self, 'ground_speed', self.max_ground_speed, 3000, easing=AnimAttr.ease_in_out_sine)
        loop.create_task(self.speed_anim.run(fps=60))
        self.start()

        print("-- Starting update_loop...")
        asyncio.run(self.start_update_loop())

    async def stop_stage(self):
        await asyncio.sleep_ms(10000)
        printc("** STOPPING STAGE AND SCREEN UPDATES**", INK_MAGENTA)
        self.pause()
        self.stage.stop()

    async def update_loop(self):
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        print(f"--- (game screen) Update loop Start time: {start_time_ms}ms ---")
        self.check_gc_mem()

        # update loop - will run until task cancellation
        try:
            while True:
                self.do_update()
                await asyncio.sleep(1/60)   # Tweaking this number can improve FPS

        except asyncio.CancelledError:
            return False

    def do_update(self):
        if DEBUG_MEM:
            print(micropython.mem_info())

        # Optimize: precompute num_lanes * bike_angle when bike_angle is being set
        self.camera.vp_x = round(self.player.turn_angle * self.num_lanes)
        self.camera.cam_x = round(self.player.turn_angle * self.num_lanes)

        self.grid.speed = self.ground_speed
        self.grid.speed_ms = self.ground_speed / 10
        self.total_frames += 1

        now = utime.ticks_ms()
        elapsed = utime.ticks_diff(now, self.last_update_ms)
        elapsed = elapsed / 1000  # @TODO change to MS?
        self.last_update_ms = now

        if not self.paused:
            self.stage.update(elapsed)
            self.grid.update_horiz_lines(elapsed)
            self.mgr.update(elapsed)
            self.player.update(elapsed)
            self.sun.x = self.sun_start_x - round(self.player.turn_angle * 4)

            for sprite in self.instances:
                sprite.update(elapsed)

            self.collider.check_collisions(self.mgr.pool.active_sprites)
    async def update_profiler(self):
        while True:
            await asyncio.sleep(3)
            prof.dump_profile()
            prof.clear()

    def do_refresh(self):
        """ Overrides parent method """
        if DEBUG_FRAME_ID:
            printc(f"[[ STARTING FRAME {self.total_frames:04.} ]]", INK_BRIGHT_GREEN)

        # First, do the world updates
        self.do_update()

        # Now run the rendering code
        self.display.fill(0x0000)
        self.grid.show()
        self.show_all()
        self.player.show(self.display)
        self.show_fx()
        self.ui.show()
        self.display.show()

        if DEBUG_POOL:
            num_active = self.mgr.pool.active_count
            num_avail = len(self.mgr.pool.ready_indices)
            printc(f"*** POOL ACTIVE COUNT: {num_active} ***", INK_BRIGHT_GREEN)
            printc(f"*** POOL AVAIL. COUNT: {num_avail} ***", INK_BRIGHT_BLUE)
        self.fps.tick()

    def show_all(self):
        size = len(self.instances)
        for i in range(size):
            self.instances[i].show(self.display)

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

    def init_sprite_images(self):  # Or _setup_sprite_assets(self) as previously named
        """
        Defines all globally used sprite types by explicitly creating SpriteType objects,
        registers them with the SpriteRegistry, which also loads their assets.
        """
        print("-- Initializing Global Sprite Assets (Explicit Mode)...")

        # --- Using specific sprite classes ---
        registry.add_type(
            SPRITE_TEST_SKULL,
            TestSkull)

        # LOADED IN STAGE CODE #
        # registry.add_type(
        #     SPRITE_BARRIER_LEFT,
        #     WarningWall)
        #
        # registry.add_type(
        #     SPRITE_BARRIER_RIGHT,
        #     WarningWall,
        #     image_path="/img/road_barrier_yellow_inv_32.bmp")

    def init_sprites(self, display):
        raise DeprecationWarning

    async def show_perf(self):
        if not prof.enabled:
            return False

        interval = 5000   # Every 5 secs

        now = utime.ticks_ms()
        delta = utime.ticks_diff(now, self.last_perf_dump_ms)
        if delta > interval:
            prof.dump_profile()
            self.last_perf_dump_ms = utime.ticks_ms()
