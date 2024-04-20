# from displayio import Group, Bitmap, TileGrid
# import adafruit_imageload
# from adafruit_display_text import label
# from adafruit_bitmap_font import bitmap_font
import ssd1331_16bit
from sprite import Sprite
import framebuf
import color_util as colors
import fonts.vtks_blocketo_6px as font
from font_writer import Writer, ColorWriter


class ui_screen():
    display: ssd1331_16bit
    lives_sprite: Sprite
    score = 0
    score_text = None
    sprites = []
    lives_sprites = []
    num_lives = 3

    def __init__(self, display) -> None:
        self.display = display
        self.lives_sprite = Sprite("/img/life.bmp")
        self.lives_sprite.set_alpha(0)

        self.init_lives()
        self.init_score()

    def init_lives(self):
        for i in range(0, self.num_lives):
            x, y = i * 12, 0
            new_sprite = self.lives_sprite.clone()
            new_sprite.x = x
            new_sprite.y = y
            self.add(new_sprite)

    def remove_life(self):
        self.num_lives = self.num_lives - 1
        self.lives_sprites = []
        self.init_lives()

    def init_score(self):
        CYAN = (0, 255, 255)
        BLACK = (0, 0, 0)

        self.score_text = ColorWriter(
            self.display,
            font, 35, 6, fgcolor=CYAN, bgcolor=BLACK)
        self.score_text.text_x = 61
        self.score_text.text_y = 0

        return self.score_text

    def update_score(self, new_score):
        if new_score == self.score:
            return False

        self.score = new_score
        Writer.set_textpos(self.display, 0, 0)
        self.score_text.printstring(f"{self.score:09}")


    def add(self, sprite):
        self.sprites.append(sprite)


    def draw_sprites(self):
        for my_sprite in self.sprites:
            my_sprite.show(self.display)

        self.score_text.show(self.display)
