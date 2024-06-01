import random

from micropython import const

from perspective_camera import PerspectiveCamera
from screen import Screen
from road_grid import RoadGrid
import asyncio
import utime

class GridTestScreen(Screen):
    lane_width: int = const(24)
    ground_speed: int = const(50)
    grid: RoadGrid = None
    camera: PerspectiveCamera
    sprites: []
    sprite_max_z: int = const(1301)
    ground_speed = 1000
    ground_max_speed: int = const(300)
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = const(4)
    crash_y_start = const(48)  # Screen Y of Sprites which will collide with the player
    crash_y_end = const(62)  # Screen Y of end collision
    total_frames = 0

    fps_every_n_frames = 50
    color_shift_every_n_frames = 200


    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)

        self.init_camera()

        """ Display Thread / 2nd core """

    def run(self):

        print("-- Creating road grid...")

        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)
        self.grid.speed = self.ground_speed

        # led = Pin(25, Pin.OUT)
        #
        self.display.fill(0xFFFF)
        # self.display.show()

        """ This will initiate the DMA transfer chain and PIO program to free the CPU from having to deal with the
        display refresh"""
        self.display.start()
        utime.sleep_ms(1000)
        self.display.fill(0x00FF)

        # START()

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
                self.fps.tick()

                # gc.collect()
                self.grid.speed = self.ground_speed
                self.total_frames += 1

                if not self.total_frames % self.fps_every_n_frames:
                    print(f"FPS: {self.fps.fps()}")

                if not self.total_frames % self.color_shift_every_n_frames:
                    color_a = int(random.randrange(0,255)) * 255
                    color_b = random.randrange(0,255)
                    color = color_a + color_b
                    # print(f"Change color to {color}")
                    self.display.fill(int(color))

                await asyncio.sleep(1/200)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """
        # self.display.fill(0xFFFF)
        # self.grid.show()
        utime.sleep_ms(30)

        # self.display.show()
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

    def debug_dma(self, buffer_addr, data_bytes):
        print(f"Framebuf addr: {buffer_addr:16x} / len: {len(data_bytes)}")
        print(f"Contents: ")

        for i in range(64):
            my_str = ''
            for i in range(0, 32, 1):
                my_str += f"{data_bytes[i]:02x}"

            print(my_str)


