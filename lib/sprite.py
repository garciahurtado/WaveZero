import framebuf
import color_util as colors
from color_util import FramebufferPalette
from image_loader import ImageLoader

class Sprite:
    """ Represents a sprite which is loaded from disk in BMP format, and stored in memory as an RGB565 framebuffer"""
    filename: str
    pixels: framebuf.FrameBuffer = None
    palette: FramebufferPalette
    num_colors = 0
    width = 0
    height = 0
    width_2d = 0
    height_2d = 0
    ratio = 0
    is3d = False
    visible = True # Whether show() will render this Sprite
    active = True # Whether update() will update this Sprite
    blink = False
    blink_flip = 1

    x = 0
    y = 0
    speed = 0

    has_alpha = False
    alpha_color = None
    alpha_index = 0
    min_y = -32
    max_x = 200
    max_y = 200

    def __init__(self, filename=None, x=0, y=0) -> None:
        if filename:
            print(filename)
            self.load_image(filename)
            self.filename = filename

        self.x = x
        self.y = y
        # self.update()

    def reset(self):
        pass

    def load_image(self, filename):
        """Loads an image from a BMP file and converts it to a binary RGB565 stream for later display"""

        image = ImageLoader.load_image(filename)

        self.width = image.width
        self.height = image.height
        self.palette = image.palette
        self.num_colors = image.num_colors
        self.pixels = image.pixels


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

    def show(self, display: framebuf.FrameBuffer):
        if not self.visible:
            return False

        # Simulate a transparent Sprite effect
        if self.blink:
            self.blink_flip = self.blink_flip * -1
            if self.blink_flip == -1:
                return False

        x, y = self.get_draw_xy(display)

        if x > self.max_x:
            x = self.max_x

        if y > self.max_y:
            y = self.max_y

        if self.has_alpha:
            display.blit(self.pixels, round(x), round(y), self.alpha_color, self.palette)
        else:
            display.blit(self.pixels, round(x), round(y), -1, self.palette)

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

        copy.pixels = self.pixels
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




