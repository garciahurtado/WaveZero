from anim.palette_rotate_one import PaletteRotateOne
from sprites2.sprite_types import *
from color.framebuffer_palette import FramebufferPalette
from color import color_util as colors


class LaserWall(SpriteType):
    name = SPRITE_LASER_WALL
    image_path = "/img/laser_wall.bmp"
    speed = 0
    width = 24
    height = 10
    color_depth = 4
    alpha = None
    x = 0
    y = 0
    z = 10000

    rotate_change_index = 1
    rotate_pal_index = 0
    rotate_new_palette = [
        0xff0500,
        0xff4200,
        0xff5e00,
        0xff7e00,
        0xffab00,
        0xfed300,
        0xfff500
    ]

    rotate_pal_freq = 1000 # ms
    rotate_task = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # new_palette = FramebufferPalette(len(self.rotate_new_palette))
        # for i, color in enumerate(self.rotate_new_palette):
        #     rgb = colors.hex_to_rgb(color)
        #     new_palette.set_rgb(i, rgb)
        #
        # self.rotate_palette = new_palette
        #
        # anim = PaletteRotateOne(self.palette, self.rotate_palette, 500, 1)
        # self.animations.append(anim)

    def do_rotate_palette(self):
        if not self.palette or not self.rotate_new_palette:
            return False

        new_palette = self.rotate_new_palette

        num_colors = len(new_palette)
        source_idx = self.rotate_pal_index
        target_idx = self.rotate_change_index
        new_color = new_palette.get_bytes(source_idx)
        self.palette.set_bytes(target_idx, new_color)

        self.rotate_pal_index = (source_idx + 1) % num_colors



