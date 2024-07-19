import fonts.vtks_blocketo_6px as font_vtks
import fonts.bm_japan as large_font
import utime

from font_writer import Writer, ColorWriter

from sprites.sprite_rect import SpriteRect
from sprites.sprite import Sprite

from anim.palette_rotate import PaletteRotate
import asyncio
from color_util import FramebufferPalette
import color_util as colors

class ui_screen():
    display: None
    lives_sprite: Sprite
    score: int = 0
    score_text = None
    game_over_text = None
    big_text_bg = None
    sprites = []
    lives_sprites = []
    num_lives: int = 0
    CYAN = (0, 255, 255)
    BLACK = (0, 0, 0)

    def __init__(self, display, num_lives) -> None:
        self.display = display
        self.num_lives = num_lives
        self.lives_sprite = Sprite("/img/life.bmp")
        self.lives_sprite.set_alpha(0)

        self.init_lives()
        self.init_score()
        self.init_big_text_bg()
        self.init_game_over()

    def init_lives(self):
        for i in range(0, self.num_lives):
            x, y = i * 12, 0
            new_sprite = self.lives_sprite.clone()
            new_sprite.x = x
            new_sprite.y = y
            self.sprites.append(new_sprite)
            self.lives_sprites.append(new_sprite)

    def remove_life(self):
        self.num_lives = self.num_lives - 1
        if self.num_lives < 0:
            return False

        self.sprites.remove(self.lives_sprites[-1])
        del self.lives_sprites[-1]

        print(f"{self.num_lives} lives left")

        return True

    def init_score(self):

        self.score_text = ColorWriter(
            self.display.write_framebuf,
            font_vtks, 35, 6, fgcolor=self.CYAN, bgcolor=self.BLACK,
            screen_width=self.display.width, screen_height=self.display.height)
        self.score_text.text_x = 61
        self.score_text.text_y = 0

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
            large_font, 96, 11, fgcolor=self.CYAN, bgcolor=self.BLACK, screen_width=self.display.width, screen_height=self.display.height)
        game_over_text.text_x = 3
        game_over_text.text_y = 28
        game_over_text.visible = False

        game_over_text.row_clip = True  # Clip or scroll when screen full
        game_over_text.col_clip = True  # Clip or new line when row is full
        game_over_text.wrap = False  # Word wrap

        Writer.set_textpos(self.display.write_framebuf, 0, 0)
        game_over_text.printstring("GAME OVER")

        self.game_over_text = game_over_text
        self.sprites.append(game_over_text)

    def show_game_over(self):
        self.big_text_bg.visible = True
        self.game_over_text.visible = True

        # Animate text colors
        text_colors = [0x00FFFF,0x0094FF,0x00FF90,0x4800FF,0x4CFF00,0x21377F]
        text_color_palette = FramebufferPalette(len(text_colors))

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
        Writer.set_textpos(self.display.write_framebuf, 0, 0)
        self.score_text.printstring(f"{self.score:09}")

    def show(self):
        self.draw_sprites()

    def draw_sprites(self):
        for my_sprite in self.sprites:
            my_sprite.show(self.display)

        self.score_text.show(self.display)


