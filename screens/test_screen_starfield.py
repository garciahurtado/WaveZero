import _thread
import asyncio
import math
import random

from perspective_camera import PerspectiveCamera
from scaler.sprite_scaler import SpriteScaler
from screens.screen import Screen
from sprites.sprite import Sprite
from sprites2.sprite_manager_2d import SpriteManager2D
from sprites2.sprite_types import SPRITE_TEST_HEART, SpriteType
from sprites2.test_heart import TestHeart
from ssd1331_pio import SSD1331PIO
from utils import dist_between
from profiler import Profiler as prof
import utime
class TestScreenStarfield(Screen):

    debug = False
    debug_inst = False
    screen_width = SSD1331PIO.WIDTH
    screen_height = SSD1331PIO.HEIGHT
    scale_dist_factor = 170 # The higher this is, the slower the scale grows w/ distance
    margin_px = 32

    def __init__(self, display, margin_px = 64):
        super().__init__(display, margin_px)
        self.init_camera()

        self.max_sprites = 10
        self.sprite_type = SPRITE_TEST_HEART
        self.mgr = SpriteManager2D(display, self.max_sprites, self.camera)
        self.mgr.bounds = self.bounds
        self.load_types()
        self.meta:SpriteType = self.load_sprite(self.sprite_type)

        self.scaler = SpriteScaler(self.display)
        self.scaler.prof = prof

        patt = self.scaler.dma.patterns
        self.all_scales = patt.get_horiz_patterns()
        self.all_keys = self.all_scales.keys()

        self.scales = list(self.all_scales.keys())
        self.scales.sort()
        self.scales = self.scales[1:]

        self.one_scales = {scale: patt for scale, patt in self.all_scales.items() if scale <= 1}
        self.two_scales = {scale: patt for scale, patt in self.all_scales.items() if scale <= 3 and scale >= 0.1}

        self.init_starfield()

    def init_camera(self):
        # Camera
        horiz_y: int = 16
        pos_y = 50
        max_sprite_height = -6

        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=pos_y,
            pos_z=-int(pos_y / 2),
            vp_x=0,
            vp_y=horiz_y,
            min_y=horiz_y + 4,
            max_y=self.display.height + max_sprite_height,
            fov=90.0)

    def init_starfield(self):
        self.load_types()
        self.base_speed = 0.02
        self.sprite.set_default(speed=self.base_speed)

        self.grid_beat = False
        self.fallout = False
        self.speed_vectors = []

        mgr = self.mgr
        # self.scales = self.make_exp_list(self.scales)

        spawn_x = int(self.screen_width / 2)
        spawn_y = int(self.screen_height / 2)
        self.screen_center = [spawn_x, spawn_y]


        self.speed_vectors = self.random_vectors(self.max_sprites)
        for inst, dir in zip(mgr.pool.sprites, self.speed_vectors):
            mgr.phy.set_dir(inst, dir[0], dir[1])

        # self.meta = self.mgr.get_meta(mgr.pool.sprites[0])
        self.meta = self.mgr.sprite_metadata[self.sprite_type]
        self.image = self.mgr.sprite_images[self.sprite_type][-1]

        self.h_scale = self.v_scale = 1
        self.max_scale_id = len(self.scales)
        self.max_scale_dot = 1/self.meta.width # scales lower than this will draw a dot in lieu of render
        self.max_dist = int(dist_between(spawn_x, spawn_y, self.full_width, self.full_height))

    def do_refresh(self):
        self.common_bg()
        center = self.screen_center

        i = 0
        for inst in self.mgr.pool.active_sprites:
            # meta = self.mgr.get_meta(inst)
            i += 1
            coords = self.mgr.phy.get_pos(inst)

            """ Calculate distance to the center """
            dist = dist_between(center[0], center[1], coords[0], coords[1])
            scale_id = self.find_scale_id(dist, exp=False)

            # scale_id = 5 # DEBUG
            scale = self.scales[scale_id]

            # if scale <= self.max_scale_dot:
            #     """ Rendering of this sprite is much simpler, since we dont need to do all the scaling stuff """
            #     self.scaler.draw_dot(coords[0], coords[1], meta)
            #     continue

            # if scale <= self.scales[6]:
            #     """ Rendering of this sprite is much simpler, since we dont need to do all the scaling stuff """
            #     self.scaler.draw_dot_2(coords[0], coords[1], meta)
            #     continue

            # if self.debug_inst:
            #     print(f" - INST coords: {coords[0]}/{coords[1]} - BEFORE speed")
            #     print(f" - INST scale_id: {scale_id}")
            #     print(f" - INST scale: {scale}")
            #     print(f" - INST speed: {inst.speed}")

            # Check bounds first
            actual_width = self.sprite.width * scale
            actual_height = self.sprite.height * scale

            """ Center of the scaled sprite, in px"""
            # offset_x = (self.sprite.width * scale) // 2
            # offset_y = (self.sprite.height * scale) // 2

            """ Only needed for bounds checking. Is there a better way? """
            # pos_x, pos_y = self.mgr.get_pos(inst)
            pos_x, pos_y = coords[0], coords[1]

            # if not self.mgr.is_within_bounds([center_x, center_y]):
            if not self.mgr.is_within_bounds([pos_x, pos_y]):
                self.mgr.release(inst, self.sprite)
                if self.debug_inst:
                    print(f"<< COORDS ({pos_x}, {pos_y}) >>")
                    print(f"<< // IS OUT OF BOUNDS >>")
                    print(f"<< s:{scale} / {actual_width} / {actual_height} w/h")
                    print(f"<< SPRITE RELEASED - ACTIVE: {self.mgr.pool.active_count}>>")
                continue

            self.scaler.draw_sprite(
                self.sprite,
                int(coords[0]),
                int(coords[1]),
                self.image,
                h_scale=scale,
                v_scale=scale)

        """ SPAWN more """
        self.spawn()

        # self.show_prof()
        self.display.show()
        self.fps.tick()

    def load_sprite(self, load_type):
        sprite_type = load_type

        self.sprite = self.mgr.get_sprite(sprite_type)
        self.sprite_img = self.mgr.sprite_images[sprite_type]

        return self.sprite


    def random_vectors(self, num):
        """ Generate an array of num x,y pairs """
        vectors = []

        for _ in range(num):
            # Random angle in radians (0-360°)
            angle = random.uniform(0, 2 * math.pi)
            x = math.cos(angle)
            y = math.sin(angle)
            vectors.append((x, y))

        return vectors

    def run(self):
        self.running = True
        self.check_mem()

        """ The display loop goes to the background (as do any input loops, other animations, etc..) """
        loop = asyncio.get_event_loop()
        loop.create_task(self.start_display_loop())

        print("-- Starting update_loop")
        asyncio.run(self.start_main_loop())

    def load_types(self):
        self.mgr.add_type(
            sprite_type=SPRITE_TEST_HEART,
            sprite_class=TestHeart)

    def spawn(self, prob=10):
        """ Probability in percent """
        if random.randint(0, 100) < prob:
            if self.mgr.pool.active_count < self.max_sprites:
                sprite_class = self.sprite_type
                inst, idx = self.mgr.spawn(sprite_class, self.sprite)
                inst.pos_type = Sprite.POS_TYPE_NEAR
                x = 48
                y = 32
                self.mgr.phy.set_pos(inst, x, y)

    def common_bg(self):
        self.display.fill(0x000000)

    async def update_loop(self):
        start_time_ms = self.last_update_ms = utime.ticks_ms()
        self.last_perf_dump_ms = start_time_ms

        print(f"--- Update loop Start time: {start_time_ms}ms ---")
        print(f" = EXEC ON CORE {_thread.get_ident()} (update_loop)")

        # update loop - will run until task cancellation
        try:
            while True:
                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms)

                self.mgr.update(elapsed)
                self.last_update_ms = utime.ticks_ms()

                # Tweaking this number can give FPS gains / give more frames to `ellapsed`, avoiding near zero
                # errors
                await asyncio.sleep(1/30)

        except asyncio.CancelledError:
            return False

    async def start_display_loop(self):
        while True:
            self.do_refresh()
            await asyncio.sleep_ms(5)

    async def start_main_loop(self):
        print("-- ... MAIN LOOP STARTING ...")
        self.check_mem()

        """ All top level tasks / threads go here. Once all of these finish, the program ends"""
        await asyncio.gather(
            self.start_fps_counter(),
            self.update_loop(),
        )

    async def start_fps_counter(self):
        while True:
            fps = self.fps.fps()
            if fps is False:
                pass
            else:
                num = self.mgr.pool.active_count
                fps_str = "{: >6.2f}".format(fps)
                print(f"FPS: {fps_str} / {num} sprites")

            await asyncio.sleep(1)

    def find_scale_id(self, dist, exp=True):
        """
        Increase scale exponential to the distance from
        the center of the display
        """

        if exp:
            scale = self.max_scale_id * math.exp(-dist / self.scale_dist_factor)
        else:
            # Linear falloff: y = mx + b
            scale = self.max_scale_id * (1 - dist / self.scale_dist_factor)

        # Flip the scale_id to match reversed scales array
        scale_id = self.max_scale_id - min(int(scale), self.max_scale_id)
        scale_id -= 1
        return max(0, min(scale_id, len(self.scales) - 1))

