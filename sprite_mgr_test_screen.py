import random
import _thread

from micropython import const

from perspective_camera import PerspectiveCamera
from sprites.player_sprite import PlayerSprite
from screen import Screen
from road_grid import RoadGrid
import asyncio
import utime
from sprites.sprite_manager import SpriteManager
SPRITE_TYPE_PLAYER = const(0)
SPRITE_TYPE_BARRIER_LEFT = const(1)
SPRITE_TYPE_BARRIER_RIGHT = const(2)

class GridTestScreen(Screen):
    lane_width: int = const(24)
    ground_speed: int = const(2000)
    grid: RoadGrid = None
    camera: PerspectiveCamera
    sprites: None
    sprite_max_z: int = const(1301)
    ground_max_speed: int = const(300)
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = const(4)
    total_frames = 0
    last_update_ms = 0
    fps_every_n_frames = 30
    color_shift_every_n_frames = 1000
    player = None


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

        # Register sprite types
        sprites.add_type(SPRITE_TYPE_PLAYER, "/img/bike_sprite.bmp", 5, 32, 22, 4, None)  # Assuming 8-bit color depth
        sprites.add_type(SPRITE_TYPE_BARRIER_LEFT, "/img/road_barrier_yellow.bmp", -0.15, 24, 15, 4, None)
        sprites.add_type(SPRITE_TYPE_BARRIER_RIGHT, "/img/road_barrier_yellow_inv.bmp", -0.15, 24, 15, 4, None)

        # frame_width = 32,
        # frame_height = 22
        # )
        # self.x = 25
        # self.y = 42
        # self.set_alpha(0)
        # self.set_frame(8)  # middle frame
        self.check_mem()

        start = 3000
        img_width = 24
        half_img_width = 12
        half_img_height = 7 # Needed because the screenspace Y is at the top, but 3D has Y at the bottom
        every = -40
        for i in range(30):
            # rand_x = random.randrange(-30, 20)
            sprites.create(SPRITE_TYPE_BARRIER_RIGHT, x=-62, y=half_img_height, z=start + i*every)
            sprites.create(SPRITE_TYPE_BARRIER_RIGHT, x=-36, y=half_img_height, z=start + i*every)
            # sprites.create(SPRITE_TYPE_BARRIER_RIGHT, x=-12, y=0, z=start + i*every)
            sprites.create(SPRITE_TYPE_BARRIER_LEFT, x=+12, y=half_img_height, z=start + i*every)
            sprites.create(SPRITE_TYPE_BARRIER_LEFT, x=+36, y=half_img_height, z=start + i*every)

            # sprites.create(SPRITE_TYPE_BARRIER_RIGHT, x=-half_img_width+rand_x, y=0, z=start + i*every)

            # sprites.create(SPRITE_TYPE_BARRIER_RIGHT, x=-(img_width*2)-img_width, y=0, z=start + i*every)
            # sprites.create(SPRITE_TYPE_BARRIER_RIGHT, x=-img_width-img_width, y=0, z=start + i*every)
            #
            # sprites.create(SPRITE_TYPE_BARRIER_LEFT, x=img_width-img_width, y=0, z=start + i*every)
            # sprites.create(SPRITE_TYPE_BARRIER_LEFT, x=img_width*2-img_width, y=0, z=start + i*every)

        self.check_mem()

        """ Display Thread / 2nd core """
        _thread.start_new_thread(self.start_display_loop, [])

        asyncio.run(self.start_main_loop())


    async def update_loop(self):
        start_time_ms = self.last_update_ms = round(utime.ticks_ms())
        print(f"Update loop Start time: {start_time_ms}")
        self.check_mem()

        # update loop - will run until task cancellation
        try:
            while True:

                # gc.collect()
                self.grid.speed = self.ground_speed / 20
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
                ellapsed = now - self.last_update_ms
                self.last_update_ms = int(utime.ticks_ms())

                self.player.update(ellapsed)
                self.sprites.update_all(ellapsed)
                self.grid.update_horiz_lines(ellapsed)

                await asyncio.sleep(1/30)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """

        self.display.fill(0x0)
        self.grid.show()
        self.sprites.show_all(self.display)
        self.player.show(self.display)
        self.display.show()

        self.fps.tick()

    def init_camera(self):
        # Camera
        horiz_y: int = 16
        camera_z: int = 50
        camera_y: int = -40
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=54,
            pos_z=-camera_z,
            focal_length=-camera_y,
            vp_x=0,
            vp_y=horiz_y)
        self.camera.horiz_z = self.sprite_max_z



