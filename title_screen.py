import asyncio
import gc
from utime import sleep_ms

from animation import Animation
from color_util import FramebufferPalette
import color_util as colors
from screen import Screen
from sprite import Sprite
from collections import deque

from ui_elements import ui_screen


class TitleScreen(Screen):
    running = False

    def __init__(self, display, *args, **kwargs):
        super().__init__(display, *args, **kwargs)
        gc.collect()
        print(f"Free memory __init__: {gc.mem_free():,} bytes")

    def run(self):
        self.running = True
        asyncio.run(self.main_async())

    async def main_async(self):
        loop = asyncio.get_event_loop()
        self.task_refresh = loop.create_task(self.refresh())

        await asyncio.gather(
            self.main_loop(),
        )
        # loop.run_until_complete(self.update_fps())


    async def refresh(self):
        while self.running:
            self.display.fill(0)
            self.draw_sprites()
            self.do_refresh()
            await asyncio.sleep(1 / 30)

    async def main_loop(self):
        loop = asyncio.get_event_loop()
        ms = 1000

        # "Wave"
        title_wave = Sprite("/img/title_wave.bmp")
        title_wave.x = 7
        title_wave.y = -40
        title_wave.orig_palette = title_wave.palette
        title_wave.set_alpha(0)

        # "Zero"
        title_zero = Sprite("/img/title_zero.bmp")
        title_zero.set_alpha(0)
        title_zero.x = 100
        title_zero.y = 15
        title_zero.orig_palette = title_zero.palette

        self.add(title_wave)
        self.add(title_zero)

        title_wave_anim = Animation(title_wave, 'y', 0, 600)
        await title_wave_anim.run()


        await asyncio.sleep(300/ms)
        title_wave.palette = FramebufferPalette(title_wave.palette.palette)

        for j in range(0, 2):
            for i in range(1, 6):
                title_wave.set_alpha(i+1)
                await asyncio.sleep(0.05)

        title_wave.set_alpha(0)

        # # Do some color transitions manipulating the palette
        for i in range(2, 5):
            title_wave.palette.set_rgb(i, colors.hex_to_rgb(0xFFFFFF))
            title_wave.set_alpha(0)
            await asyncio.sleep(50/ms)

        title_wave.palette = title_wave.orig_palette
        title_wave.set_alpha(0)

        # Make the bitmap white by assigning a new palette
        white_palette = [colors.hex_to_rgb(0xFFFFFF) for _ in range(1,8)]
        white_palette = FramebufferPalette(white_palette)
        white_palette.set_rgb(0, colors.hex_to_rgb(0x000000))
        title_wave.palette = white_palette

        await asyncio.sleep(100/ms)

        title_wave.palette = title_wave.orig_palette
        await asyncio.sleep(100/ms)


        zero_anim = Animation(title_zero, "x", 15, 300)
        await zero_anim.run()

        # just a quick white flash
        self.display.fill(colors.rgb_to_565(colors.hex_to_rgb(0xFFFFFF)))
        await asyncio.sleep(0.5)

        # title1_grid.pixel_shader = title1_palette
        # title_zero.pixel_shader = title2_palette
        # display.refresh()

        # new_palette = displayio.Palette(len(title1_palette))

        # Do some crazy palette tricks

        new_palette = [color for color in title_wave.palette.palette]
        new_palette = deque(new_palette, len(new_palette))

        for i in range(1, title_wave.num_colors):
            # rotate palette list by one

            new_palette.appendleft(new_palette.pop())
            new_palette_buffer = FramebufferPalette(list(new_palette))
            new_palette_buffer.set_rgb(0, colors.hex_to_rgb(0x000000))
            title_wave.palette = new_palette_buffer

            #self.refresh()

            await asyncio.sleep(100/ms)

        title_wave.palette = title_wave.orig_palette
        #self.refresh()

        new_palette = [color for color in title_zero.palette.palette]
        new_palette = deque(new_palette, len(new_palette))

        # Do the same with "Zero"
        for i in range(1, title_zero.num_colors):
            # rotate palette list by one

            new_palette.appendleft(new_palette.pop())
            new_palette_buffer = FramebufferPalette(list(new_palette))
            new_palette_buffer.set_rgb(0, colors.hex_to_rgb(0x000000))
            title_zero.palette = new_palette_buffer

            await asyncio.sleep(150/ms)

        title_zero.palette = title_zero.orig_palette
        await asyncio.sleep(200/ms)

        self.running = False

        print("-- End of intro screen --")
