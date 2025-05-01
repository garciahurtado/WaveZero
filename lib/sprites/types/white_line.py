from sprites.sprite_types import *
from colors.palettes import convert_hex_palette, PALETTE_CODE_BLUE
from colors.color_util import RGB565

class WhiteLine(SpriteType):
    name = SPRITE_WHITE_LINE
    rotate_palette = PALETTE_CODE_BLUE
    rotate_pal_freq = 150 / 1000
    repeat_spacing = 24
    alpha_color = 0

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rotate_palette = convert_hex_palette(self.rotate_palette, color_mode=RGB565)