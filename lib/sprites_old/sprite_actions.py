import random
from colors import color_util as colors
from collections import namedtuple

PixelBounds = namedtuple(
        "PixelBounds",
        (
            "left",
            "right",
            "top",
            "bottom",
        )
    )

class Actions:
    display = None
    camera = None
    sprite_mgr = None
    margins = None
    by_sprite = {}

    def __init__(self, display=None, camera=None, mgr=None):

        """ Extra width and height margins (each side) """
        extra_width = extra_height = 16

        self.display = display
        # self.bounds_width = display.width +

        self.margins = PixelBounds(
            -extra_width,
            display.width + extra_width,
            -extra_height,
            display.height + extra_height,
        )
        self.bounds_width
        self.bounds_height

        self.camera = camera
        self.sprite_mgr = mgr

    def add_action(self, sprite_type, func):
        self.by_sprite[sprite_type] = func

    def run_action(self, inst, sprite_type, func):
        self.by_sprite[sprite_type] = func

    def for_sprite(self, sprite_type):
        if sprite_type in self.by_sprite.keys():
            actions = self.by_sprite[sprite_type]
        else:
            actions = None

        return actions

    def ground_laser(self, display, from_x, from_y, x, y, z, sprite_width):
        if z < 200:
            line_colors = 0xFF0000, 0xF63800, 0xFF7C00, 0xFFBB00
            # if random.randrange(0,2):
            #     return

            id = random.randrange(0, 4)

            line_color = colors.rgb_to_565(colors.hex_to_rgb(line_colors[id]), color_format=colors.RGB565)
            half_width = sprite_width // 2
            [to_x, to_y] = self.camera.to_2d(x+half_width, 0, z)

            display.line(to_x, int(from_y), to_x, to_y, line_color)
            display.line(to_x-1, int(from_y), to_x+2, to_y, line_color)

            """Sparks"""
            color = colors.rgb_to_565(colors.hex_to_rgb(0xFFFF00), color_format=colors.RGB565)

            x_offset = random.randrange(-4,+4)
            display.line(to_x, to_y, to_x+5+x_offset, to_y-7, color)
            x_offset = random.randrange(-4,+4)
            display.line(to_x, to_y, to_x-3+x_offset, to_y-5, color)
            x_offset = random.randrange(-4,+4)
            display.line(to_x, to_y, to_x-1+x_offset, to_y-8, color)


    def check_bounds_and_remove(self, sprite, params):
        print("Checking bounds")
        half_sprite = sprite.width // 2 # Assumes 1:1 aspect ratio
        sprite_x = sprite.x + half_sprite
        sprite_y = sprite.y + half_sprite
        margins = self.margins

        if (sprite_x < margins.x0) or\
           (sprite_x > margins.x1) or\
           (sprite_y < margins.x0) or\
           (sprite_y < margins.x0):
            self.sprite_mgr.release(sprite)

