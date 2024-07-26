import asyncio
import gc

from machine import Pin

from anim.anim_attr import AnimAttr
from color_util import FramebufferPalette
import color_util as colors
from screen import Screen
from sprites.sprite import Sprite
from collections import deque

# from wav.wavePlayer import wavePlayer


class TitleScreen(Screen):
    running = False
    sound_player = None

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

        """ Sound Thread """

        await asyncio.gather(
            self.start_main_loop(),
        )
        # loop.run_until_complete(self.update_fps())

    def play_music(self):
        self.sound_player = wavePlayer(
            leftPin=Pin(18),
            rightPin=Pin(19),
            virtualGndPin=Pin(20))

        sound_file = '/sound/thunder_force_iv_01_8k.wav'
        print(f"Playing {sound_file}")
        self.sound_player.play(sound_file)
        print(f"End of play music loop")

    async def refresh(self):
        while self.running:
            self.display.fill(0)
            self.draw_sprites()
            self.do_refresh()
            await asyncio.sleep(1 / 60)

    async def start_main_loop(self):
        ms = 1000
        WHITE = colors.hex_to_rgb(0xFFFFFF)
        BLACK = colors.hex_to_rgb(0x000000)

        """ Load Sprites ------------------------ """

        # "Wave"
        title_wave = Sprite("/img/title_wave.bmp")
        title_wave.x = 7
        title_wave.y = -40
        title_wave.set_alpha(0)
        wave_old_palette = title_wave.palette.clone()
        wave_new_palette = title_wave.palette.clone()

        # "Zero"
        title_zero = Sprite("/img/title_zero.bmp")
        title_zero.set_alpha(0)
        title_zero.x = 100
        title_zero.y = 15
        zero_orig_palette = title_zero.palette.clone()
        zero_new_palette = title_zero.palette.clone()

        self.add(title_wave)
        self.add(title_zero)

        """ Start animation ---------------------- """

        title_wave_anim = AnimAttr(title_wave, 'y', 0, 600)
        await title_wave_anim.run()

        await asyncio.sleep(300/ms)
        title_wave.palette = wave_new_palette

        # # Do some color transitions manipulating the palette
        for i in range(2, 5):
            title_wave.palette.set_rgb(i, WHITE)
            title_wave.set_alpha(0)
            await asyncio.sleep(100/ms)

        title_wave.palette = wave_old_palette
        title_wave.set_alpha(0)
        await asyncio.sleep(100 / ms)

        # Make the bitmap white by assigning a new palette
        white_palette = [WHITE for _ in range(1, title_wave.num_colors+1)]
        white_palette = FramebufferPalette(white_palette)
        white_palette.set_rgb(0, WHITE)
        title_wave.palette = white_palette
        title_wave.set_alpha(0)

        await asyncio.sleep(100/ms)

        title_wave.palette = wave_old_palette
        title_wave.set_alpha(0)
        await asyncio.sleep(100/ms)

        zero_anim = AnimAttr(title_zero, "x", 15, 300)
        await zero_anim.run()

        # just a quick flash
        for i in range(0, 3):
            self.display.fill(colors.rgb_to_565(WHITE))
            self.do_refresh()
            await asyncio.sleep(10 / ms)
            self.display.fill(colors.rgb_to_565(BLACK))
            self.do_refresh()
            await asyncio.sleep(10 / ms)

        # Do some crazy palette tricks
        title_wave.palette = wave_new_palette

        for i in range(1, title_wave.num_colors):

            # rotate palette list by one
            for color_idx in range(1, title_wave.num_colors + 1):
                new_color = color_idx+i
                if new_color >= title_wave.num_colors - 1:
                    new_color = new_color % title_wave.num_colors

                new_color = title_wave.palette.get_bytes(new_color)
                wave_new_palette.pixel(color_idx, int(new_color))

            title_wave.set_alpha(0)
            self.do_refresh()
            await asyncio.sleep(10/ms)

        title_wave.palette = wave_old_palette
        title_wave.set_alpha(0)

        zero_new_palette = deque(zero_new_palette.palette, len(zero_new_palette))

        # Do the same with "Zero"
        for i in range(1, title_zero.num_colors):
            # rotate palette list by one

            zero_new_palette.appendleft(zero_new_palette.pop())
            new_palette_buffer = FramebufferPalette(bytearray(zero_new_palette))
            new_palette_buffer.set_rgb(0, colors.hex_to_rgb(0x000000))
            title_zero.palette = new_palette_buffer

            await asyncio.sleep(100/ms)

        title_zero.palette = zero_orig_palette
        await asyncio.sleep(200/ms)

        self.running = False

        print("-- End of intro screen --")
