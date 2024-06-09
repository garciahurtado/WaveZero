import gc

from input import make_input_handler
from stages.stage_1 import Stage1
gc.collect()

from ui_elements import ui_screen
from micropython import const

gc.collect()

import utime

from image_loader import ImageLoader

import _thread

import framebuf
import utime as time
import uasyncio as asyncio

from anim.anim_attr import AnimAttr
from player_sprite import PlayerSprite
from fx.crash import Crash

from screen import Screen
from road_grid import RoadGrid
from perspective_camera import PerspectiveCamera
from sprites.sprite import Sprite
from title_screen import TitleScreen
import color_util as colors
# from primitives.encoder import Encoder

start_time_ms = 0

class GameScreen(Screen):
    display: framebuf.FrameBuffer
    grid: RoadGrid = None
    camera: PerspectiveCamera
    sprites: []
    enemies: []
    ui: ui_screen
    crash_fx: None
    sprite_max_z: int = const(1301)
    ground_speed = 0
    ground_max_speed: int = const(300)
    saved_ground_speed = 0
    lane_width: int = const(24)
    num_lives: int = const(4)
    crash_y_start = const(48) # Screen Y of Sprites which will collide with the player
    crash_y_end = const(62) # Screen Y of end collision

    # Bike movement
    bike: PlayerSprite
    current_enemy_lane = 0
    current_enemy_palette = None

    encoder = None
    encoder_last_pos = {'pos': 0}

    # Threading
    update_task: None
    display_task: None
    input_task: None
    speed_anim: None

    refresh_lock: None
    sprite_lock: None
    loop: None
    stage: None
    sun_x_start: 0
    handler: None

    def __init__(self, display, *args, **kwargs):
        gc.collect()

        self.enemies = []
        self.flying_enemies = []

        self.mem_marker('- Before init display')
        super().__init__(display, *args, **kwargs)

        self.init_camera()

        self.ui = ui_screen(self.display, self.num_lives)

        """ Display Thread """
        # _thread.start_new_thread(self.start_display_loop, [])
        self.start_display_loop()

        self.mem_marker('--- Before preload images ---')
        self.preload_images()
        self.mem_marker('--- After preload images ---')

        self.bike = PlayerSprite(camera=self.camera)
        self.handler = make_input_handler(self.bike)


        self.mem_marker('%%% Before FX init %%%')
        self.crash_fx = Crash(self.display, self.bike)

        #self.mem_marker('- After init display')
        self.init_stage()

        self.sun_x_start = 39
        self.num_lanes = 5
        self.bike.blink = True

        self.loop = asyncio.get_event_loop()

    def preload_images(self):
        images = [
            {"name": "laser_tri.bmp", "width": 20, "height": 20, "color_depth": 4},
            {"name": "road_barrier_yellow.bmp", "width": 24, "height": 15, "color_depth": 4},
            {"name": "bike_sprite.bmp", "width": 32, "height": 22, "color_depth": 4},
            {"name": "sunset.bmp"},
            {"name": "life.bmp"},
        ]

        ImageLoader.load_images(images, self.display)


    def run(self):
        self.init_sprites()
        self.init_road_grid()

        asyncio.run(self.main_loop())

    def init_sprites(self):
        sun = Sprite("/img/sunset.bmp")
        sun.x = self.sun_x_start
        sun.y = 7
        self.add(sun)
        self.sun = sun
        self.bike.visible = True

    def init_road_grid(self):
        print("Creating road grid...")
        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)
        self.grid.speed = self.ground_speed

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

    async def main_loop(self):
        self.stage.start()
        self.input_task = make_input_handler(self.bike)

        await asyncio.gather(
            self.update_loop(),
            self.update_fps(),
        )

    async def update_loop(self):
        sun = self.sun
        loop = asyncio.get_event_loop()

        start_time_ms = round(time.ticks_ms())
        print(f"Update loop Start time: {start_time_ms}")
        self.check_mem()

        self.add(self.bike) # Add after the obstacles, to it appears on top

        self.restart_game()
        bike_y = self.bike.y
        self.bike.y = 64 # Hide it below the screen

        # Animate the road speed from 0 to max
        self.speed_anim = AnimAttr(self, 'ground_speed', self.ground_max_speed, 1 * 1000)

        # Make the bike slide in from the bottom
        anim = AnimAttr(self.bike, 'y', bike_y, 1 * 1000)
        loop.create_task(self.speed_anim.run(fps=30))
        loop.create_task(anim.run(fps=30))

        if not self.last_tick:
            self.last_tick = utime.ticks_ms()

        # update loop - will run until task cancellation
        try:
            while True:
                self.grid.speed = self.ground_speed
                # self.stage.event_chain.speed = -self.ground_speed
                self.bike.update()

                # REFACTOR
                # used so that 3D sprites will follow the movement of lanes as they change perspective
                # Not sure why the multipliers are needed, or how to get rid of them
                mult1 = self.num_lanes
                mult2 = self.num_lanes

                self.camera.vp["x"] = round(self.bike.bike_angle * mult1)
                self.camera.pos["x"] = round(self.bike.bike_angle * mult2)
                sun.x = self.sun_x_start - round(self.bike.bike_angle*4)

                # Calculate elapsed time
                now = utime.ticks_ms()
                elapsed = now - self.last_tick
                self.last_tick = now

                if elapsed:
                    self.stage.update(elapsed)
                    self.detect_collisions(self.stage.sprites)

                # Wait for next update
                await asyncio.sleep(1 // 200)

        except asyncio.CancelledError:
            return False


    def init_stage(self):
        self.stage = Stage1(
            self.camera,
            lane_width=self.lane_width,
            speed=self.ground_max_speed,
            sprite_max_z=self.sprite_max_z
            )

    def init_enemies(self):
        self.enemies = []

        # Create road obstacles
        num_groups = 0
        palette_size = 4
        palette_width = 16
        num_palettes = int(palette_width / palette_size)
        # print(f"Creating {num_palettes} palettes")

        # self.enemy_palettes = Spritesheet(filename='/img/enemy_gradients.bmp', frame_width=4, frame_height=1)
        # self.enemy_palettes.set_frame(0)
        # all_palettes = []
        # self.check_mem()

        # print(f"Loaded {len(self.enemy_palettes.frames)} enemy palettes")

        # Split up the palette gradient into individual sub-palettes
        # for i in range(int(palette_width / palette_size)):
        #     self.enemy_palettes.set_frame(i)
        #
        #     pixels = self.enemy_palettes.frames[0].pixels # Colors for a single group (4 palettes)
        #
        #     orig_palette = [
        #         (0,0,0),
        #         (0,0,0),
        #         (255,255,255),
        #         (0,0,0),
        #     ]
        #     for j in range(palette_size):
        #         print(f"Creating palette {j}")
        #         new_palette = colors.make_framebuffer_palette(orig_palette)
        #
        #         color_idx = pixels.pixel(j, 0)
        #         color = self.enemy_palettes.palette.get_bytes(color_idx)
        #         new_palette.set_bytes(0, color)
        #
        #         all_palettes.append(new_palette) # We should end up with 16 palettes total

        # print(f"Num enemy palettes: {len(all_palettes)}")
        # Create enemy / obstacle groups

        for i in range(0, num_groups):
            print(f"Created group {i}")
            # Set a random palette
            # palette_num = random.randrange(0, 4)
            # print(f"All palettes size: {len(all_palettes)}")
            # current_enemy_palettes = all_palettes[i*palette_size:(i+1)*palette_size]

            self.create_group(self.base_group, i)
    def detect_collisions(self, colliders):
        if self.bike.visible and self.bike.active:
            for sprite in colliders:
                if not sprite.has_physics:
                    continue

                # Check collisions
                if ((sprite.draw_y >= self.crash_y_start) and
                    (sprite.draw_y < self.crash_y_end) and
                    (sprite.get_lane() == self.bike.current_lane) and
                    self.bike.has_physics):

                    print(f"Crash on {self.bike.current_lane}")
                    self.bike.active = False
                    self.do_crash()
                    break # No need to check other collisions

    def create_group(self, base_group, i):
        group = base_group.clone()
        #group.z = group.z + (i * 50)
        group.set_camera(self.camera)
        group.grid = self.grid
        group.reset()

        self.add(group)
        self.enemies.append(group)

        return group

    def do_refresh(self):
        """ Overrides parent method """
        self.display.fill(0)
        if self.grid:
            self.grid.show()

        self.draw_sprites()
        self.display.show()
        self.fps.tick()
        # print(f"Speed: {self.ground_speed}")

    def do_crash(self):
        self.pause()

        white = colors.rgb_to_565(colors.hex_to_rgb(0xFFFFFF))

        # Visual flash
        for i in range(3):
            self.display.fill(white)
            self.display.show()
            self.do_refresh()

        self.crash_fx.create_particles()
        self.crash_fx.anim_particles()

        if not self.ui.remove_life():
            self.bike.visible = False
            self.ui.show_game_over()
            return False

        self.bike.blink = True
        self.restart_game()

    def pause(self):
        self.saved_ground_speed = self.ground_speed
        # self.input_task.cancel()
        self.grid.speed = self.ground_speed = 0

    def unpause(self):
        self.ground_speed = self.saved_ground_speed
        self.grid.speed = self.ground_speed

    def restart_game(self):
        """After losing a life, we reset all the obstacle sprites and the speed"""

        for group in self.enemies:
            group.reset()

        loop = asyncio.get_event_loop()
        loop.create_task(self.bike.stop_blink())  # Will run after a few seconds
        self.unpause()

    def start_display_loop(self):
        """
        Starts / restarts the input loop and display loop. Should be ran on Core #2
        """

        # if getattr(self, 'input_task', False):
        #     self.input_task.cancel()

        # if getattr(self, 'display_task', False):
        #     self.display_task.cancel()

        # self.display.start()

        # Restart the game display and input
        loop = asyncio.get_event_loop()
        self.display_task = loop.create_task(self.refresh_display())

    async def update_fps(self):
        while True:

            # Show the FPS in the score label
            fps = int(self.fps.fps())
            self.ui.update_score(fps)

            await asyncio.sleep(0.2)

    def draw_sprites(self):
        super().draw_sprites()
        self.stage.show(self.display)
        self.ui.show()


if __name__ == "__main__":
    scr = TitleScreen()
    scr.run()
