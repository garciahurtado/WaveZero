from displayio import Group, Bitmap, TileGrid
import adafruit_imageload
from adafruit_display_text import label
from adafruit_bitmap_font import bitmap_font


def init_score(root):
    font = bitmap_font.load_font("fonts/vtksblocketo-7.bdf", Bitmap)
    score_text = label.Label(font, text="000000000", color=0x00FFFF)
    score_text.x = 60
    score_text.y = 2
    root.append(score_text)
    return score_text

def draw_lives(root):
    life_bitmap, life_palette = adafruit_imageload.load("/img/life.bmp")
    life_palette.make_transparent(1)
    lives = 3
    group = Group()
    for i in range(lives):
        grid = TileGrid(life_bitmap, pixel_shader=life_palette, x=i*12, y=0, tile_width=12, tile_height=7)
        group.append(grid)
        
    root.append(group)
    
def draw_score(score, score_text):
    score_text.text = f"{score:09}"
    


