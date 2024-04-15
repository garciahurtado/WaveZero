import asyncio
import time

from color_util import FramebufferPalette
import color_util as colors
from screen import Screen
from sprite import Sprite


class TitleScreen(Screen):
    def run(self):
        asyncio.run(self.main_loop())

    async def main_loop(self):
        await asyncio.gather(
            self.update_loop(),
            self.refresh()
        )

    async def update_loop(self):

        # "Wave"
        title_wave = Sprite("/img/title_wave.bmp")
        title_wave.x = 7
        title_wave.y = 4

        # "Zero"
        title_zero = Sprite("/img/title_zero.bmp")
        title_zero.set_alpha(0)
        title_zero.x = 100
        title_zero.y = 15

        self.screen.add(title_wave)
        self.screen.add(title_zero)

        title_wave.set_alpha(0)

        # num_colors = len(title1_palette) - 1
        # # Make transparent before we show the bitmap
        # for i in range(0, num_colors):
        #     title1_palette.make_transparent(i)
        #

        self.screen.draw_sprites()
        await asyncio.sleep(0.5)

        # # Do some color transitions manipulating the palette
        for i in range(title_wave.num_colors-1):
            title_wave.set_alpha(i+1)
            self.display.fill(0)
            self.refresh_display()
            await asyncio.sleep(0.2)

        title_wave.set_alpha(0)
        self.display.fill(0)
        self.refresh_display()

        title_wave.orig_palette = title_wave.palette

        self.refresh_display()

        # Make the bitmap white by assigning a new palette
        white_palette = [colors.hex_to_rgb(0xFFFFFF) for color in range(0,8)]
        white_palette = FramebufferPalette(white_palette)
        title_wave.palette = white_palette

        self.refresh_display()
        await asyncio.sleep(0.1)

        title_wave.palette = title_wave.orig_palette
        self.refresh_display()
        await asyncio.sleep(0.1)


        for x in range(100, 15, -2):
            title_zero.x = x
            self.display.fill(0)
            self.refresh_display()

            await asyncio.sleep(0.0001)

        # title1_grid.pixel_shader = white_palette
        # title_zero.pixel_shader = white_palette

        # just a flash

        await asyncio.sleep(0.15)

        #time.sleep(0.15)
        # title1_grid.pixel_shader = title1_palette
        # title_zero.pixel_shader = title2_palette
        # display.refresh()

        # new_palette = displayio.Palette(len(title1_palette))

        # Do some crazy palette tricks

        for i in range(1, title_wave.num_colors):
            # rotate palette list by one
            new_palette = [color for color in title_wave.palette.palette]
            new_palette = FramebufferPalette(new_palette)
            new_color = title_wave.palette.get_color(i)
            new_palette.set_color(title_wave.num_colors-1, new_color)

            for j in range(0, title_wave.num_colors - 1):
                new_palette.set_color(j, title_wave.palette.get_color(j+1))

            new_palette.set_color(0, colors.hex_to_rgb(0x000000))
            title_wave.palette = new_palette
            title_wave.set_alpha(0)
            self.refresh_display()

            await asyncio.sleep(0.05)

        title_wave.palette = title_wave.orig_palette
        self.refresh_display()

        await asyncio.sleep(2)
        self.display.fill(0)

        self.refresh_display()
