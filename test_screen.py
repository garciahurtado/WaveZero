import _thread
import asyncio
import gc

import utime

from font_writer import ColorWriter, Writer
from fps_counter import FpsCounter
from perspective_camera import PerspectiveCamera
from scaled_sprite import ScaledSprite
from screen import Screen
from sprite_3d import Sprite3D
import color_util as colors
import fonts.vtks_blocketo_6px as font_vtks

class TestScreen(Screen):
    sprite_max_z = 1000
    display_task = None
    sprites = []
    CYAN = (0, 255, 255)
    GREEN = (0, 255, 0)
    BLACK = (0, 0, 0)
    fps_text: ColorWriter

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        gc.collect()
        print(f"Free memory __init__: {gc.mem_free():,} bytes")
        self.init_camera()
        self.init_fps()

    def run(self):
        asyncio.run(self.main_loop())

    async def main_loop(self):
        _thread.start_new_thread(self.start_display_loop, [])
        await asyncio.gather(
            self.update_fps(),
            self.sprite_fps_test()
        )

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
            fps = int(self.fps.fps())
            Writer.set_textpos(self.display, 0, 0)
            self.fps_text.printstring(f"{fps:.>4}")

            await asyncio.sleep(0.2)

    async def sprite_fps_test(self):
        # Create 64 sprites
        num_sprites = 4
        print(f"Creating {num_sprites**3} sprites")

        base_enemy1 = ScaledSprite(
            camera=self.camera,
            filename='/img/laser_tri.bmp')
        base_enemy1.set_alpha(0)
        base_enemy1.is3d = True

        base_enemy2 = ScaledSprite(
            camera=self.camera,
            filename='/img/road_wall_single.bmp')
        base_enemy2.set_alpha(0)
        base_enemy2.is3d = True

        for z in range(1, 0, -1):
            for row in range(num_sprites, 0, -1):
                for i in range(num_sprites, 0, -1):
                    # self.check_mem()

                    enemy1 = base_enemy1.clone()
                    enemy1.x = i * 12 - 50
                    enemy1.y = row * 20 - 30
                    enemy1.z = z * 15 - 20
                    enemy1.set_camera(self.camera)
                    self.sprites.append(enemy1)

                    enemy2 = base_enemy2.clone()
                    enemy2.x = i * 12 - 10
                    enemy2.y = row * 20 - 30
                    enemy2.z = z * 15 - 20
                    enemy2.set_camera(self.camera)
                    self.sprites.append(enemy2)

        while True:
            for i, sprite in enumerate(self.sprites):
                sprite.z = sprite.z + 2
                sprite.update()

            await asyncio.sleep(1 / 60)

    def start_display_loop(self):
        loop = asyncio.get_event_loop()
        self.display_task = loop.create_task(self.refresh_display())

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

        color = colors.rgb_to_565((4, 4, 4))
        try:
            while True:
                self.display.fill(color)
                for i, sprite in enumerate(self.sprites):
                    sprite.show(self.display)

                self.fps_text.show(self.display)

                self.do_refresh()
                await asyncio.sleep(1/60)
        except asyncio.CancelledError:
            return True
