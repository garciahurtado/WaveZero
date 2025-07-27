import random
import gc
import micropython
from debug.mem_logging import log_mem, log_new_frame

from scaler.const import DEBUG_INST, DEBUG, INK_MAGENTA, DEBUG_POOL, INK_BRIGHT_RED, INK_RED, DEBUG_MEM, INK_CYAN, \
    INK_BRIGHT_GREEN, INK_BRIGHT_BLUE, DEBUG_FRAME_ID, INK_YELLOW, DEBUG_PROFILER, DEBUG_FPS, DEBUG_LOG_MEM
from scaler.scaler_debugger import check_gc_mem
from print_utils import printc
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

from profiler import prof
from micropython import const
class GameScreen(Screen):
    fps_enabled = DEBUG_FPS
    ground_speed: int = 0
    max_ground_speed: int = const(-3000)
    grid: RoadGrid = None
    sun: Sprite = None
    sun_start_x = None
    camera: PerspectiveCamera
    mgr: SpriteManager3D = None
    max_sprites: int = 128
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = 4
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
        # self.preload_images() # Still haven't gotten this to work

        print("-- Creating UI...")
        self.ui = ui_screen(display, self.num_lives)
        check_gc_mem()

        print("-- Creating player sprite...")
        self.player = PlayerSprite(camera=self.camera)

        self.collider = Collider(self.player, self.mgr, self.crash_y_start, self.crash_y_end)
        self.collider.add_callback(self.do_crash)

        print("-- Creating road grid...")
        self.grid = RoadGrid(self.camera, display, lane_width=self.lane_width)

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
        check_gc_mem()
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

        self.is_render_finished = True  # this will trigger the first update loop

        barrier_speed = self.max_ground_speed / 200
        print(f"Sprite speed: {barrier_speed}")

        self.input = make_input_handler(self.player)
        loop = asyncio.get_event_loop()

        if prof.enabled:
            loop.create_task(self.update_profiler())

        if self.fps_enabled:
            printc("... STARTING FPS COUNTER ...")
            self.fps_counter_task = loop.create_task(self.start_fps_counter(self.mgr.pool))

        self.update_score_task = loop.create_task(self.mock_update_score())

        # Start the road speed-up task
        self.speed_anim = AnimAttr(self, 'ground_speed', self.max_ground_speed, 3000, easing=AnimAttr.ease_in_out_sine)
        loop.create_task(self.speed_anim.run(fps=60))
        self.start()

        printc("-- STARTING UPDATE_LOOP and RENDER_LOOP ... ---", INK_BRIGHT_GREEN)
        loop.create_task(self.start_update_loop())
        loop.create_task(self.start_render_loop())
        loop.run_forever()

    async def stop_stage(self):
        await asyncio.sleep_ms(10000)
        printc("** STOPPING STAGE AND SCREEN UPDATES **", INK_MAGENTA)
        self.pause()
        self.stage.stop()

    def do_update(self):
        if DEBUG_MEM:
            print(micropython.mem_info())

        # Optimize: precompute num_lanes * bike_angle when bike_angle is being set
        self.camera.vp_x = round(self.player.turn_angle * self.num_lanes)
        self.camera.cam_x = round(self.player.turn_angle * self.num_lanes)

        self.grid.speed = self.ground_speed
        self.grid.speed_ms = self.ground_speed / 10

        now = utime.ticks_ms()
        elapsed = utime.ticks_diff(now, self.last_update_ms)
        elapsed = elapsed / 1000  # @TODO change to MS?
        self.last_update_ms = now

        """ Call the update methods of all the subsystems that are updated every frame """
        if not self.paused:
            if DEBUG_FRAME_ID:
                printc("-- Updating subsystems --", INK_YELLOW)

            self.update_profiler_sync()
            self.grid.update_horiz_lines(elapsed)
            self.player.update(elapsed)
            self.sun.x = self.sun_start_x - round(self.player.turn_angle * 4)

            # The sprite manager is one of these instances, this is how it receives world updates
            for sprite in self.instances:
                sprite.update(elapsed)

            self.collider.check_collisions(self.mgr.pool.active_sprites)
            self.stage.update(elapsed)

    def do_render(self):
        """ Overrides parent method """
        if DEBUG_PROFILER:
            prof.start_frame()

        if DEBUG_FRAME_ID:
            printc(f"[[ STARTING FRAME {self.total_frames:04.} ]]", INK_BRIGHT_GREEN)

        # Now run the rendering code
        self.display.fill(0x0000)
        self.grid.show()

        # disable garbage collection in the inner display loop
        gc.disable()

        self.show_all()
        # self.player.show(self.display) # Explicitly so that we can control the z order
        self.show_fx()
        # self.ui.show()
        self.display.show()

        gc.enable()
        gc.collect()

        if DEBUG_POOL:
            num_active = self.mgr.pool.active_count
            num_avail = len(self.mgr.pool.ready_indices)
            printc(f"*** POOL ACTIVE COUNT: {num_active} ***", INK_BRIGHT_GREEN)
            printc(f"*** POOL AVAIL. COUNT: {num_avail} ***", INK_BRIGHT_BLUE)

    def show_all(self):
        # self.mgr was registered as one of these instances, so it will be rendered as a result of this call
        size = len(self.instances)
        for i in range(size):
            inst = self.instances[i]
            inst.show(self.display)

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
            self.do_render()

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

        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=pos_y,
            pos_z=-int(pos_y/2),
            vp_x=0,
            vp_y=horiz_y,
            min_y=horiz_y+4,
            # max_y=self.display.height + max_sprite_height,
            max_y=self.display.height,
            fov=90.0)

    def init_sprites(self, display):
        raise DeprecationWarning
