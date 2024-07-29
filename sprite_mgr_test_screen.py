import random
import _thread

from micropython import const

from input import make_input_handler
from perspective_camera import PerspectiveCamera
from sprites.player_sprite import PlayerSprite
from screen import Screen
from road_grid import RoadGrid
import asyncio
import utime
from sprites.sprite_manager import SpriteManager
import sprites.sprite_actions as actions

SPRITE_TYPE_PLAYER = const(0)
SPRITE_TYPE_BARRIER_LEFT = const(1)
SPRITE_TYPE_BARRIER_RIGHT = const(2)
SPRITE_TYPE_BARRIER_RED = const(3)
SPRITE_TYPE_LASER_ORB = const(4)

from profiler import Profiler as prof, timed

class GridTestScreen(Screen):
    ground_speed: int = const(-100)
    grid: RoadGrid = None
    camera: PerspectiveCamera
    sprites: None
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


    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        self.init_camera()
        self.sprites = SpriteManager(display, 100, self.camera, self.lane_width)
        self.player = PlayerSprite(camera=self.camera)
        self.display.fps = self.fps


    def run(self):
        self.display.fill(0x9999)
        utime.sleep_ms(1000)
        self.display.fill(0x0)
        print("-- Creating road grid...")

        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)

        print("-- Creating sprites...")
        sprites = self.sprites

        barrier_speed = self.ground_speed / 2
        print(f"Sprite speed: {barrier_speed}")

        self.check_mem()

        # Register sprite types
        sprites.add_type(SPRITE_TYPE_PLAYER, "/img/bike_sprite.bmp", 5, 32, 22, 4, None)  # Assuming 8-bit color depth
        sprites.add_type(SPRITE_TYPE_BARRIER_LEFT, "/img/road_barrier_yellow.bmp", -0.15, 24, 15, 4, None)
        sprites.add_type(SPRITE_TYPE_BARRIER_RIGHT, "/img/road_barrier_yellow_inv.bmp", -0.15, 24, 15, 4, None)
        sprites.add_type(SPRITE_TYPE_BARRIER_RED, "/img/road_barrier_red.bmp", barrier_speed, 26, 8, 4, None)
        sprites.add_type(SPRITE_TYPE_LASER_ORB, "/img/laser_orb.bmp", barrier_speed * 2, 16, 16, 4, None, 0x0000)
        sprites.add_action(SPRITE_TYPE_LASER_ORB, actions.ground_laser)

        # frame_width = 32,
        # frame_height = 22
        # )
        # self.x = 25
        # self.y = 42
        # self.set_alpha(0)
        # self.set_frame(8)  # middle frame


        start = 700
        img_height = 8 # Needed because the screenspace Y is at the top, but 3D has Y at the bottom

        """ These numbers were derived by trial and error in order to match up the sprites perspective to the road grid"""
        lane_width = self.lane_width + 2
        half_lane_width = self.lane_width // 2
        start_x = -half_lane_width -(lane_width*2)

        #
        # every = -50
        # for i in range(20):
        #     # rand_x = random.randrange(-30, 20)
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=start_x, y=img_height, z=start + i*every)
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=start_x+lane_width, y=img_height, z=start + i*every)
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=start_x+lane_width*2, y=img_height, z=start + i*every)
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=start_x+lane_width*3, y=img_height, z=start + i*every)
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=start_x+lane_width*4, y=img_height, z=start + i*every)

        self.check_mem()

        orb_height = 50
        every = 50
        start = 1000
        for i in range(20):
            start_z = start + i*every
            sprites.create(SPRITE_TYPE_LASER_ORB, x=start_x + lane_width * 0, y=orb_height, z=start_z)
            # sprites.create(SPRITE_TYPE_LASER_ORB, x=start_x + lane_width * 1, y=orb_height, z=start_z)
            # sprites.create(SPRITE_TYPE_LASER_ORB, x=start_x + lane_width * 3, y=orb_height, z=start_z)
            sprites.create(SPRITE_TYPE_LASER_ORB, x=start_x + lane_width * 4, y=orb_height, z=start_z)

        self.check_mem()

        # start = 3000
        # for i in range(20):
        #     rand_x = random.randrange(-30, 20)
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=-half_lane_width+rand_x, y=0, z=start + i*every)
        #
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=-(lane_width*2)-lane_width, y=0, z=start + i*every)
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=-lane_width-lane_width, y=0, z=start + i*every)
        #
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=lane_width-lane_width, y=0, z=start + i*every)
        #     sprites.create(SPRITE_TYPE_BARRIER_RED, x=lane_width*2-lane_width, y=0, z=start + i*every)

        self.check_mem()

        """ Display Thread / 2nd core """
        # _thread.start_new_thread(self.start_display_loop, [])
        self.start_display_loop()
        self.input_task = make_input_handler(self.player)
        asyncio.run(self.start_main_loop())


    async def update_loop(self):
        start_time_ms = self.last_update_ms = round(utime.ticks_ms())
        self.last_perf_dump_ms = start_time_ms

        print(f"Update loop Start time: {start_time_ms}")
        self.check_mem()

        # update loop - will run until task cancellation
        try:
            while True:
                num_lanes = 5

                self.camera.vp_x = round(self.player.bike_angle * num_lanes)
                self.camera.cam_x = round(self.player.bike_angle * num_lanes)

                # gc.collect()
                self.grid.speed = self.ground_speed
                self.grid.speed_ms = self.ground_speed / 1000
                self.total_frames += 1

                if not self.total_frames % self.fps_every_n_frames:
                    print(f"FPS: {self.fps.fps()}")

                # if not self.total_frames % self.color_shift_every_n_frames:
                #     self.display.fill(0x0)
                #
                #     color_a = int(random.randrange(0,255)) * 255
                #     color_b = random.randrange(0,255)
                #     color = color_a + color_b
                #     # print(f"Change color to {color}")
                #     self.display.fill(int(color))

                now = int(utime.ticks_ms())
                elapsed = now - self.last_update_ms
                self.last_update_ms = int(utime.ticks_ms())

                self.player.update(elapsed)
                self.sprites.update_all(elapsed)
                self.grid.update_horiz_lines(elapsed)
                self.grid.update_horiz_lines(elapsed)

                await asyncio.sleep(1/60)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """

        self.display.fill(0x0000)
        self.grid.show()
        self.sprites.show_all(self.display)
        self.player.show(self.display)
        self.display.show()

        # self.show_perf()
        self.fps.tick()

    def init_camera(self):
        # Camera
        horiz_y: int = 16
        camera_z: int = 60
        camera_y: int = -40
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=60,
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
