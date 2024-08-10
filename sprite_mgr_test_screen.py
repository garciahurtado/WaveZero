import random

import color_util as colors
from micropython import const

from anim.anim_attr import AnimAttr
from sprites.player_sprite import PlayerSprite
from road_grid import RoadGrid

from input import make_input_handler
from perspective_camera import PerspectiveCamera
from game_screen import Screen
import uasyncio as asyncio
import utime

from sprites2.sprite_manager import SpriteManager
from ui_elements import ui_screen
from collider import Collider
# from wav.test_wav import play_music

SPRITE_PLAYER = const(0)
SPRITE_BARRIER_LEFT = const(1)
SPRITE_BARRIER_RIGHT = const(2)
SPRITE_BARRIER_RED = const(3)
SPRITE_LASER_ORB = const(4)
SPRITE_LASER_WALL = const(5)
SPRITE_LASER_WALL_POST = const(6)
SPRITE_WHITE_DOT = const(7)

from profiler import Profiler as prof

class SpriteMgrTestScreen(Screen):
    ground_speed: int = const(-0)
    max_ground_speed: int = const(-150)
    grid: RoadGrid = None
    camera: PerspectiveCamera
    sprites: SpriteManager = None
    saved_ground_speed = 0
    lane_width: int = const(22)
    num_lives: int = const(4)
    total_frames = 0
    last_update_ms = 0
    fps_every_n_frames = 30
    color_shift_every_n_frames = 1000
    player = None
    last_perf_dump_ms = 0
    input_task = None
    crash_y_start = const(48)  # Screen start Y of Sprites which will collide with the player
    crash_y_end = const(62)  # Screen end Y
    death_anim = None
    paused = False
    fx_callback = None
    ui = None
    collider = None

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)

        self.check_mem()
        self.ui = ui_screen(self.display, self.num_lives)

        # _thread.start_new_thread(self.start_music, [])

        self.init_camera()
        self.sprites = SpriteManager(display, 100, self.camera, self.lane_width)

        self.player = PlayerSprite(camera=self.camera)
        self.display.fps = self.fps

        self.collider = Collider(self.player, self.sprites)
        self.collider.add_callback(self.do_crash)


    async def mock_update_score(self):
        while True:
            now = random.randrange(0, 100000)
            self.ui.update_score(int(now))
            await asyncio.sleep(1)

    def run(self):
        self.display.fill(0x9999)
        utime.sleep_ms(1000)
        self.display.fill(0x0)
        print("-- Creating road grid...")

        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)

        print("-- Creating sprites...")
        sprites = self.sprites

        barrier_speed = self.max_ground_speed
        print(f"Sprite speed: {barrier_speed}")

        self.check_mem()

        # Register sprite types
        sprites.add_type(SPRITE_PLAYER, "/img/bike_sprite.bmp", 5, 32, 22, 4, None)  # Assuming 8-bit color depth
        sprites.add_type(SPRITE_BARRIER_LEFT, "/img/road_barrier_yellow.bmp", barrier_speed, 24, 15, 4, None)
        sprites.add_type(SPRITE_BARRIER_RIGHT, "/img/road_barrier_yellow_inv.bmp", barrier_speed, 24, 15, 4, None)
        # sprites.add_type(SPRITE_TYPE_BARRIER_RED, "/img/road_barrier_red.bmp", barrier_speed * 2, 22, 8, 4, None)
        sprites.add_type(SPRITE_LASER_WALL, "/img/laser_wall.bmp", barrier_speed * 2, 22, 10, 4, None)
        sprites.add_type(SPRITE_LASER_WALL_POST, "/img/laser_wall_post.bmp", barrier_speed, 10, 24, 4, None, 0x0000)
        sprites.add_type(SPRITE_LASER_ORB, "/img/laser_orb.bmp", barrier_speed, 16, 16, 4, None, 0x0000)
        sprites.add_type(SPRITE_WHITE_DOT, "/img/white_dot.bmp", barrier_speed, 4, 4, 4, None)
        # sprites.add_action(SPRITE_TYPE_LASER_ORB, actions.ground_laser)

        """ These numbers were derived by trial and error in order to match up the sprites perspective to the road grid"""
        lane_width = self.lane_width
        half_lane_width = self.lane_width // 2
        start_x = -half_lane_width -(lane_width*2)


        self.check_mem()

        img_height = 15
        start = 2000
        every = +100
        num_rows = 10

        for i in range(num_rows):
            new_sprite, idx = sprites.create(SPRITE_BARRIER_RIGHT, x=start_x, y=img_height,
                                             z=start + i * every)
            sprites.set_lane(new_sprite, 0)

        for i in range(num_rows):
            new_sprite, idx = sprites.create(SPRITE_BARRIER_RIGHT, x=start_x, y=img_height,
                                             z=start + i * every)
            sprites.set_lane(new_sprite, 1)

        # for i in range(6):
        #     new_sprite, idx = sprites.create(SPRITE_LASER_WALL, x=start_x, y=img_height,
        #                                      z=start + i * every)
        #     sprites.set_lane(new_sprite, 2)

        for i in range(num_rows):
            new_sprite, idx = sprites.create(SPRITE_BARRIER_LEFT, x=start_x, y=img_height,
                                             z=start + i * every)
            sprites.set_lane(new_sprite, 3)

        for i in range(num_rows):
            new_sprite, idx = sprites.create(SPRITE_BARRIER_LEFT, x=start_x, y=img_height,
                                             z=start + i * every)
            sprites.set_lane(new_sprite, 4)

        self.check_mem()

        """ Display Thread / 2nd core """
        # _thread.start_new_thread(self.start_display_loop, [])

        self.start_display_loop()
        self.input_task = make_input_handler(self.player)
        loop = asyncio.get_event_loop()
        self.update_score_task = loop.create_task(self.mock_update_score())

        # Start the speed-up task
        self.speed_anim = AnimAttr(self, 'ground_speed', self.max_ground_speed, 1500, easing=AnimAttr.ease_in_out_sine)
        loop.create_task(self.speed_anim.run(fps=60))

        asyncio.run(self.start_main_loop())


    async def update_loop(self):
        start_time_ms = self.last_update_ms = round(utime.ticks_ms())
        self.last_perf_dump_ms = start_time_ms

        print(f"Update loop Start time: {start_time_ms}")
        self.check_mem()
        num_lanes = 5

        # update loop - will run until task cancellation
        try:
            while True:
                self.camera.vp_x = round(self.player.bike_angle * num_lanes)
                self.camera.cam_x = round(self.player.bike_angle * num_lanes)

                # gc.collect()
                self.grid.speed = self.ground_speed
                self.grid.speed_ms = self.ground_speed / 1000
                self.total_frames += 1

                if not self.total_frames % self.fps_every_n_frames:
                    print(f"FPS: {self.fps.fps()}")

                now = utime.ticks_ms()
                elapsed = utime.ticks_diff(now, self.last_update_ms)
                self.last_update_ms = utime.ticks_ms()

                if not self.paused:
                    self.grid.update_horiz_lines(elapsed)
                    self.player.update(elapsed)
                    self.sprites.update_all(elapsed)
                    self.collider.is_collision(self.sprites.pool.active_sprites)

                await asyncio.sleep(1/120)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """

        self.display.fill(0x0000)
        self.grid.show()
        self.sprites.show_all(self.display)
        self.player.show(self.display)
        self.show_fx()
        self.ui.show()

        self.display.show()

        # self.show_perf()
        self.fps.tick()

    def show_fx(self):
        self.sprites.death_anim.update_and_draw()

    def check_collisions(self, colliders):
        if self.player.visible and self.player.active and self.player.has_physics:
            for sprite in colliders:

                # Check collisions
                if ((sprite.draw_y >= self.crash_y_start) and
                        (sprite.draw_y < self.crash_y_end) and
                        (self.sprites.get_lane(sprite) == self.player.current_lane) and
                        self.player.has_physics):
                    print(f"Crash on {self.player.current_lane}")
                    self.do_crash()

                    break  # No need to check other collisions

    def do_crash(self):
        loop = asyncio.get_event_loop()

        # self.display_task.cancel()

        self.paused = True
        self.player.active = False
        self.grid.stop()
        loop.create_task(
            self.sprites.death_anim.start_animation(self.player.x, self.player.y))

        # if not self.ui.remove_life():
        #     self.bike.visible = False
        #     self.ui.show_game_over()
        #     return False


        white = colors.rgb_to_565_v2(colors.hex_to_rgb(0xFFFFFF))
        white = int.from_bytes(white, "big")

        # # Quick flash of white
        # for i in range(1):
        #     self.do_refresh2()
        #     self.display.rect(10, 10, 50, 50, white, fill=white)
        #     self.display.show()
        #
        #     await asyncio.sleep(2)
        #

        # ms = 1000
        # for i in range(0, 3):
        #     self.display.fill(0xFFFF)
        #     self.do_refresh()
        #     await asyncio.sleep(100 / ms)
        #     self.display.fill(0x0000)
        #     self.do_refresh()
        #     await asyncio.sleep(100 / ms)

        self.player.visible = False

        # self.player.start_blink()



        # loop.create_task(self.player.stop_blink())

    def init_camera(self):
        # Camera
        horiz_y: int = 14
        camera_z: int = 60
        camera_y: int = -40
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=70,
            pos_z=-camera_z,
            focal_length=-camera_y+5,
            vp_x=0,
            vp_y=horiz_y)

    def show_perf(self):
        interval = 2000 # Every 2 secs

        now = int(utime.ticks_ms())
        elapsed = now - self.last_perf_dump_ms

        if elapsed > interval:
            prof.dump_profile()
            self.last_perf_dump_ms = int(utime.ticks_ms())
