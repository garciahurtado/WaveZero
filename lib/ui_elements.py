import fonts.vtks_blocketo_6px as font_vtks
import fonts.bm_japan as large_font
import framebuf

from anim.palette_rotate_one import PaletteRotateOne
from font_writer_new import ColorWriter

from sprites_old.sprite_rect import SpriteRect
from sprites_old.sprite import Sprite

import uasyncio as asyncio
from colors.framebuffer_palette import FramebufferPalette as fp, FramebufferPalette
import framebuf as fb
from colors import color_util as colors
from colors.palettes import PALETTE_UI_FLASH_TEXT

BLACK = 0x000000
CYAN = 0x00FFFF
RED = 0xFF0000
YELLOW = 0xFFFF00
WHITE = 0xFFFFFF

# COLOR_SCORE = YELLOW
# COLOR_LIVES = CYAN

# tmp colors to avoid burn-in
COLOR_SCORE = CYAN
COLOR_LIVES = RED

class ui_screen():
    display = None
    score = ''
    score_text = None
    game_over_text = None
    center_text_bg = None
    sprites = []
    life_sprite: Sprite
    lives_sprites = []
    lives_text = None
    dirty = True
    max_life_sprites = 3

    def __init__(self, display, num_lives) -> None:
        self.dirty = True
        self.display = display
        self.num_lives = num_lives
        self.life_sprite = Sprite("/img/life.bmp", width=12, height=8)
        self.life_sprite.visible = False
        self.life_sprite.set_alpha(0)

        # Create palettes for different text elements
        self.score_palette = FramebufferPalette(16, color_mode=fb.GS4_HMSB)
        self.lives_palette = FramebufferPalette(16, color_mode=fb.GS4_HMSB)
        self.game_over_palette = FramebufferPalette(16, color_mode=fb.GS4_HMSB)

        for i in range(16):
            if i == 0:
                self.score_palette.set_bytes(i, 0)
                self.lives_palette.set_bytes(i, 0)
                self.game_over_palette.set_bytes(i, 0)
            elif i == 1:
                self.score_palette.set_bytes(i, 1)
                self.lives_palette.set_bytes(i, 2)
                self.game_over_palette.set_bytes(i, 3)
            else:
                self.score_palette.set_bytes(i, 1)
                self.lives_palette.set_bytes(i, 2)
                self.game_over_palette.set_bytes(i, 3)

        self.life_sprite.palette = self.lives_palette
        format = colors.BGR565

        self.palette_all = FramebufferPalette(4)

        inv = True if format == colors.RGB565 else False
        self.palette_all.set_rgb(0, colors.hex_to_rgb(BLACK, inv=inv))
        self.palette_all.set_rgb(1, colors.hex_to_rgb(COLOR_SCORE, inv=inv))
        self.palette_all.set_rgb(2, colors.hex_to_rgb(COLOR_LIVES, inv=inv))
        self.palette_all.set_rgb(3, colors.hex_to_rgb(WHITE, inv=inv))

        self.init_lives(num_lives)
        self.init_score()
        self.init_center_text_bg()
        self.init_game_over()

        num_bytes = (self.display.width * 8) // 2

        self.cached_img = framebuf.FrameBuffer(bytearray(num_bytes), self.display.width, 8, framebuf.GS4_HMSB)

    def init_lives(self, num_lives):
        self.lives_text = ColorWriter(
            font_vtks,
            40, 15,
            self.lives_palette,
            color_format=fb.GS4_HMSB)

        self.lives_text.orig_x = 7
        self.lives_text.orig_y = 1
        self.num_lives = num_lives

        self.lives_sprites.append(self.life_sprite)
        for i in range(1, self.max_life_sprites):
            new_sprite = self.life_sprite.clone()
            new_sprite.visible = False
            new_sprite.x = i * 12
            new_sprite.y = 0
            self.lives_sprites.append(new_sprite)

        self.render_lives()

    def init_score(self):
        self.score_text = ColorWriter(
            font_vtks,
            36, 6,
            self.score_palette,
            fixed_width=4,
            color_format=fb.GS4_HMSB
        )
        self.score_text.orig_x = 60
        self.score_text.orig_y = 0
        self.score_text.visible = True

        return self.score_text

    def init_game_over(self):
        game_over_text = ColorWriter(
            large_font,
            96, 10,
            self.game_over_palette,
            None,
            color_format=fb.GS4_HMSB
        )
        game_over_text.orig_x = 1
        game_over_text.orig_y = 28
        game_over_text.visible = False

        game_over_text.row_clip = True  # Clip or scroll when screen full
        game_over_text.col_clip = True  # Clip or new line when row is full

        game_over_text.render_text("GAME OVER")
        self.game_over_text = game_over_text

    def init_center_text_bg(self):
        width, height = self.display.width, 18
        text_bg = SpriteRect(width, height, None, x=0, y=23)
        text_bg.visible = False

        self.center_text_bg = text_bg
        self.sprites.append(text_bg)

    def render_lives(self):
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
        for i in range(0, len(self.lives_sprites)):
            one_sprite = self.lives_sprites[i]
            if i >= num:
                one_sprite.visible = False
            else:
                one_sprite.visible = True

    def update_score(self, new_score):
        if new_score == self.score:
            return False

        self.score = new_score
        self.dirty = True

    def update_lives(self, new_lives=0):
        # if new_lives == self.num_lives:
        #     return False

        self.num_lives = new_lives
        self.render_lives()

    def show_game_over(self):
        self.center_text_bg.visible = True
        self.game_over_text.visible = True
        self.sprites.append(self.game_over_text)

        # Animate text colors
        color_list_palette = fp(len(PALETTE_UI_FLASH_TEXT))

        for i, color in enumerate(PALETTE_UI_FLASH_TEXT):
            color_list_palette.set_rgb(i, colors.hex_to_rgb(color))

        self.game_over_anim = PaletteRotateOne(self.palette_all, color_list_palette, 10, 3)
        loop = asyncio.get_event_loop()
        loop.create_task(self.game_over_anim.run())

        return True

    def reset_game_over(self):
        self.game_over_anim.stop()
        self.game_over_text.visible = False
        self.center_text_bg.visible = False
        self.sprites.remove(self.game_over_text)
        self.sprites.remove(self.center_text_bg)

    def show(self):
        if self.dirty:
            # must update the cached image
            self.refresh_canvas(self.cached_img)
            self.dirty = False

        self.display.blit(self.cached_img, 0, 0, -1, self.palette_all)

        for my_sprite in self.sprites:
            my_sprite.show(self.display, self.palette_all)

    def refresh_canvas(self, canvas):
        canvas.fill(0x00)
        self.lives_text.show(canvas)
        self.render_lives()

        for life in self.lives_sprites:
            life.show(canvas)

        self.score_text.render_text(f"{self.score:09}")
        self.score_text.show(canvas)
