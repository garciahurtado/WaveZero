
import framebuf
from micropython import const

import color_util as colors
from framebuffer_palette import FramebufferPalette
from images.image_loader import ImageLoader
from images.indexed_image import Image

class Sprite:
    """ Represents a sprite which is loaded from disk in BMP format, and stored in memory as an RGB565 framebuffer"""
    filename: str
    image: Image = None
    palette: FramebufferPalette
    palette_bytes: bytearray
    num_colors: int = 0
    width: int = 0
    height: int = 0
    ratio = 0
    visible = False # Whether show() will render this Sprite
    active = True # Whether update() will update this Sprite
    blink = False
    blink_flip = 1
    has_physics: bool

    x: int = 0
    y: int = 0
    speed: int = 0

    has_alpha = False
    alpha_color = None
    alpha_index: int = 0
    min_x = const(-40)
    max_x = const(200)
    min_y = const(-40)
    max_y = const(200)
    dot_color: int = 0
    pool = None # The pool that spawned this sprite
    pos_type = None # To help the stage place the sprite in order according to Z index

    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)
    event_chain = None

    def __init__(self, filename=None, x=0, y=0, speed=0, pos_type=None, width=None, height=None):
        if width and height:
            self.width = width
            self.height = height

        if filename:
            self.load_image(filename, width, height)
            self.filename = filename

        self.x = x
        self.y = y
        self.speed = speed
        self.event_chain = None

        if pos_type:
            self.pos_type = pos_type
        else:
            self.pos_type = self.POS_TYPE_FAR

        self.has_physics = False
        # self.update()

    def reset(self):
        self.active = True
        self.visible = True
        if self.event_chain:
            self.event_chain.start()

    def load_image_old(self, filename, width, height):
        self.filename = filename
        self.image = ImageLoader.load_image(filename, frame_width=width, frame_height=height)

        meta = self.image

        self.width = meta.width
        self.height = meta.height
        self.palette = meta.palette
        self.num_colors = meta.palette.num_colors

        self.visible = True

        return meta

    def load_image(self, filename, frame_width, frame_height):
        # color_depth = self.color_depth
        # if not frame_height or not frame_height:
        #     frame_width=self.width
        #     frame_height=self.height

        image = ImageLoader.load_image(filename, frame_width=frame_width, frame_height=frame_height)
        self.frames = image.frames

        if image.frames:
            self.num_frames = len(image.frames)
        else:
            self.num_frames = 0

        print(f"Loaded {self.num_frames} frames")


        # self.width = meta.width
        # self.height = meta.height
        self.image = image.pixels
        self.palette = image.palette
        self.dot_color = self.palette.get_bytes(1)
        self.num_colors = image.palette.num_colors
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

    def show(self, display: framebuf.FrameBuffer, x: int = None, y: int = None, palette=None):
        if not self.visible or not self.image:
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

        if x < self.min_x:
            x = self.min_x

        if y < self.min_y:
            y = self.min_y

        return self.do_blit(x, y, display, palette=palette)

    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer, palette=None):
        palette = palette if palette else self.palette
        if self.has_alpha:
            display.blit(self.image, int(x), int(y), self.alpha_color, palette)
        else:
            display.blit(self.image, int(x), int(y), -1, palette)

        return True

    def update(self, elapsed=None):
        """ Meant to be overridden in child class"""
        if not self.active:
            return False

        if self.event_chain:
            self.event_chain.update()

        return True

    def clone(self):
        cloned_obj = self.__class__()
        for key, value in self.__dict__.items():
            if False and hasattr(value, 'clone'):
                # Recursively clone the object
                setattr(cloned_obj, key, value.clone())
            else:
                setattr(cloned_obj, key, value)

        return cloned_obj

    def kill(self):
        self.active = False
        self.visible = False

        """ If this sprite came from a pool, return it to the pool"""
        if self.pool:
            self.pool.add(self)




