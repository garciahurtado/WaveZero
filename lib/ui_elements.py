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
from framebuffer_palette import FramebufferPalette as fp, FramebufferPalette
import framebuf as fb
from framebuf import FrameBuffer as FrameBuffer
import color_util as colors
BLACK = 0x000000
CYAN = 0x00FFFF
YELLOW = 0xFF0067
WHITE = 0xFFFFFF

class ui_screen():
    display = None
    score = ''
    score_text = None
    game_over_text = None
    big_text_bg = None
    sprites = []
    life_sprite: Sprite
    lives_sprites = []
    num_lives: int = 0
    lives_text = None
    dirty = True

    def __init__(self, display, num_lives) -> None:
        self.dirty = True
        self.display = display
        self.num_lives = num_lives
        self.life_sprite = Sprite("/img/life.bmp", width=12, height=8)
        self.life_sprite.visible = False
        self.life_sprite.set_alpha(0)


        num_colors = 2
        # buffer = bytearray(num_colors // 2)
        # self.palette1 = FrameBuffer(buffer, 2, 1, framebuf.GS4_HMSB)
        # self.palette1.pixel(0, BLACK)
        # self.palette1.pixel(1, CYAN)
        #
        # buffer = bytearray(num_colors // 2)
        # self.palette2 = FrameBuffer(buffer, 2, 1, framebuf.GS4_HMSB)
        # self.palette2.pixel(0, BLACK)
        # self.palette2.pixel(1, ORANGE)
        #
        # buffer = bytearray(num_colors // 2)
        # self.palette3 = FrameBuffer(buffer, 2, 1, framebuf.GS4_HMSB)
        # self.palette3.pixel(0, BLACK)
        # self.palette2.pixel(1, WHITE)

        # Create palettes for different text elements
        self.score_palette = FramebufferPalette(16, color_mode=fb.GS4_HMSB)
        self.score_palette.set_bytes(0, 0)
        self.score_palette.set_bytes(1, 1)

        self.lives_palette = FramebufferPalette(16, color_mode=fb.GS4_HMSB)

        for i in range(16):
            if i == 0:
                self.lives_palette.set_bytes(i, 0)
            elif i == 1:
                self.lives_palette.set_bytes(i, 2)
            else:
                self.lives_palette.set_bytes(i, 2)

        self.life_sprite.palette = self.lives_palette

        self.palette_all = FramebufferPalette(4, color_mode=fb.RGB565)
        self.palette_all.set_bytes(0, colors.hex_to_565(BLACK, format=colors.RGB565))
        self.palette_all.set_bytes(1, colors.hex_to_565(YELLOW , format=colors.RGB565))
        self.palette_all.set_bytes(2, colors.hex_to_565(CYAN, format=colors.RGB565))
        self.palette_all.set_bytes(3, colors.hex_to_565(WHITE, format=colors.RGB565))

        self.init_lives()
        self.init_score()
        self.init_big_text_bg()
        self.init_game_over()

        num_bytes = (self.display.width * 8) // 2

        self.cached_img = framebuf.FrameBuffer(bytearray(num_bytes), self.display.width, 8, framebuf.GS4_HMSB)

    def init_lives(self):
        self.lives_text = ColorWriter(
            self.display,
            font_vtks,
            40, 15,
            self.lives_palette,
            color_format=fb.GS4_HMSB)

        self.lives_text.orig_x = 7
        self.lives_text.orig_y = 0

        self.refresh_lives()

    def init_score(self):
        self.score_text = ColorWriter(
            self.display,
            font_vtks,
            36, 6,
            self.score_palette,
            fixed_width=4,
            color_format=fb.GS4_HMSB
            )
        self.score_text.orig_x = 61
        self.score_text.orig_y = 0

        return self.score_text


    def remove_life(self):
        self.num_lives = self.num_lives - 1

        if self.num_lives < 0:
            self.num_lives = 0
            return False

        if self.num_lives < 4:
            self.init_lives()

        print(f"{self.num_lives} lives left")
        self.dirty = True

        return True

    def refresh_lives(self):
        if self.num_lives > 3:
            """ Show '<icon> x4' type lives"""
            self.lives_text.visible = True
            self.lives_text.render_text(f"x {self.num_lives}")
            self.render_life_icons(1)

        else:
            """ Show '<icon> <icon> <icon>' type lives"""
            self.lives_text.visible = False
            self.render_life_icons(self.num_lives)

        self.dirty = True

    def render_life_icons(self, num):
        self.lives_sprites = []

        for i in range(0, num):
            x, y = i * 12, -1
            new_sprite = self.life_sprite.clone()
            new_sprite.x = x
            new_sprite.y = y
            new_sprite.visible = True
            self.lives_sprites.append(new_sprite)

    def update_score(self, new_score):
        if new_score == self.score:
            return False

        self.score = new_score
        self.dirty = True

    def update_lives(self, new_lives):
        if new_lives == self.num_lives:
            return False

        self.num_lives = new_lives
        self.dirty = True
        self.refresh_lives()

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
            self.lives_palette
        )
        game_over_text.orig_x = 3
        game_over_text.orig_y = 28
        game_over_text.visible = False
        game_over_text.fgcolor = 2

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

        print("IN SHOW GAME OVER")
        # Animate text colors
        text_colors = [0x00FFFF,0x0094FF,0x00FF90,0x4800FF,0x4CFF00,0x21377F]
        text_color_palette = fp(len(text_colors))

        for i, color in enumerate(text_colors):
            text_color_palette.set_rgb(i, colors.hex_to_rgb(color))

        anim = PaletteRotate(text_color_palette, 300, [0, 6])

        loop = asyncio.get_event_loop()
        loop.create_task(anim.run())

        print("END OF SHOW GAME OVER")
        # utime.sleep_ms(10000)
        return True

    def show(self):
        if self.dirty:
            # must update the cached image
            self.refresh_canvas(self.cached_img)
            self.dirty = False

        self.display.blit(self.cached_img, 0, 0, -1, self.palette_all)
        self.dirty = False

    def refresh_canvas(self, canvas):
        for my_sprite in self.sprites:
            my_sprite.show(canvas)

        # ColorWriter.set_textpos(self.display, 0, 0)
        # print(f"SCORE: {self.score:09} / {self.score_text.orig_x},{self.score_text.orig_y}")

        self.refresh_lives()
        self.lives_text.show(canvas)

        for life in self.lives_sprites:
            life.show(canvas)

        self.score_text.render_text(f"{self.score:09}")
        self.score_text.show(canvas)




