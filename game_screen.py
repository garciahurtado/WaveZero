import _thread
import gc
import random
import micropython

import framebuf
import utime as time
import uasyncio as asyncio

from anim.anim_attr import AnimAttr
from fx.crash import Crash
from player_sprite import PlayerSprite
from scaled_sprite import ScaledSprite
from screen import Screen
from road_grid import RoadGrid
from perspective_camera import PerspectiveCamera
from encoder import Encoder
from sprite import Sprite
from spritesheet import Spritesheet
from image_loader import ImageLoader
from sprite_group import SpriteGroup, SpriteEnemyGroup
from title_screen import TitleScreen
import color_util as colors
from ui_elements import ui_screen

start_time_ms = 0

class GameScreen(Screen):
    display: framebuf.FrameBuffer
    grid: RoadGrid
    camera: PerspectiveCamera
    sprites: []
    enemies: []
    flying_enemies: []
    ui: ui_screen
    crash_fx: None
    sprite_max_z = 1000
    ground_speed = 8
    saved_ground_speed = 0
    lane_width = 24
    num_lives = 2
    crash_y = 50 # Screen Y of Sprites which will start colliding with the player

    # Bike movement
    bike: PlayerSprite
    current_enemy_lane = 0
    current_enemy_palette = None

    encoder: Encoder
    encoder_last_pos = {'pos': 0}

    update_task: None
    display_task: None
    input_task: None
    speed_anim: None

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        gc.collect()
        print(f"Free memory __init__: {gc.mem_free():,} bytes")
        self.init_camera()
        self.preload_images()
        self.enemies = []
        self.flying_enemies = []
        micropython.alloc_emergency_exception_buf(100)

    def preload_images(self):
        images = [
            {"name": "enemy_gradients.bmp", "width": 4, "height": 1},
            {"name": "bike_sprite.bmp", "width": 37, "height": 22},
            {"name": "road_wall.bmp", "width": 10, "height": 20},
            {"name": "sunset.bmp"},
            {"name": "life.bmp"},
            ]

        ImageLoader.load_images(images, self.display)

        self.bike = PlayerSprite(camera=self.camera)
        self.crash_fx = Crash(self.display, self.bike)

    def run(self):
        gc.collect()
        self.check_mem()

        self.encoder = Encoder(27, 26)
        self.ui = ui_screen(self.display, self.num_lives)

        self.init_sprites()
        self.init_enemies()

        # Start the display render / input handling loop in core #2
        gc.collect()
        self.check_mem()

        _thread.start_new_thread(self.start_display_loop, [])

        asyncio.run(self.main_async())


    def init_sprites(self):
        sun = Sprite("/img/sunset.bmp")
        sun.x = 39
        sun.y = 7
        self.add(sun)
        self.sun = sun

        print("Creating road grid...")
        self.check_mem()
        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)
        self.grid.speed = self.ground_speed
        self.check_mem()

    def init_camera(self):
        # Camera
        horiz_y = 16
        camera_z = 64
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=63,
            pos_z=-camera_z,
            focal_length=camera_z,
            vp_x=0,
            vp_y=horiz_y)
        self.camera.horiz_z = self.sprite_max_z

    async def main_async(self):


        gc.collect()
        loop = asyncio.get_event_loop()
        self.update_task = loop.create_task(self.update_loop())

        max_speed = 50
        self.speed_anim = AnimAttr(self, 'ground_speed', max_speed, 240000)

        gc.collect()
        await asyncio.gather(
            self.update_fps(),
        )

    async def update_loop(self):
        sun_x_start = 39
        sun = self.sun
        loop = asyncio.get_event_loop()

        start_time_ms = round(time.ticks_ms())
        print(f"Update loop Start time: {start_time_ms}")
        self.check_mem()

        self.add(self.bike) # Add after the obstacles, to it appears on top
        bike_angle = 0
        turn_incr = 0.2  # turning speed
        half_width = int(self.camera.half_width)

        self.restart_game()
        bike_y = self.bike.y
        self.bike.y = 64 # Hide it below the screen

        # Make the bike slide in from the bottom
        anim = AnimAttr(self.bike, 'y', bike_y, 1 * 1000)
        loop.create_task(anim.run(fps=30))
        loop.create_task(self.speed_anim.run(fps=5))

        # Draw loop - will run until task cancellation
        try:
            while True:
                self.grid.speed = self.ground_speed
                for sprite in self.enemies:
                    sprite.speed = -self.ground_speed * 2

                # Handle bike swerving
                target_lane = self.bike.target_lane
                current_lane = self.bike.current_lane
                target_angle = (target_lane * (2 / 4)) - 1

                if target_lane < current_lane:
                    bike_angle = bike_angle - turn_incr
                    if bike_angle < target_angle:
                        self.bike.current_lane = target_lane
                        bike_angle = target_angle

                elif target_lane > current_lane:
                    bike_angle = bike_angle + turn_incr
                    if bike_angle > target_angle:
                        self.bike.current_lane = target_lane
                        bike_angle = target_angle

                bike_angle = min(bike_angle, 1)  # Clamp the input between -1 and 1
                line_offset = self.bike.turn(bike_angle)  # bike_angle->(-1,1)
                self.bike.x = int((line_offset * 32) + half_width - 18)

                # REFACTOR
                # used so that 3D sprites will follow the movement of lanes as they change perspective
                # Not sure why the multipliers are needed, or how to get rid of them
                mult1 = 4
                mult2 = 5

                self.camera.vp["x"] = int(bike_angle * mult1)
                self.camera.pos["x"] = int(bike_angle * mult2)
                sun.x = sun_x_start - int(bike_angle*5)

                for sprite in self.sprites:
                    sprite.update()

                self.detect_collisions(self.enemies)

                await asyncio.sleep(1 / 90)

        except asyncio.CancelledError:
            return False

        # Wait for next update

    def init_enemies(self):
        self.enemies = []

        # Create flying triangles
        # for i in range(0,4):
        #     enemy = ScaledSprite(z=100, camera=self.camera, filename='/img/laser_tri.bmp', x=-40+(i*20), y=80)
        #     enemy.set_alpha(2)
        #     enemy.is3d = True
        #     self.flying_enemies.append(enemy)
        #     self.add(enemy)

        # Create road obstacles
        num_groups = 4
        palette_size = 4
        palette_width = 16
        num_palettes = int(palette_width / palette_size)
        print(f"Creating {num_palettes}")

        self.enemy_palettes = Spritesheet(filename='/img/enemy_gradients.bmp', frame_width=4, frame_height=1)
        self.enemy_palettes.set_frame(0)
        all_palettes = []
        self.check_mem()

        print(f"{len(self.enemy_palettes.frames)} enemy palettes")
        # Split up the palette gradient into individual sub-palettes
        for i in range(num_groups):
            print(f"Group {i}")
            self.enemy_palettes.set_frame(i)

            pixels = self.enemy_palettes.frames[0].pixels # Colors for a single group (4 palettes)

            for j in range(palette_size):
                print(f"Creating palette {j}")
                new_palette = colors.FramebufferPalette(bytearray(3 * 2))
                color_idx = pixels.pixel(j, 0)
                color = self.enemy_palettes.palette.get_bytes(color_idx)

                new_palette.set_bytes(0, color)
                new_palette.set_rgb(1, (255,255,255))
                new_palette.set_rgb(2, (0,0,0,))

                all_palettes.append(new_palette) # We should end up with 16 palettes total

        print(f"Num enemy palettes: {len(all_palettes)}")
        # Create enemy / obstacle groups
        base_group = SpriteGroup(
            num_elements=4,
            palette_gradient=all_palettes[0],
            pos_delta={"x": 0, "y": 0, "z": 10},
            filename="/img/road_wall.bmp",
            frame_width=10,
            frame_height=20,
            lane_width=self.lane_width,
            x=50,
            y=0,
            z=2000
        )
        base_group.grid = self.grid
        # base_group.visible = False

        for i in range(0, num_groups):
            # Set a random palette
            palette_num = random.randrange(0, 4)
            print(f"All palettes size: {len(all_palettes)}")
            current_enemy_palettes = all_palettes[i*palette_size:(i+1)*palette_size]

            group = self.create_group(base_group, current_enemy_palettes)
            group.z = group.z + (i * 500)
            group.set_alpha(1)

            self.add(group)
            self.enemies.append(group)

    def detect_collisions(self, colliders):
        if self.bike.visible and self.bike.active:
            for sprite in colliders:

                # Check collisions
                if ((sprite.draw_y >= self.crash_y) and
                        (sprite.draw_y < (self.display.height - 2)) and
                        (sprite.get_lane() == self.bike.current_lane) and
                        not self.bike.blink):
                    print(f"Crash on {self.bike.current_lane}")
                    self.bike.active = False
                    self.do_crash()
                    break # No need to check other collisions

    def create_group(self, base_group, enemy_palettes):
        group = base_group.clone()
        group.instance_palettes = enemy_palettes
        group.pos_delta = {"x": 0, "y": 0, "z": 20}
        group.grid = self.grid
        group.visible = True
        group.set_camera(self.camera)
        group.reset()

        return group

    def do_refresh(self):
        """ Overrides parent method """
        self.display.fill(0)
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
            self.input_task.cancel()
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

        if getattr(self, 'input_task', False):
            self.input_task.cancel()

        if getattr(self, 'display_task', False):
            self.display_task.cancel()

        # Restart the game display and input
        loop = asyncio.get_event_loop()

        #self.display_task = loop.create_task(self.refresh_display())
        #self.input_task = loop.create_task(self.get_input(self.encoder, self.encoder_last_pos))

    def display_thread(self):
        """ Display refresh thread will be executed by core #2 """

        loop = asyncio.get_event_loop()

        # asyncio.gather(self.refresh_display())
        loop.create_task(self.refresh_display())


    async def update_fps(self):
        while True:

            # Show the FPS in the score label
            fps = int(self.fps.fps())
            self.ui.update_score(fps)

            await asyncio.sleep(0.2)

    async def get_input(self, encoder, last_pos):
        while True:
            position = encoder.value
            if position > last_pos['pos']:
                self.bike.move_left()
                last_pos['pos'] = position
            elif position < last_pos['pos']:
                self.bike.move_right()
                last_pos['pos'] = position

            await asyncio.sleep_ms(70)

    def draw_sprites(self):
        super().draw_sprites()
        self.ui.show()


if __name__ == "__main__":
    scr = TitleScreen()
    scr.run()
