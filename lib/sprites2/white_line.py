from sprites2.sprite_types import *
from color.palettes import PALETTE_SHIFT, PALETTE_UI_FLASH_TEXT, convert_hex_palette, PALETTE_FIRE, PALETTE_CODE_GREEN
from color.color_util import BGR565, RGB565

class WhiteLine(SpriteType):
    name = SPRITE_WHITE_LINE
    rotate_palette = PALETTE_CODE_GREEN
    rotate_pal_freq = 200 / 1000

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.rotate_palette = convert_hex_palette(self.rotate_palette, color_mode=RGB565)