import fonts.vtks_blocketo_6px as font_vtks
import fonts.bm_japan as large_font
import framebuf
import utime

# from font_writer import Writer, ColorWriter
from font_writer_new import ColorWriter, FontRenderer
from font_writer_new import MonochromeWriter as Writer

from sprites.sprite_rect import SpriteRect
from sprites.sprite import Sprite

from anim.palette_rotate import PaletteRotate
import uasyncio as asyncio
from framebuffer_palette import FramebufferPalette as fp

import color_util as colors

ORANGE = 0x00FFFF
CYAN = 0xFFFF00
BLACK = 0x000000
WHITE = 0xFFFFFF

class ui_screen():
    display = None
    lives_sprite: Sprite
    score = ''
    score_text = None
    game_over_text = None
    big_text_bg = None
    sprites = []
    lives_sprites = []
    num_lives: int = 0
    lives_text = None
    lives_text_str = "x0"
    dirty = True

    def __init__(self, display, num_lives) -> None:
        self.display = display
        self.num_lives = num_lives
        self.lives_sprite = Sprite("/img/life.bmp", width=12, height=8)
        self.lives_sprite.set_alpha(0)

        self.init_lives()
        self.init_score()
        self.init_big_text_bg()
        self.init_game_over()

        num_bytes = (self.display.width * 8) // 4

        self.cached_img = framebuf.FrameBuffer(bytearray(num_bytes), self.display.width, 8, framebuf.GS2_HMSB)
        self.palette = fp(4, color_mode=fp.BGR565)
        self.palette.set_bytes(0, BLACK)
        self.palette.set_bytes(1, ORANGE)
        self.palette.set_bytes(2, WHITE)
        self.palette.set_bytes(3, CYAN)

    def init_lives(self):
        if self.num_lives < 4:
            self.has_x_lives = False
        else:
            self.has_x_lives = True

        for i in range(0, self.num_lives):
            x, y = i * 12, 0
            new_sprite = self.lives_sprite.clone()
            new_sprite.x = x
            new_sprite.y = y
            self.sprites.append(new_sprite)
            self.lives_sprites.append(new_sprite)

        self.lives_text = ColorWriter(
            self.display,
            font_vtks, 9, 5,
            CYAN, BLACK)

        # def __init__(self, device, font, text_width, text_height, screen_width=None, screen_height=None, verbose=True):
        # self.lives_text = ColorWriter(
        #     self.display,
        #     font_vtks,
        #     9,5,
        #     self.display.width,
        #     self.display.height,
        #     CYAN,
        #     BLACK,
        #     )

        self.lives_text.orig_x = 14
        self.lives_text.orig_y = 1

        self.update_lives()

    def remove_life(self):
        self.num_lives = self.num_lives - 1

        if self.num_lives < 0:
            return False

        if self.num_lives < 4:
            self.init_lives()

        print(f"{self.num_lives} lives left")
        self.dirty = True

        return True

    def update_lives(self):
        if not self.dirty:
            return False

        if self.num_lives > 3:
            self.has_x_lives = True
            one_sprite = self.lives_sprite.clone()
            # one_sprite.x = x
            # one_sprite.y = y
            self.sprites = [one_sprite]
            self.lives_text.render_text(f"x {self.num_lives}")
            self.sprites.append(self.lives_text)

    def init_score(self):

        self.score_text = ColorWriter(
            self.display,
            font_vtks,
            35, 6,
            ORANGE, BLACK,
            )
        self.score_text.orig_x = 61
        self.score_text.orig_y = 0

        return self.score_text

    def init_big_text_bg(self):
        width, height = self.display.width, 21
        text_bg = SpriteRect(x=0, y=21, width=width, height=height)
        text_bg.visible = None

        self.big_text_bg = text_bg
        self.sprites.append(text_bg)

    def init_game_over(self):
        game_over_text = ColorWriter(
            self.display.write_framebuf,
            large_font, 96, 11,
            CYAN, BLACK
        )
        game_over_text.orig_x = 3
        game_over_text.orig_y = 28
        game_over_text.visible = False

        game_over_text.row_clip = True  # Clip or scroll when screen full
        game_over_text.col_clip = True  # Clip or new line when row is full
        game_over_text.wrap = False  # Word wrap

        # ColorWriter.set_textpos(self.display, 0, 0)
        game_over_text.render_text("GAME OVER")

        self.game_over_text = game_over_text
        self.sprites.append(game_over_text)

    def show_game_over(self):
        self.big_text_bg.visible = True
        self.game_over_text.visible = True

        # Animate text colors
        text_colors = [0x00FFFF,0x0094FF,0x00FF90,0x4800FF,0x4CFF00,0x21377F]
        text_color_palette = fp(len(text_colors))

        for i, color in enumerate(text_colors):
            text_color_palette.set_rgb(i, colors.hex_to_rgb(color))

        anim = PaletteRotate(text_color_palette, 300, [0, 6])

        loop = asyncio.get_event_loop()
        loop.create_task(anim.run())
        utime.sleep_ms(10000)

    def update_score(self, new_score):
        if new_score == self.score:
            return False

        self.score = new_score
        self.dirty = True

    def show(self):
        if self.dirty:
            # must update the cached image
            self.draw_sprites(self.cached_img)
            self.dirty = False

        self.display.blit(self.cached_img, 0, 0, -1, self.palette)
        self.dirty = False

    def draw_sprites(self, canvas):
        for my_sprite in self.sprites:
            my_sprite.show(canvas)

        # ColorWriter.set_textpos(self.display, 0, 0)
        print(f"SCORE: {self.score:09} / {self.score_text.orig_x},{self.score_text.orig_y}")
        self.score_text.render_text(f"{self.score:09}")
        self.score_text.show(canvas)



