import gc
import utime as time
import math

import uasyncio as asyncio

import color_util
from screen import Screen
from road_grid import RoadGrid
from perspective_sprite import PerspectiveSprite
from perspective_camera import PerspectiveCamera
from encoder import Encoder
from sprite import Sprite, Spritesheet
from title_screen import TitleScreen
import color_util as colors

start_time_ms = 0
line_cache = {}
line_cache = {}
road_sprites = []

# Bike movement
current_lane = 2
target_lane = 2


class GameScreen(Screen):
    display: None
    grid: None
    camera: None

    def __init__(self, display=None):
        super().__init__(display)
        print(f"Free memory __init__: {gc.mem_free():,} bytes")

        self.preload_images()

    def preload_images(self):
        pass

    def run(self):
        asyncio.run(self.main_async())

    async def main_async(self):
        self.preload_images()

        bike = Spritesheet("/img/bike_sprite.bmp", 37, 22)
        bike.set_alpha(0)
        bike.set_frame(8)  # middle frame
        bike.x = 25
        bike.y = 42
        self.ui.add(bike)

        # bike_img = None

        # bike_palette.make_transparent(172) # index of #333333
        # bike = TileGrid(bike_bitmap, pixel_shader=bike_palette, x=32, y=42, tile_width=37, tile_height=22)
        # bike[0] = bike_anim

        sun_img = Sprite("/img/sunset.bmp")
        sun_img.x = 39
        sun_img.y = 5
        sun_x_start = 39

        # show_title(display, root)
        gc.collect()
        print(f"Free memory before main loop:  {gc.mem_free():,} bytes")

        encoder = Encoder(27, 26)
        last_pos = {'pos': 0}

        sprite_max_z = 3000

        # Camera
        horiz_y = 16
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=64,
            pos_z=-64,
            vp_x=0,
            vp_y=horiz_y)
        self.camera.horiz_z = sprite_max_z

        self.grid = RoadGrid(self.camera, self.ui.display)


        await asyncio.gather(
            self.update_loop(bike, sun_img, sun_x_start, sprite_max_z),
            self.refresh(),
            self.get_input(encoder, last_pos))


    async def get_input(self, encoder, last_pos):
        while True:
            position = encoder.value
            if position > last_pos['pos']:
                self.move_left()
                last_pos['pos'] = position
            elif position < last_pos['pos']:
                self.move_right()
                last_pos['pos'] = position

            await asyncio.sleep(0.0001)


    def move_left(self):
        global current_lane, target_lane

        if current_lane == 0:
            return

        if current_lane == target_lane:
            target_lane = current_lane - 1
        else:
            if target_lane > 0:
                target_lane -= 1


    def move_right(self):
        global current_lane, target_lane

        if current_lane == 4:
            return

        if current_lane == target_lane:
            target_lane = current_lane + 1
        else:
            if target_lane < 4:
                target_lane += 1


    async def update_loop(self, bike, sun_image, sun_x_start, sprite_max_z, speed=1, fps=None):
        global target_lane, current_lane
        BLACK = self.display.rgb(0, 0, 0)
        speed = 1
        self.ui.add(sun_image)

        start_time_ms = round(time.ticks_ms())
        print(f"Start time: {start_time_ms}")

        # 2D Y coordinate at which obstacles will crash with the player
        crash_y = 50

        # Create road obstacles
        road_sprites = []
        num_obstacles = 10

        obstacle = Spritesheet("/img/road_wall.bmp", 10, 20)
        obstacle.camera = self.camera
        obstacle.set_alpha(1)
        obstacle.x = 0
        obstacle.y = 0
        obstacle.z = sprite_max_z
        obstacle.set_frame(0)

        all_colors = [0x00f6ff, 0x00dff9, 0x00c8f1, 0x00b1e8, 0x009add, 0x0083cf, 0x006cbf, 0x0055ac, 0x003e96,
                      0x00267d]
        #all_colors = color_util.make_palette(all_colors)

        # Create a number of road obstacles by cloning
        for i in range(num_obstacles):
            new_obs = obstacle.clone()
            new_obs.z = 500 + (i * 30)
            new_obs.palette.set_color(0, colors.hex_to_rgb(all_colors[i]))

            # print(f"New obs palette: {new_obs.palette}")

            #new_obs.palette.pixel(0, 0, all_colors[i])

            #new_obs.set_palette()

            # print(f"New mod. palette: {new_obs.palette}")

            # clone the base palette
            #          palette_colors = [color for color in palette]
            #          new_palette = []
            #          for ii, color in enumerate(palette_colors):
            #              new_palette[ii] = color

            # Unique color to this sprite
            # new_palette[1] = all_colors[i - 1]

            road_sprites.insert(0, new_obs) # prepend, so they will be drawn in the right order


        for one_sprite in road_sprites:
            self.ui.add(one_sprite)

        bike_angle = 0
        turn_incr = 0.3  # turning speed

        # Draw loop - will run until program exit
        while True:
            # gc.collect()
            # print("Free memory: {} bytes".format(gc.mem_free()) )

            now = time.ticks_ms()

            # Turn the bike automatically
            # bike_angle = math.sin(now / 1000) # (-1,1)

            # Handle bike swerving
            target_angle = (target_lane * (2 / 4)) - 1

            if target_lane < current_lane:
                bike_angle = bike_angle - turn_incr
                if bike_angle < target_angle:
                    current_lane = target_lane
                    bike_angle = target_angle
            elif target_lane > current_lane:
                bike_angle = bike_angle + turn_incr
                if bike_angle > target_angle:
                    current_lane = target_lane
                    bike_angle = target_angle

            bike_angle = sorted((-1, bike_angle, 1))[1]  # Clamp the input

            line_offset = self.turn_bike(bike, bike_angle)  # range(-1,1)
            bike.x = math.floor((line_offset * 30)) + round(self.display.width / 2) - 18

            # REFACTOR
            self.camera.vp["x"] = int(bike_angle * 10)  # So that 3D sprites will follow the movement of the road
            self.camera.pos["x"] = int(bike_angle * 5)
            sun_image.x = sun_x_start - int(self.camera.pos["x"] * 1)

            # Move the road sprites
            for sprite in road_sprites:
                sprite.z = sprite.z - 10 * speed
                x, y = sprite.pos()

                if y < 0 or sprite.z <= sprite.camera.pos['z']:
                    sprite.z = sprite_max_z


                sprite.update_frame()

                # Check collisions
                # print(f"x: {sprite.x} y: {sprite.y} z: {sprite.z}")

                # if (sprite.sprite_grid.y > crash_y) and (sprite.get_lane(x_offset_3d) == current_lane):
                #     particles, grid = death.create_particles(bike.bitmap, root)
                #     death.anim_particles(particles, display, grid)

            # Show the FPS in the score label
            self.ui.update_score(int(self.fps.fps()))
            await asyncio.sleep(1 / 90)

        # Wait for next update


    def create_road_sprite(self, x, y, z, bitmap=None, palette=None, camera=None, i=0):
        global road_sprites

        palette.make_transparent(2)
        grid = TileGrid(bitmap, pixel_shader=palette, x=0, y=0, tile_width=10, tile_height=20)
        grid[0] = 8

        # Will be used by displayio to render the bitmap
        sprite = PerspectiveSprite(grid, x=x, y=y, z=z, camera=camera)
        road_sprites.append(sprite)  # Will be used to update sprite coordinates

        return grid


    def turn_bike(self, bike: Spritesheet, angle):
        new_frame = round(((angle * 16) + 17) / 2)
        if bike.current_frame != new_frame:
            bike.set_frame(new_frame)

        line_offset = angle
        return line_offset


    def make_palette_from_img(self):
        bitmap, palette = adafruit_imageload.load(
            "/img/horizon_gradient.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette)
        print(palette.__version__)
        palette._colors.sort()

        return palette

if __name__ == "__main__":
    #scr = GameScreen()
    scr = TitleScreen()
    scr.run()
