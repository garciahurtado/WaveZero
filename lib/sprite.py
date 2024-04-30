import framebuf
import utime

import color_util as colors
from color_util import FramebufferPalette
from image_loader import ImageLoader
from indexed_image import Image

class Sprite:
    """ Represents a sprite which is loaded from disk in BMP format, and stored in memory as an RGB565 framebuffer"""
    filename: str
    image: Image = None
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
    frames = []
    current_frame = 0
    frame_width = 0
    frame_height = 0
    half_scale_one_dist = 0

    x = 0
    y = 0
    speed = 0

    has_alpha = False
    alpha_color = None
    alpha_index = 0
    min_y = -32
    max_x = 200
    max_y = 200
    dot_color: int = 0

    def __init__(self, filename=None, x=0, y=0, frame_width=None, frame_height=None) -> None:
        self.frame_width = frame_width
        self.frame_height = frame_height

        if filename:
            print(filename)
            self.load_image(filename)
            self.filename = filename

        self.x = x
        self.y = y

        # self.update()

    def reset(self):
        pass
    def set_frame(self, frame_num):
        if frame_num == self.current_frame:
            return False

        self.current_frame = frame_num
        self.image = self.frames[frame_num]

    def update_frame(self):
        """Update the current frame in the spritesheet to the one that represents the correct size when taking into
        account 3D coordinates and the camera"""

        if not self.camera or not self.frames or (len(self.frames) == 0):
            print("MISSING PARAMS ERROR")
            return False

        frame_idx = self.get_frame_idx(self.z)
        if self.current_frame == frame_idx:
            return False

        self.set_frame(frame_idx)

        return True

    def get_frame_idx(self, real_z):

        rate = ((real_z - self.camera.pos['z']) / 2)
        if rate == 0:
            rate = 0.00001 # Avoid divide by zero

        scale = self.half_scale_one_dist / rate
        frame_idx = int(scale * len(self.frames))
        #self.height_2d = scale * self.frame_height
        #self.width_2d = self.ratio * self.height_2d

        if frame_idx >= len(self.frames):
            frame_idx = len(self.frames) - 1

        if frame_idx < 0:
            frame_idx = 0

        return frame_idx

    def load_image(self, filename, frame_width=None, frame_height=None):
        """Overrides parent"""
        if not frame_width:
            frame_width == self.width

        if not frame_height:
            frame_height = self.height

        images = ImageLoader.load_image(filename, frame_width, frame_height)

        if isinstance(images, list):
            print(f"Loaded {len(images)} frames")
            self.frames = images
            self.set_frame(0)
            meta = images[0]
        else:
            self.image = images
            meta = images

        self.width = meta.width
        self.height = meta.height
        self.palette = meta.palette
        self.dot_color = self.palette.get_bytes(1)
        self.num_colors = meta.palette.num_colors
        self.reset()


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

        # If this is a scaled sprite, rather than blit, draw a dot into the framebuffer
        if 5 > self.image.height > 1:
            display.fill_rect(round(x) + 1, round(y) + 1, 2, 2, self.dot_color)
            return True
        if self.image.height <= 1:
            display.pixel(round(x), round(y), self.dot_color)
            return True

        if self.has_alpha:
            #print(f"x/y: {x},{y} / alpha:{self.alpha_color}")
            display.blit(self.image.pixels, round(x), round(y), self.alpha_color, self.palette)
        else:
            display.blit(self.image.pixels, round(x), round(y), -1, self.palette)

    def get_draw_xy(self, display: framebuf.FrameBuffer):
        x, y = self.x, self.y
        return x, y

    def update(self):
        """ Meant to be overridden in child class"""
        if not self.active:
            return False

        self.update_frame()

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




