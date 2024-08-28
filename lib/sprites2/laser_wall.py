import asyncio

from anim.anim_attr import AnimAttr
from anim.palette_rotate import PaletteRotate
from sprites2.sprite_types import SpriteType
from sprites2.sprite_types import *
from framebuffer_palette import FramebufferPalette
import color_util as colors

class LaserWall(SpriteType):
    name = SPRITE_LASER_WALL
    image_path = "/img/laser_wall.bmp"
    speed = -150
    width = 24
    height = 15
    color_depth = 4
    alpha = None
    repeats = 3
    repeat_spacing = 22

    rotate_palette = [
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

        new_palette = FramebufferPalette(len(self.rotate_palette))
        for i, color in enumerate(self.rotate_palette):
            rgb = colors.hex_to_rgb(color)
            new_palette.set_rgb(i, rgb)

        self.rotate_palette = new_palette
        #
        # loop = asyncio.get_event_loop()
        # anim = PaletteRotate(self.rotate_palette, 500, [0,1])
        # self.rotate_task = loop.create_task(anim.run())
