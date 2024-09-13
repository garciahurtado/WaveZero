from color.framebuffer_palette import FramebufferPalette
from color import color_util as colors
from color.color_util import BGR565, RGB565

PALETTE_UI_FLASH_TEXT = [0x00FFFF,
                         0xFF00FF,
                         0xFF8000,
                         0x00FFCC,
                         0xCC00FF,
                         0xFFCC00,
                         0x80FFFF,
                         0xFF80FF,
                         0xFFCC80,
                         0x00FFAA
                         ]

PALETTE_SHIFT = [
    0xFF0000,
    0xFFFF00,
    0xFF00FF,
    0x00FFFF,
    0x00FF00,
    0x0000FF
    ]

PALETTE_FIRE = {
    0xFFF300,
    0xFFDC00,
    0xFFC300,
    0xFFB200,
    0xFF9A00,
    0xFF8200,
    0xFD6C00,
    0xF75800,
    0xF34200,
    0xEF3300,
    0xEA1F00,
    0xE60B00,
}

PALETTE_CODE_GREEN = {
    0X002C1E,
    0X00501B,
    0X00870E,
    0X00C000,
    0X00FF00,
    0X00C000,
    0X00870E,
    0X00501B,
    0X002C1E,
}

def convert_hex_palette(hex_palette, color_mode=RGB565):
    color_list_palette = FramebufferPalette(len(hex_palette), color_mode=color_mode)
    inv = False if (color_mode == RGB565) else True
    for i, color in enumerate(hex_palette):
        color_list_palette.set_rgb(i, colors.hex_to_rgb(color, inv=inv))

    return color_list_palette


