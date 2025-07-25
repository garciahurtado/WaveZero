import _thread
import asyncio
import utime
import fonts.vtks_blocketo_6px as font_vtks

from colors import color_util as colors
from colors.framebuffer_palette import FramebufferPalette
from font_writer_new import ColorWriter
from screens.screen import Screen
import framebuf

from sprites.sprite_registry import registry
from ssd1331_pio import SSD1331PIO

class TestScreenBase(Screen):
    screen_width = SSD1331PIO.WIDTH
    screen_height = SSD1331PIO.HEIGHT

    fps_text: ColorWriter
    score_palette = FramebufferPalette(16, color_mode=framebuf.GS4_HMSB)
    grid_lines_color = colors.hex_to_565(0x0b2902)
    grid_lines = False
    grid_center = False
    grid_color = colors.hex_to_565(0x00FF00)
    mgr = None

    def init_score(self):
        self.score_text = ColorWriter(
            font_vtks,
            36, 6,
            self.score_palette,
            fixed_width=4,
            color_format=framebuf.GS4_HMSB
        )
        self.score_text.orig_x = 68
        self.score_text.orig_y = 0
        self.score_text.visible = True

        return self.score_text

    async def update_score(self):
        while True:
            new_score = 100
            if new_score == self.score:
                return False

            self.score = new_score

            await asyncio.sleep(1)

    def init_thread_2(self):
        print(f" == CPU CORE THREAD# {_thread.get_ident()} STARTED ==")

        utime.sleep_ms(500)
        loop = asyncio.get_event_loop()
        loop.create_task(self.start_render_loop())

    async def endless_wait(self):
        """ Here only so that the screen doesn't suddenly end """
        while True:
            await asyncio.sleep_ms(1)
            pass

    def common_bg(self):
        self.display.fill(0x000000)

        if self.grid_lines:
            # Vertical lines
            width = self.screen_width
            height = self.screen_height

            for x in range(0, width, 8):
                self.display.line(x, 0, x, height, self.grid_lines_color)
            self.display.line(width-1, 0, width-1, height, self.grid_lines_color)

            # Horiz lines
            for y in range(0, height, 8):
                self.display.line(0, y, width, y, self.grid_lines_color)
            self.display.line(0, height-1, width, height-1, self.grid_lines_color)

        if self.grid_center:
            """ Center grid origin """
            width = self.screen_width
            height = self.screen_height

            self.display.hline(0, height//2, width, self.grid_color)
            self.display.line(width//2, 0, width//2, height, self.grid_color)

    def load_sprite(self, sprite_type, sprite_class):
        """ Creates images if not exist, returns meta"""
        registry.add_type(
            sprite_type,
            sprite_class)

        self.sprite_type = sprite_type
        self.sprite_meta = self.sprite = registry.sprite_metadata[sprite_type]
        self.image = registry.sprite_images[sprite_type]
        return self.sprite_meta

    def init_fps(self):
        """ FPS text is the same as 'score text', a place on the screen to display debug info """
        self.fps_text = ColorWriter(
            font_vtks,
            36, 6,
            self.score_palette,
            fixed_width=4,
            color_format=framebuf.GS4_HMSB
        )
        self.fps_text.orig_x = 60
        self.fps_text.orig_y = 0
        self.fps_text.visible = True

        return self.fps_text


