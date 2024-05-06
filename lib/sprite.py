
import framebuf

import color_util as colors
from color_util import FramebufferPalette
from image_loader import ImageLoader
from indexed_image import Image

class Sprite:
    """ Represents a sprite which is loaded from disk in BMP format, and stored in memory as an RGB565 framebuffer"""
    filename: str
    image: Image = None
    palette: FramebufferPalette
    num_colors: int = 0
    width: int = 0
    height: int = 0
    ratio = 0
    visible = False # Whether show() will render this Sprite
    active = True # Whether update() will update this Sprite
    blink = False
    blink_flip = 1


    x: int = 0
    y: int = 0
    speed: int = 0

    has_alpha = False
    alpha_color = None
    alpha_index: int = 0
    min_y: int = -32
    max_x: int = 200
    max_y: int = 200
    dot_color: int = 0

    def __init__(self, filename=None, x=0, y=0) -> None:

        if filename:
            self.load_image(filename)
            self.filename = filename

        self.x = x
        self.y = y

        # self.update()

    def reset(self):
        pass

    def load_image(self, filename):
        self.filename = filename
        self.image = ImageLoader.load_image(filename)

        meta = self.image

        self.width = meta.width
        self.height = meta.height
        self.palette = meta.palette
        # self.dot_color = self.palette.get_bytes(1)
        self.num_colors = meta.palette.num_colors

        self.visible = True


    def set_alpha(self, alpha_index=0):
        """Sets the index of the color to be used as an alpha channel (transparent), when drawing the sprite
        into the display framebuffer """

        self.has_alpha = True
        self.alpha_index = alpha_index
        alpha_color = self.palette.get_bytes(alpha_index)
        self.alpha_color = alpha_color

    def set_palette(self, palette):
        """ Convert a list of colors to a palette Framebuffer ready to use with display.blit(). Useful in changing
        the color palette of an already loaded image"""
        self.num_colors = len(palette)

        new_palette = framebuf.FrameBuffer(bytearray(self.num_colors * 2), self.num_colors, 1, framebuf.RGB565)
        for i, new_color in enumerate(palette):
            new_color = colors.byte3_to_byte2(new_color)
            new_color = colors.bytearray_to_int(new_color)
            new_palette.pixel(i, 0, new_color)

        self.palette = new_palette

    def show(self, display: framebuf.FrameBuffer, x: int = None, y: int = None):
        if not self.visible or not self.image:
            # print("nothing to show")
            return False

        if x is None or y is None:
            x = self.x
            y = self.y

        # Simulate a transparent Sprite effect
        if self.blink:
            self.blink_flip = self.blink_flip * -1
            if self.blink_flip == -1:
                return False

        if x > self.max_x:
            x = self.max_x

        if y > self.max_y:
            y = self.max_y

        return self.do_blit(x, y, display)


    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer):
        if self.has_alpha:
            #print(f"x/y: {x},{y} / alpha:{self.alpha_color}")
            display.blit(self.image.pixels, x, y, self.alpha_color, self.palette)
        else:
            display.blit(self.image.pixels, x, y, -1, self.palette)

        return True

    def get_draw_xy(self, display: framebuf.FrameBuffer):
        x, y = self.x, self.y
        return x, y

    def update(self):
        """ Meant to be overridden in child class"""
        if not self.active:
            return False

        return True

    def _clone(self):
        copy = Sprite()
        copy.x = self.x
        copy.y = self.y

        copy.image = self.image
        copy.palette = self.palette
        copy.width = self.width
        copy.height = self.height

        copy.has_alpha = self.has_alpha
        copy.alpha_color = self.alpha_color
        copy.alpha_index = self.alpha_index

        return copy

    def clone(self):
        cloned_obj = self.__class__()
        for key, value in self.__dict__.items():
            if False and hasattr(value, 'clone'):
                # Recursively clone the object
                setattr(cloned_obj, key, value.clone())
            else:
                setattr(cloned_obj, key, value)

        return cloned_obj




