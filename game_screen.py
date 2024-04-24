import _thread
import gc
import random

import utime as time
import uasyncio as asyncio

from fx.crash import Crash
from player_sprite import PlayerSprite
from screen import Screen
from road_grid import RoadGrid
from perspective_sprite import PerspectiveSprite
from perspective_camera import PerspectiveCamera
from encoder import Encoder
from sprite import Sprite, Spritesheet, ImageLoader
from sprite_group import SpriteGroup
from title_screen import TitleScreen
import color_util as colors
from ui_elements import ui_screen

start_time_ms = 0

class GameScreen(Screen):
    display: None
    grid: None
    camera: None
    sprites: []
    enemies: []
    ui: ui_screen
    crash_fx: None
    sprite_max_z = 1000
    ground_speed = 0
    max_ground_speed = 11
    lane_width = 24

    # Bike movement
    bike: PlayerSprite
    current_enemy_lane = 0
    current_enemy_palette = None

    encoder: Encoder
    encoder_last_pos = {'pos': 0}

    update_task: None
    display_task: None
    input_task: None

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        gc.collect()
        print(f"Free memory __init__: {gc.mem_free():,} bytes")
        self.ground_speed = self.max_ground_speed
        self.preload_images()
        self.enemies = []

    def preload_images(self):
        images = [
            {"name": "road_wall.bmp", "width": 10, "height": 20},
            {"name": "bike_sprite.bmp", "width": 37, "height": 22},
            {"name": "sunset.bmp"},
            {"name": "life.bmp"},
            ]

        ImageLoader.load_images(images, self.display)

        self.bike = PlayerSprite()
        self.crash_fx = Crash(self.display, self.bike)

    def run(self):
        gc.collect()
        print(f"Free memory before main loop:  {gc.mem_free():,} bytes")

        self.encoder = Encoder(27, 26)
        self.ui = ui_screen(self.display)
        asyncio.run(self.main_async())

    async def main_async(self):
        sun_x_start = 39
        sun = Sprite("/img/sunset.bmp")
        sun.x = 39
        sun.y = 7
        self.add(sun)

        # Camera
        horiz_y = 16
        camera_z = 72

        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=64,
            pos_z=-camera_z,
            focal_length=camera_z,
            vp_x=0,
            vp_y=horiz_y)
        self.camera.horiz_z = self.sprite_max_z

        self.grid = RoadGrid(self.camera, self.display, lane_width=self.lane_width)

        loop = asyncio.get_event_loop()

        self.update_task = loop.create_task(self.update_loop(sun, sun_x_start))

        await asyncio.gather(
            self.update_fps(),
            )

    async def update_loop(self, sun, sun_x_start):
        lane_width = self.grid.lane_width
        loop = asyncio.get_event_loop()

        start_time_ms = round(time.ticks_ms())
        print(f"Start time: {start_time_ms}")

        # 2D Y coordinate at which obstacles will crash with the player
        crash_y = 48

        # Create road obstacles
        self.enemies = []
        num_enemies = 4

        enemy = Spritesheet("/img/road_wall.bmp", 10, 20)
        enemy.set_camera(self.camera)
        enemy.set_alpha(1)
        enemy.x = -16
        enemy.y = 0
        enemy.z = self.sprite_max_z
        enemy.is3d = True
        enemy.speed = -self.ground_speed
        enemy.set_frame(0)
        enemy.lane_width = lane_width

        palette_size = 4
        palette_width = 16
        num_palettes = int(palette_width / palette_size)

        print(f"Creating {num_palettes}")
        self.enemy_palettes = Spritesheet('/img/enemy_gradients.bmp', frame_width=4, frame_height=1)
        print(f"Frames len: {len(self.enemy_palettes.frames)}")
        all_palettes = []

        # Split up the palette gradient into individual sub-palettes
        for i in range(num_palettes):
            start = i * palette_size
            new_palette = []
            print(f"Grabbing frame {i}")
            self.enemy_palettes.set_frame(i)
            pixels = self.enemy_palettes.pixels

            new_palette = colors.FramebufferPalette(bytearray(palette_size))

            for j in range(0, palette_size):
                new_palette.set_bytes(j, pixels.pixel(j,0))

            all_palettes.append(new_palette)

        # Create a number of road obstacles by cloning
        # for i in range(num_enemies):
        #     new_enemy = enemy.clone()
        #     new_enemy.z = 1000 + (i * 10)
        #     new_enemy.set_lane(1)
        #     new_enemy.palette.set_bytes(0, current_enemy_palette[i])
        #
        #     self.enemies.insert(0, new_enemy)  # prepend, so they will be drawn in the right order

        # for one_sprite in self.enemies:
        #     self.add(one_sprite)

        base_group = SpriteGroup(
            "/img/road_wall.bmp",
            num_elements=6,
            frame_width=10,
            frame_height=20,
            palette_gradient=all_palettes[0],
            lane_width=self.lane_width,
            pos_delta={"x": 0, "y": 0, "z": 20}
        )

        for i in range(1, 6):
            # Set a random palette
            palette_num = random.randrange(0, 4)
            current_enemy_palette = all_palettes[palette_num]
            group = self.create_group(base_group, current_enemy_palette, i)
            group.z = group.z + (i*1000)
            group.set_lane(palette_num)
            self.add(group)

        self.add(self.bike) # Add after the obstacles, to it appears on top
        bike_angle = 0
        turn_incr = 0.2  # turning speed
        half_width = int(self.camera.half_width)


        self.reset_game()

        _thread.start_new_thread(self.start_display_loop, [])

        # Draw loop - will run until program exit
        while True:

            #self.camera.yaw = self.camera.yaw + 1

            # print("Free memory: {} bytes".format(gc.mem_free()) )

            # Turn the bike automatically
            # bike_angle = math.sin(now / 1000) # (-1,1)

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
            self.bike.x = int((line_offset * 30) + half_width - 18)

            # REFACTOR
            # used so that 3D sprites will follow the movement of lanes as they change perspective
            # Not sure why the multipliers are needed, or how to get rid of them
            mult = 4.5

            self.camera.vp["x"] = int(bike_angle * mult)
            self.camera.pos["x"] = int(bike_angle * mult)
            sun.x = sun_x_start - int(bike_angle*5)

            for sprite in self.sprites:
                sprite.update()

            for sprite in self.enemies:

                # Check collisions
                if (    (sprite.draw_y >= crash_y) and
                        (sprite.draw_y < (self.display.height - 2) ) and
                        (sprite.get_lane() == self.bike.current_lane) and
                        not self.bike.blink):

                    self.do_crash()


            await asyncio.sleep(1 / 90)

        # Wait for next update

    def create_group(self, base_group, palette, lane=0):
        group = base_group.clone()
        group.set_camera(self.camera)
        group.palette = palette
        group.pos_delta = {"x": 0, "y": 0, "z": 20}
        group.speed = -self.ground_speed
        group.set_alpha(1)
        group.x = 0
        group.y = 0
        group.z = self.sprite_max_z
        group.is3d = True
        group.set_frame(0)
        group.lane_width = self.lane_width
        group.set_lane(lane)

        return group

    def do_refresh(self):
        """ Overrides parent method """
        self.display.fill(0)
        self.grid.show()
        self.draw_sprites()
        super().do_refresh()

    def do_crash(self):
        self.display_task.cancel()
        self.input_task.cancel()
        self.grid.global_speed = self.ground_speed = 0

        white = colors.rgb_to_565(colors.hex_to_rgb(0xFFFFFF))

        for i in range(3):
            self.display.fill(white)
            self.display.show()
            self.do_refresh()

        self.crash_fx.create_particles()
        self.crash_fx.anim_particles()

        self.bike.blink = True
        self.ui.remove_life()

        if self.ui.num_lives < 0:
            self.game_over()

        self.reset_game()


    def game_over(self):
        self.ui.big_text_bg.visible = True
        self.ui.game_over_text.visible = True
        self.bike.visible = False

    def reset_game(self):
        """After losing a life, we reset all the obstacle sprites and the speed"""

        for sprite in self.enemies:
            sprite.z = self.sprite_max_z

        self.grid.global_speed = self.ground_speed = self.max_ground_speed
        self.start_display_loop()

        loop = asyncio.get_event_loop()
        loop.create_task(self.bike.stop_blink())  # Will run after a few seconds

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

        self.display_task = loop.create_task(self.refresh_display())
        self.input_task = loop.create_task(self.get_input(self.encoder, self.encoder_last_pos))

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
    # scr = GameScreen()
    scr = TitleScreen()
    scr.run()
