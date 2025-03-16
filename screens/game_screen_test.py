from _rp2 import DMA

from colors import color_util as colors
from bus_monitor import BusMonitor, BusProfiler
from scaler.const import BUS_CTRL_BASE, BUS_PRIORITY, DEBUG_BUS_MONITOR
from scaler.sprite_scaler import SpriteScaler
from perspective_camera import PerspectiveCamera
from sprites2.sprite_manager_2d import SpriteManager2D
from sprites2.test_heart import TestHeart
from ui_elements import ui_screen

from images.image_loader import ImageLoader
from road_grid import RoadGrid

from screens.screen import Screen
import uasyncio as asyncio
import utime

from sprites2.sprite_manager import SpriteManager
from sprites2.sprite_types import *

from micropython import const

class GameScreenTest(Screen):
    max_ground_speed: int = const(-1000)
    ground_speed: 0
    grid: RoadGrid = None
    sun: Sprite = None
    sun_start_x = None
    camera: PerspectiveCamera
    enemies: SpriteManager = None
    max_sprites: int = 100
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
    total_elapsed = 0
    fps_enabled = True
    is_first = True # so that we only use the scaler on frame 2+
    bus_prof:BusProfiler = None

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        self.ground_speed = self.max_ground_speed
        display.fill(0x0000)
        self.init_camera()

        self.scaler = SpriteScaler(display)
        self.mgr = SpriteManager2D(self.display, 1)
        self.load_types()
        self.load_sprite(SPRITE_TEST_HEART)
        self.inst, idx = self.mgr.pool.get(self.sprite_type, self.sprite)
        self.phy = self.mgr.phy

        self.preload_images()
        self.ui = ui_screen(display, self.num_lives)
        self.grid = RoadGrid(self.camera, display, lane_width=self.lane_width)

        self.display.fps = self.fps


    def preload_images(self):
        images = [
            {"name": "life.bmp", "width": 12, "height": 8},
        ]

        ImageLoader.load_images(images, self.display)

    def run(self):
        if DEBUG_BUS_MONITOR:
            self.bus_prof = BusProfiler()
            self.bus_prof.perf.list_presets()
            self.bus_prof.perf.list_available_events()
            self.bus_prof.perf.configure_preset("dma_impact")
            self.bus_prof.start_profiling()

        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())
        self.scaler.dma.init_channels()

        self.display.fill(0x9999)
        utime.sleep_ms(1000)
        self.display.fill(0x0)

        if self.fps_enabled:
            self.fps_counter_task = asyncio.create_task(self.start_fps_counter())

        if DEBUG_BUS_MONITOR:
            self.bus_prof_task = asyncio.create_task(self.start_bus_profiler())

        print("-- Starting update_loop...")
        asyncio.run(self.start_main_loop())


    async def update_loop(self):
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        print(f"--- (game screen) Update loop Start time: {start_time_ms}ms ---")

        # update loop - will run until task cancellation
        try:
            while True:
                if DEBUG_BUS_MONITOR:
                    self.bus_prof.sample_frame()

                self.total_frames += 1
                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms)
                elapsed = elapsed / 1000 # @TODO change to MS?
                self.last_update_ms = now

                if not self.paused:
                    self.grid.update_horiz_lines(elapsed)
                await asyncio.sleep_ms(1)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """
        self.display.fill(0x0000)
        self.phy.set_pos(self.inst, 53, 32)

        self.grid.show()
        self.ui.show()
        self.draw_corners()

        # self.scaler.draw_sprite(
        #     self.sprite,
        #     self.inst,
        #     self.image,
        #     h_scale=1,
        #     v_scale=1)

        self.display.show()
        self.fps.tick()

    def draw_corners(self):
        green = colors.hex_to_565(0x00FF00)
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

    async def start_bus_profiler(self):
        while True:
            bus_prof = self.bus_prof
            if bus_prof is False: 
                pass
            else:
                self.bus_prof.display_profile_stats()

            await asyncio.sleep(1)
    def load_types(self):
        self.mgr.add_type(
            sprite_type=SPRITE_TEST_HEART,
            sprite_class=TestHeart)

    def load_sprite(self, sprite_type):
        """ Creates images if not exist, returns meta"""
        self.sprite_type = sprite_type
        self.sprite_meta = self.sprite = self.mgr.sprite_metadata[sprite_type]
        self.sprite_palette = self.mgr.get_palette(sprite_type)
        self.image = self.mgr.sprite_images[self.sprite_type][-1]
        return self.sprite_meta

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

