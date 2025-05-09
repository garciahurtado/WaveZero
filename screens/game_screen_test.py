import random

from colors import color_util as colors
from scaler.const import DEBUG, INK_GREEN
from perspective_camera import PerspectiveCamera
from scaler.scaler_debugger import printc
from sprites.sprite_physics import SpritePhysics
from sprites.types.warning_wall import WarningWall
from sprites_old.sprite import Sprite

from ui_elements import ui_screen

from images.image_loader import ImageLoader
from road_grid import RoadGrid

from screens.screen import Screen
import uasyncio as asyncio
import utime

from sprites.sprite_manager import SpriteManager
from sprites.sprite_types import *
from sprites.types.test_flat import TestFlat
from sprites.types.test_heart import TestHeart
from sprites.types.test_skull import TestSkull
from sprites.renderer_prescaled import RendererPrescaled
from sprites.renderer_scaler import RendererScaler
from sprites.sprite_manager_2d import SpriteManager2D
from sprites.sprite_manager_3d import SpriteManager3D
from sprites.sprite_registry import registry as registry
from micropython import const

from utils import pprint, pprint_pure

CURRENT_SPRITE = SPRITE_TEST_SKULL

class GameScreenTest(Screen):
    ground_speed: 0
    max_ground_speed: int = const(-700)
    max_sprites: int = 32 # for the sprite pool
    num_sprites: int = 16 # for the circle

    grid: RoadGrid = None
    sun: Sprite = None
    sun_start_x = None
    camera: PerspectiveCamera
    mgr: SpriteManager = None
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = 4
    total_frames = 0
    last_update_ms = 0
    fps_every_n_frames = 30
    player = None
    last_perf_dump_ms = 0
    paused = False
    ui = None
    frames_elapsed = 0
    fps_enabled = True
    is_first = True # so that we only use the scaler on frame 2+
    inst_group = []

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)

        self.ground_speed = self.max_ground_speed
        display.fill(0x0000)
        self.init_camera()

        renderer = RendererScaler(display)
        self.scaler = renderer.scaler

        self.mgr = SpriteManager3D(
            self.display,
            renderer,
            max_sprites=self.max_sprites,
            camera=self.camera,
            grid=self.grid
        )
        self.phy = self.mgr.phy

        self.init_sprite_images()
        self.init_sprites(display)

        # self.mgr = SpriteManager2D(self.display, renderer, self.max_sprites) # max sprites

        patterns = self.scaler.dma.patterns.horiz_patterns
        pattern_keys = list(patterns.keys())
        pattern_keys.sort()
        short_keys = pattern_keys[0:16]
        self.scale_list = short_keys
        self.scale_list.reverse()

        self.sprite_type = registry.sprite_metadata[CURRENT_SPRITE]
        self.image = registry.sprite_images[CURRENT_SPRITE]
        self.display.fps = self.fps

    # @DEPRECATED
    def _preload_images(self):
        raise DeprecationWarning

        images = [
            {"name": "life.bmp", "width": 12, "height": 8},
        ]

        ImageLoader.load_images(images, self.display)

    def run(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())

        self.display.fill(0x0)

        if self.fps_enabled:
            self.fps_counter_task = asyncio.create_task(self.start_fps_counter(self.mgr.pool))

        print("-- Starting update_loop...")
        asyncio.run(self.start_main_loop())

    async def update_loop(self):
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        printc(f"--- (SCREEN) Update loop start time: {start_time_ms}ms ---", INK_GREEN)

        # update loop - will run until task cancellation
        try:
            while True:
                self.total_frames += 1
                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms)
                elapsed = elapsed / 1000 # @TODO change to MS?
                total_elapsed = utime.ticks_diff(now, start_time_ms)
                self.last_update_ms = now

                if not self.paused:
                    self.grid.update_horiz_lines(elapsed)

                    # Update sprites circular motion
                    for sprite in self.inst_group:
                        self.phy.update_circ_pos(sprite, total_elapsed)

                await asyncio.sleep_ms(1)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """
        if DEBUG:
            print(f"--------------------------")
            print(f"- START OF FRAME n. {self.frames_elapsed} - ")
            print(f"--------------------------")

            self.check_gc_mem()

        self.display.fill(0x0)

        self.grid.show()
        self.ui.update_score(random.randint(0, 99999999))
        self.ui.show()

        # self.draw_corners()
        self.draw_sprite_circle()
        #
        # inst = self.inst_group[0]
        # h_scale = 2
        # v_scale = 2
        # self.scaler.draw_sprite(self.sprite, inst, self.image, h_scale=h_scale, v_scale=v_scale)

        self.display.show()
        self.fps.tick()

        if DEBUG:
            print(f"__________________________")
            print(f"- END OF FRAME n. {self.frames_elapsed} - ")
            print(f"__________________________")

        self.frames_elapsed += 1

    def draw_sprite_circle(self):
        scale_idx = 0
        for inst in self.inst_group:
            curr_scale = self.scale_list[scale_idx]
            inst.draw_x, inst.draw_y = SpritePhysics.get_pos(inst)
            self.scaler.draw_sprite(
                self.sprite_type, inst, self.image,
                h_scale=curr_scale, v_scale=curr_scale)
            scale_idx += 1

    def draw_corners(self):
        green = colors.hex_to_565(0x00FF00)
        red = colors.hex_to_565(0x0000FF)
        blue = colors.hex_to_565(0xFF0000)
        yellow = colors.hex_to_565(0x00FFFF)
        width = self.display.width-1
        height = self.display.height-1
        length = 16

        self.display.hline(0, 0,                    length, green)
        self.display.hline(width-length, 0,         length, green)
        self.display.hline(0, height,               length, green)
        self.display.hline(width-length, height,    length, green)

        self.display.line(0, 0, 0, length, green)
        self.display.line(width, 0, width, length, green)
        self.display.line(0, height, 0, height-length, green)
        self.display.line(width, height, width, height-length, green)

        self.display.hline(0, 0, 8, red)
        self.display.hline(0, 0, 4, blue)

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

    def init_sprites(self, display):
        """ Inits the sprite instances, not the sprite types and images
        """
        running_ms = 0
        print(f"Creating a group of {self.num_sprites} sprites")

        for i in range(self.num_sprites):
            """ We give each sprite a slightly different 'birthday', so that the animation will place them in different
            parts of the circle """
            new_inst, idx = self.mgr.pool.get(CURRENT_SPRITE)
            new_inst.born_ms += running_ms
            self.phy.set_pos(new_inst, 50, 24)
            self.inst_group.append(new_inst)
            running_ms += 200

        self.ui = ui_screen(display, self.num_lives)
        self.grid = RoadGrid(self.camera, display, lane_width=self.lane_width)

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

        registry.add_type(
            SPRITE_TEST_HEART,
            TestHeart)

        registry.add_type(
            SPRITE_TEST_FLAT,
            TestFlat)

        registry.add_type(
            SPRITE_BARRIER_LEFT,
            WarningWall)
            # num_frames=1)

        # Player Sprite
        player_meta = SpriteType(
            image_path="/img/bike_sprite.bmp",
            width=32,
            height=22,
            color_depth=4,  # BPP
            num_frames=5  # For prescale: 5 scale levels.
        )
        # --- For sprites defined with generic SpriteType class ---
        # All their properties must be passed as kwargs.
        # Explicitly set prescale=True only when needed.
        registry.add_type(
            SPRITE_PLAYER,
            SpriteType,
            image_path="/img/bike_sprite.bmp",
            width=32,
            height=22,
            color_depth=4,
            num_frames=5,
        )

        registry.add_type(
            SPRITE_SUNSET,
            SpriteType,
            image_path="/img/sunset.bmp",
            width=20,
            height=10,
            color_depth=8,
            num_frames=1,
        )

        registry.add_type(
            SPRITE_LIFE,
            SpriteType,
            image_path="/img/life.bmp",
            width=12,
            height=8,
            color_depth=4,
            num_frames=1,
        )

        registry.add_type(
            SPRITE_DEBRIS_BITS,
            SpriteType,
            image_path="/img/debris_bits.bmp",
            width=4,
            height=4,
            color_depth=1,
            num_frames=1,
        )

        registry.add_type(
            SPRITE_DEBRIS_LARGE,
            SpriteType,
            image_path="/img/debris_large.bmp",
            width=8,
            height=6,
            color_depth=1,
            num_frames=1,
        )

    # Placeholder for drawing the sun if it's not a standard sprite instance managed elsewhere
    def _draw_sun(self, display):
        sun_img_asset = registry.get_img(SPRITE_SUNSET)
        sun_palette = registry.get_palette(SPRITE_SUNSET)
        sun_meta = registry.get_metadata(SPRITE_SUNSET)  # For alpha or other info

        if sun_img_asset and sun_palette:
            # Assuming sun_img_asset is a single Image object
            alpha = sun_meta.alpha_color if sun_meta and hasattr(sun_meta, 'alpha_color') else -1
            display.blit(sun_img_asset.pixels, int(self.sun.x), int(self.sun.y), alpha, sun_palette)


