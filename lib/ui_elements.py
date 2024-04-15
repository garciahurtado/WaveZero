# from displayio import Group, Bitmap, TileGrid
# import adafruit_imageload
# from adafruit_display_text import label
# from adafruit_bitmap_font import bitmap_font
from sprite import Sprite
import framebuf
import color_util as colors
import fonts.vtks_blocketo_6
from font_writer import Writer, CWriter as ColorWriter

class ui():
    display:framebuf.FrameBuffer
    lives_sprite:Sprite
    score = 0
    score_text = None
    sprites = []

    def __init__(self, display) -> None:
        self.display = display
        self.lives_sprite = Sprite("/img/life.bmp")
        pass

    def add(self, sprite):
        self.sprites.append(sprite)

    def init_score(self):
        
        CYAN = self.display.rgb(0,255,255)
        BLACK = self.display.rgb(0,0,0)
        
        self.score_text = ColorWriter(self.display, fonts.vtks_blocketo_6, verbose=True)
        self.score_text.setcolor(CYAN, BLACK)
        Writer.set_textpos(self.display, 0, 60) 
                
        return self.score_text
    
    def draw_score(self, score):
        Writer.set_textpos(self.display, 0, 60)
        self.score_text.printstring(f"{score:09}")

    def draw_lives(self, num_lives=3):
        # life_palette.make_transparent(1)
        bg_index = 0 # Color index to be used as transparent
        bg_color = self.lives_sprite.palette.get_color(bg_index)
        #bg_color = colors.rgb_to_565(bg_color)

        for i in range(0, num_lives):

            x, y = i*12, 0
            self.display.blit(
                self.lives_sprite.pixels,
                x, y,
                bg_color
                )
            pass

    def refresh(self):
        self.draw_sprites()
        self.display.re

    def draw_sprites(self):
        for my_sprite in self.sprites:
            my_sprite.show(self.display)



