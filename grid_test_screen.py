import random
import _thread

from micropython import const

from perspective_camera import PerspectiveCamera
from screen import Screen
from road_grid import RoadGrid
import asyncio
import utime

class GridTestScreen(Screen):
    lane_width: int = const(24)
    ground_speed: int = const(1000)
    grid: RoadGrid = None
    camera: PerspectiveCamera
    sprites: []
    sprite_max_z: int = const(1301)
    ground_max_speed: int = const(300)
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = const(4)
    total_frames = 0

    fps_every_n_frames = 30
    color_shift_every_n_frames = 1000


    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)

        self.init_camera()
        self.display.fps = self.fps

        """ Display Thread / 2nd core """

    def run(self):
        # led = Pin(25, Pin.OUT)
        #
        self.display.fill(0x9999)
        utime.sleep_ms(1000)
        self.display.fill(0x0)

        print("-- Creating road grid...")

        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)
        self.grid.speed = self.ground_speed

        _thread.start_new_thread(self.start_display_loop, [])
        # self.start_display_loop()

        asyncio.run(self.main_loop())

    def start_display_loop(self):
        # Start display and input
        loop = asyncio.get_event_loop()
        self.display_task = loop.create_task(self.refresh_display())

    async def main_loop(self):
        await asyncio.gather(
            self.update_loop(),
            # self.update_fps(),
        )

    async def update_loop(self):
        start_time_ms = round(utime.ticks_ms())
        print(f"Update loop Start time: {start_time_ms}")
        self.check_mem()

        # update loop - will run until task cancellation
        try:
            while True:

                # gc.collect()
                self.grid.speed = self.ground_speed
                self.total_frames += 1

                if not self.total_frames % self.fps_every_n_frames:
                    print(f"FPS: {self.fps.fps()}")

                if not self.total_frames % self.color_shift_every_n_frames:
                    self.display.fill(0x0)

                    color_a = int(random.randrange(0,255)) * 255
                    color_b = random.randrange(0,255)
                    color = color_a + color_b
                    # print(f"Change color to {color}")
                    self.display.fill(int(color))

                await asyncio.sleep(1/120)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """

        """ Wait until the display is done writing to its 2nd buffer"""
        # while not self.display.can_write():
        #     pass

        self.display.fill(0x0)
        self.grid.show()
        self.display.show()

        self.fps.tick()

    def init_camera(self):
        # Camera
        horiz_y: int = 16
        camera_z: int = 64
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=54,
            pos_z=-camera_z,
            focal_length=camera_z,
            vp_x=0,
            vp_y=horiz_y+2)
        self.camera.horiz_z = self.sprite_max_z



