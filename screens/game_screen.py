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
from sprites.sprite_registry import registry
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
        self.check_gc_mem()  # Keep your memory checks

        print("-- Setting up Sprite Assets...")
        self._setup_sprite_assets()  # New method call
        self.check_gc_mem()

        print("-- Creating UI...")
        self.ui = ui_screen(display, self.num_lives)
        self.check_gc_mem()

        print("-- Creating player sprite...")
        # PlayerSprite might need to be adapted if it directly loaded its own image before
        # Now it should primarily use its type_id (e.g., SPRITE_PLAYER)
        self.player = PlayerSprite(
            camera=self.camera)  # Assuming PlayerSprite can be initialized without direct image path

        print("-- Creating Enemy Sprite Manager...")
        # Choose your renderer
        # renderer = RendererPrescaled(display)
        renderer = RendererScaler(display)  # Current choice in your code

        self.enemies = SpriteManager3D(
            display,
            renderer,
            max_sprites=self.max_sprites,
            camera=self.camera,
            grid=self.grid
        )

        # REMOVE THESE LINES:
        # renderer.sprite_images = self.enemies.sprite_images
        # renderer.sprite_palettes = self.enemies.sprite_palettes
        # The renderer will get assets from sprite_registry when it needs them.
        # SpriteManager3D will also use sprite_registry to get metadata for sprite creation.

        self.collider = Collider(self.player, self.enemies, self.crash_y_start, self.crash_y_end)
        self.collider.add_callback(self.do_crash)

        print("-- Creating road grid...")
        self.grid = RoadGrid(self.camera, display, lane_width=self.lane_width)
        self.check_gc_mem()

        self.death_anim = DeathAnim(display)
        self.death_anim.callback = self.after_death
        self.check_gc_mem()

        self.display.fps = self.fps

        self.stage = Stage1(self.enemies)  # Stage1 might need to know about sprite types
        # or get them via the enemy manager.
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

        self.add_sprite(self.enemies)  # SpriteManager3D handles its own rendering using the registry.
        # If self.sun needs to be drawn by the Screen's show_all, ensure add_sprite can handle it.
        # self.add_sprite(self.sun) # If you want screen to draw it.

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

    def _setup_sprite_assets(self):
        """
        Defines all sprite types, registers them with the SpriteRegistry,
        and loads their assets.
        """
        # Define metadata for each sprite type
        # Note: 'num_frames' for prescaled sprites means number of scale levels.
        # For non-prescaled, it usually means animation frames if the image is a spritesheet.
        # ImageLoader handles spritesheet animation frames within the single Image object.
        # SpriteRegistry's prescale=True creates a list of differently scaled Image objects.

        sprite_definitions = [
            {"id": SPRITE_PLAYER, "path": "/img/bike_sprite.bmp", "w": 32, "h": 22, "cd": 4, "nf": 5, "prescale": True},
            # Example: 5 prescale levels
            {"id": SPRITE_SUNSET, "path": "/img/sunset.bmp", "w": 20, "h": 10, "cd": 8, "nf": 1, "prescale": False},
            # nf=1 means no animation/scaling levels needed
            {"id": SPRITE_LIFE, "path": "/img/life.bmp", "w": 12, "h": 8, "cd": 4, "nf": 1, "prescale": False},
            # Assuming cd=4 for life.bmp
            {"id": SPRITE_DEBRIS_BITS, "path": "/img/debris_bits.bmp", "w": 4, "h": 4, "cd": 1, "nf": 1,
             "prescale": False},
            {"id": SPRITE_DEBRIS_LARGE, "path": "/img/debris_large.bmp", "w": 8, "h": 6, "cd": 1, "nf": 1,
             "prescale": False},
            {"id": SPRITE_WHITE_LINE_VERT, "path": "/img/test_white_line_vert.bmp", "w": 2, "h": 24, "cd": 4, "nf": 1,
             "prescale": False},  # Assuming cd=4

            # Add all other sprite types used by enemies, UI, effects etc.
            # Example for an enemy that might be prescaled:
            # {"id": SPRITE_ALIEN_FIGHTER, "path": "/img/alien_fighter.bmp", "w": 24, "h": 16, "cd": 4, "nf": 4, "prescale": True},
            # Example for an enemy that is NOT prescaled by the registry (uses SpriteScaler on the fly):
            # {"id": SPRITE_ROAD_BARRIER, "path": "/img/road_barrier_yellow.bmp", "w": 24, "h": 15, "cd": 4, "nf": 1, "prescale": False},
        ]

        for s_def in sprite_definitions:
            meta = SpriteType(
                image_path=s_def["path"],
                width=s_def["w"],
                height=s_def["h"],
                color_depth=s_def["cd"],  # This is BPP
                num_frames=s_def["nf"]  # Meaning depends on prescale flag
                # Add any other common SpriteType defaults here if needed
            )
            registry.add_type(s_def["id"], meta)
            registry.load_images(s_def["id"], prescale=s_def.get("prescale", False))

        print("Sprite assets configured and loaded into registry.")

    # Placeholder for drawing the sun if it's not a standard sprite instance managed elsewhere
    def _draw_sun(self, display):
        sun_img_asset = registry.get_img(SPRITE_SUNSET)
        sun_palette = registry.get_palette(SPRITE_SUNSET)
        sun_meta = registry.get_metadata(SPRITE_SUNSET)  # For alpha or other info

        if sun_img_asset and sun_palette:
            # Assuming sun_img_asset is a single Image object
            alpha = sun_meta.alpha_color if sun_meta and hasattr(sun_meta, 'alpha_color') else -1
            display.blit(sun_img_asset.pixels, int(self.sun.x), int(self.sun.y), alpha, sun_palette)