import math

import fonts.vtks_blocketo_6px as font_vtks
import utime

from screen import Screen

import asyncio
import _thread
import gc
from micropython import const

from font_writer import ColorWriter, Writer
from perspective_camera import PerspectiveCamera
from sprites.scaled_sprite import ScaledSprite
import color_util as colors
import random

class TestScreen(Screen):
    sprite_max_z = const(5000)
    display_task = None
    CYAN = (0, 255, 255)
    GREEN = (0, 255, 0)
    BLACK = (0, 0, 0)
    fps_text: ColorWriter
    sprites = []
    lines = []
    # line_color = colors.hex_to_rgb(0xFFFFFF)
    line_colors = [ colors.hex_to_565(0xFF0000),
                    colors.hex_to_565(0x00FF00),
                    colors.hex_to_565(0x0000FF)]

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        print(f"Free memory __init__: {gc.mem_free():,} bytes")

        # self.display.set_clock_divide(16)
        self.init_camera()
        self.init_fps()

    def run(self):
        #self.check_mem()
        self.display.start()
        asyncio.run(self.main_loop())

    async def main_loop(self):
        self.create_lines()

        _thread.start_new_thread(self.start_display_loop, [])

        await asyncio.gather(
            self.sprite_fps_test(),
            # self.display_line_test(),
            self.update_fps()
        )

    def create_lines(self):
        count = 40
        print(f"Creating {count} lines")
        for i in range(count):
            y_start = 16 + int(i)
            y_start -= y_start % 2
            idx = math.floor(random.randrange(0,3))
            color = self.line_colors[idx]
            self.lines.append([int(0), int(y_start), int(95), int(y_start), color])

    def init_fps(self):
        self.fps_text = ColorWriter(
            self.display,
            font_vtks, 35, 6, fgcolor=self.GREEN, bgcolor=self.BLACK)
        self.fps_text.text_x = 78
        self.fps_text.text_y = 0

        return self.fps_text

    async def update_fps(self):
        while True:
            # Show the FPS in the score label
            fps = self.fps.fps()
            if fps is False:
                pass
            else:
                fps = int(fps)
                Writer.set_textpos(self.display, 0, 0)
                self.fps_text.row_clip = True
                self.fps_text.printstring("{: >6}".format(fps))

            await asyncio.sleep(0.1)

    async def sprite_fps_test(self):
        self.create_sprites()
        self.last_tick = utime.ticks_ms()

        while True:
            elapsed = utime.ticks_ms() - self.last_tick
            for i, sprite in enumerate(self.sprites):
                sprite.z = sprite.z + 1
                sprite.update(elapsed)
            await asyncio.sleep(1 / 90)

    async def display_line_test(self):
        while True:
            await asyncio.sleep(1 / 60)

    def create_sprites(self):
        # Create n * n * n sprites
        num_sprites = 4
        print(f"Creating {num_sprites ** 3} sprites")

        base_enemy1 = ScaledSprite(
            camera=self.camera,
            filename='/img/laser_tri.bmp',
            frame_width=20,
            frame_height=20)
        base_enemy1.set_alpha(0)
        base_enemy1.is3d = True

        base_enemy2 = ScaledSprite(
            camera=self.camera,
            filename='/img/road_wall_single.bmp',
            frame_width=12,
            frame_height=22)
        base_enemy2.set_alpha(0)
        base_enemy2.is3d = True
        far_z = 3

        for z in range(num_sprites, 0, -1):
            for row in range(num_sprites, 0, -1):
                for i in range(num_sprites, 0, -1):
                    # self.check_mem()

                    enemy1 = base_enemy1.clone()
                    enemy1.set_camera(self.camera)

                    enemy1.x = i * 15 - 90
                    enemy1.y = row * 25 - 60
                    enemy1.z = z * 15 - far_z
                    self.sprites.append(enemy1)

                    enemy2 = base_enemy2.clone()
                    enemy2.set_camera(self.camera)

                    enemy2.x = i * 15 - 0
                    enemy2.y = row * 25 - 60
                    enemy2.z = z * 15 - far_z
                    self.sprites.append(enemy2)


    def init_camera(self):
        # Camera
        horiz_y = 16
        camera_z = 48
        self.camera = PerspectiveCamera(
            self.display,
            pos_x=0,
            pos_y=48,
            pos_z=-camera_z,
            focal_length=camera_z,
            vp_x=0,
            vp_y=horiz_y)
        self.camera.horiz_z = self.sprite_max_z

    async def refresh_display(self):

        bg_color = colors.rgb_to_565((4, 4, 4))
        while True:
            #start = utime.ticks_ms()

            self.display.fill(bg_color)

            # self.refresh_lines()
            for i, sprite in enumerate(self.sprites):
                sprite.show(self.display)

            self.fps_text.show(self.display)
            self.do_refresh()

            #diff = utime.ticks_ms() - start
            #print(f"sprite.show(): {diff}ms")
            await asyncio.sleep(1/20)

    def show_lines(self):
        for line in self.lines:
            # print(f"Line in {line[0]},{line[1]}, / {line[2]},{line[3]}")
            x1 = line[0]
            y1 = line[1]
            x2 = line[2]
            y2 = line[3]
            color = line[4]

            y2 = y2 + int(random.randrange(0, 2))
            self.display.rect(
                x1,
                y1,
                x2,
                y2,
                color)


    def start_display_loop(self):
        loop = asyncio.get_event_loop()
        loop.create_task(self.refresh_display())

        return True
