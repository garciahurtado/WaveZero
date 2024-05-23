from micropython import const
import _thread

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

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        self.init_camera()

        """ Display Thread / 2nd core """

    def run(self):
        print("Creating road grid...")

        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)
        self.grid.speed = self.ground_speed

        _thread.start_new_thread(self.start_display_loop, [])
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

        if not self.last_tick:
            self.last_tick = utime.ticks_ms()

        # update loop - will run until task cancellation
        try:
            while True:
                self.grid.speed = self.ground_speed
                self.total_frames += 1
                fps_every_n_frames = 10

                if not self.total_frames % fps_every_n_frames:
                    print(f"FPS: {self.fps.fps()}")

                await asyncio.sleep(1/1000)

        except asyncio.CancelledError:
            return False

    def do_refresh(self):
        """ Overrides parent method """
        self.display.fill(0)
        self.grid.show()

        self.display.show()
        self.last_tick = self.fps.tick()

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


