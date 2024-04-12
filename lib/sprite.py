from ucollections import namedtuple

from microbmp import MicroBMP as bmp
import framebuf
import os
import color_old as colors
import math
from camera3d import Point3D


class Sprite:
    """ Represents a sprite which is loaded from disk in BMP format, and stored in memory as an RGB565 framebuffer"""
    pixels = None
    palette = []
    width = 0
    height = 0
    width_2d = 0
    height_2d = 0
    ratio = 0

    x = 0
    y = 0
    z = 0  # used in pseudo 3D rendering
    draw_x = 0
    draw_y = 0

    horiz_z = 2000

    has_alpha = False
    alpha_color = None
    camera = None  # to simulate 3D
    point: Point3D

    def __init__(self, filename=None, x=0, y=0, z=0, camera=None) -> None:
        if filename:
            self.load_image(filename)

        self.x = x
        self.y = y
        self.z = z
        self.camera = camera

    def load_image(self, filename):
        """Loads an image from a BMP file and converts it to a binary RGB565 stream for later display"""
        print(f"Loading BMP: {filename}")

        image = ImageLoader.load_image(filename)

        # if filename in ImageLoader.images:
        #     image = ImageLoader.images[filename]
        # else:
        #     image = ImageLoader.load_image(filename)
        #     ImageLoader.images[filename] = image

        self.width = image.width
        self.height = image.height
        self.ratio = self.width / self.height
        self.palette = image.palette
        self.pixels = image.pixels

    def set_alpha(self, alpha_index=0):
        """Sets the index of the color to be used as an alpha channel (transparent), when drawing the sprite
        into the display framebuffer """

        self.has_alpha = True
        self.alpha_color = self.palette[alpha_index]
        self.alpha_color = colors.rgb_to_565(self.alpha_color)
        # alpha_color = alpha_color[2],alpha_color[1],alpha_color[0] # RGB to BGR
        # self.alpha_color = colors.rgb_to_565(alpha_color)
        print(f"Alpha color: {colors.rgb565_to_rgb(self.alpha_color)}")

    def show(self, display: framebuf.FrameBuffer):
        x, y = self.pos()
        if x > (display.width * 2):
            x = display.width * 2

        if self.has_alpha:
            display.blit(self.pixels, x, y, self.alpha_color)
        else:
            display.blit(self.pixels, x, y)

    def clone(self):
        copy = self.__class__()
        copy.camera = self.camera
        copy.x = self.x
        copy.y = self.y
        copy.z = self.z

        copy.pixels = self.pixels
        copy.width = self.width
        copy.height = self.height
        copy.horiz_z = self.horiz_z

        copy.has_alpha = self.has_alpha
        copy.alpha_color = self.alpha_color

        return copy

    """3D sprites only"""


    def get_lane(self, offset):
        """
        Returns the lane number which this sprite occupies in 3D space
        """
        total_width = self.num_lanes * self.lane_width

        if (self.x + offset) == 0:
            return 0
        else:
            return math.floor((self.x + offset) / self.lane_width)

    def pos(self):
        """Returns the 2D coordinates of the object, calculated from the internal x,y (if 2D) or x,y,z
        (if 3D with perspective camera)
        """
        if self.camera:
            x, y = self.camera.to2d2(self.x, self.y, self.z)
            x = int(x - (self.width_2d / 2))
            y = int(y - self.height_2d) # set the object on the "floor", since it starts being drawn from the top

            return x, y
        else:
            return self.x, self.y


class Spritesheet(Sprite):
    frames = []
    current_frame = 0
    frame_width = 0
    frame_height = 0
    scale_one_dist = 0

    def __init__(self, filename=None, frame_width=None, frame_height=None, *args, **kwargs):
        super().__init__(filename, *args, **kwargs)

        if frame_width and frame_height:
            self.frame_width = frame_width
            self.frame_height = frame_height

            num_frames = self.width // frame_width
            print(f"Spritesheet with {num_frames} frames")

            self.frames = [None] * num_frames

            for idx in range(num_frames):
                x = idx * frame_width
                y = 0

                buffer = bytearray(frame_width * frame_height * 2)
                my_buffer = framebuf.FrameBuffer(buffer, frame_width, frame_height, framebuf.RGB565)

                for i in range(frame_width):
                    for j in range(frame_height):
                        color = self.pixels.pixel(x + i, y + j)
                        my_buffer.pixel(i, j, color)

                self.frames[idx] = my_buffer

            self.set_frame(0)

    def set_frame(self, frame_num):
        self.current_frame = frame_num
        self.pixels = self.frames[frame_num]

    def update_frame(self):
        """Update the current frame in the spritesheet to the one that represents the correct size when taking into
        account 3D coordinates and the camera"""

        if not self.frames or len(self.frames) == 0 or not self.camera:
            return False

        scale_one_dist = abs(self.camera.pos['z'])
        scale = (scale_one_dist / 2) / ((self.z - self.camera.pos['z']) / 2)
        frame_idx = int(scale * len(self.frames))

        print(f"Scale: {scale:.3} / Frame: {frame_idx}")
        self.height_2d = scale * self.height
        self.width_2d = int(self.ratio * self.height_2d)
        self.height_2d = int(self.height_2d)

        if frame_idx < 0:
            frame_idx = 0
        if frame_idx >= len(self.frames):
            frame_idx = len(self.frames) - 1
        self.set_frame(frame_idx)

        return True

    def clone(self):
        copy = super().clone()
        copy.frames = self.frames
        copy.current_frame = self.current_frame
        copy.frame_width = self.frame_width
        copy.frame_height = self.frame_height

        return copy


class ImageLoader():
    """Preloads a list of images in order to cache their framebuffers (as RGB565) to later be used by Sprites"""
    img_dir = "/img"
    images = {}

    @staticmethod
    def load_images(image_names):
        # Get a list of all BMP files in the specified directory
        bmp_files = [file for file in os.listdir(ImageLoader.img_dir) if file.endswith(".bmp")]

        # Load each BMP file as a Sprite and add it to the sprites list
        for file in list(set(image_names) & set(bmp_files)):
            print(f"Loading {file}")
            image_path = os.path.join(ImageLoader.img_dir, file)
            image = ImageLoader.load_image(image_path)
            ImageLoader.images[image_path] = image

    @staticmethod
    def load_image(filename):
        bmp_image = bmp().load(filename)
        print(bmp_image)  # Show metadata

        width = bmp_image.DIB_w
        height = bmp_image.DIB_h
        palette = bmp_image.palette

        print("Creating framebuffer...")

        image = Image(
            width,
            height,
            framebuf.FrameBuffer(
                bmp_image.rgb565(),
                width,
                height,
                framebuf.RGB565),
            palette)

        return image


Image = namedtuple("Image",
                   ("width",
                    "height",
                    "pixels",
                    "palette",)
                   )
