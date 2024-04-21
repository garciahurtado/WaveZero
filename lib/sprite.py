from ucollections import namedtuple

from microbmp import MicroBMP as bmp
import framebuf
import os
import color_util as colors
from color_util import FramebufferPalette


class Sprite:
    """ Represents a sprite which is loaded from disk in BMP format, and stored in memory as an RGB565 framebuffer"""
    pixels: framebuf.FrameBuffer = None
    palette: FramebufferPalette
    num_colors = 0
    width = 0
    height = 0
    width_2d = 0
    height_2d = 0
    ratio = 0
    is3d = False
    visible = True
    blink = False
    blink_flip = 1

    x = 0
    y = 0
    z = 0
    draw_x = 0
    draw_y = 0
    speed = 0

    horiz_z = 1500

    has_alpha = False
    alpha_color = None
    alpha_index = 0
    camera = None  # to simulate 3D

    def __init__(self, filename=None, x=0, y=0, z=0, camera=None) -> None:
        if filename:
            print(filename)
            self.load_image(filename)

        self.x = x
        self.y = y
        self.z = z
        self.camera = camera
        self.update()

    def load_image(self, filename):
        """Loads an image from a BMP file and converts it to a binary RGB565 stream for later display"""
        print(f"Loading BMP: {filename}")

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
        alpha_color = self.palette.pixel(alpha_index, 0)
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

    def set_camera(self, camera):
        self.camera = camera

    def show(self, display: framebuf.FrameBuffer):
        if not self.visible:
            return False

        # Simulate a transparent Sprite effect
        if self.blink:
            self.blink_flip = self.blink_flip * -1
            if self.blink_flip == -1:
                return False

        if self.is3d:
            if self.z > self.horiz_z:
                return False

            x, y = self.draw_x, self.draw_y
        else:
            x, y = self.x, self.y

        if x > (display.width * 2):
            x = display.width * 2

        if self.has_alpha:
            display.blit(self.pixels, x, y, self.alpha_color, self.palette)
        else:
            display.blit(self.pixels, x, y, -1, self.palette)

    def update(self):
        if self.speed:
            self.z = self.z + self.speed

        self.draw_x, self.draw_y = self.pos()

    def clone(self):
        copy = Sprite()
        copy.camera = self.camera
        copy.x = self.x
        copy.y = self.y
        copy.z = self.z
        copy.is3d = self.is3d
        copy.draw_x = self.draw_x
        copy.draw_y = self.draw_y

        copy.pixels = self.pixels
        copy.palette = self.palette
        copy.width = self.width
        copy.height = self.height
        copy.horiz_z = self.horiz_z

        copy.has_alpha = self.has_alpha
        copy.alpha_color = self.alpha_color
        copy.alpha_index = self.alpha_index

        return copy

    """3D sprites only"""

    def get_lane(self):
        """
        Returns the lane number which this sprite occupies in 3D space
        """
        if self.x == 0:
            lane = 0
        else:
            lane = int((self.x) / self.lane_width)

        # +2 because X=0 in 3D is at the center and we count
        # lanes from the left edge
        lane = lane + 2
        return lane

    def set_lane(self, lane_num):
        self.x = (lane_num - 2) * self.lane_width

    def pos(self):
        """Returns the 2D coordinates of the object, calculated from the internal x,y (if 2D) or x,y,z
        (if 3D with perspective camera)
        """
        if self.camera:
            x, y = self.camera.to_2d(self.x, self.y + self.height, self.z)

            if y < 0 or self.z <= self.camera.pos['z']:
                self.z = self.camera.horiz_z

            x = int(x - (self.width_2d / 2))  # Draw the object so that it is horizontally centered

            return x, y
        else:
            return self.x, self.y


class Spritesheet(Sprite):
    frames = []
    current_frame = 0
    frame_width = 0
    frame_height = 0
    ratio = 0
    half_scale_one_dist = 0
    lane_width = 0

    def __init__(self, filename=None, frame_width=None, frame_height=None, x=0, y=0, z=0, camera=None, *args, **kwargs):
        self.frame_width = frame_width
        self.frame_height = frame_height


        if filename:
            print(filename)
            self.load_image(filename, frame_width, frame_height)

        self.x = x
        self.y = y
        self.z = z
        self.camera = camera
        self.update()

        if self.frame_width and self.frame_height:
            self.ratio = self.frame_width / self.frame_height

        if self.pixels:
            self.set_frame(0)


    def set_camera(self, camera):
        self.camera = camera
        self.half_scale_one_dist = abs(self.camera.pos['z']) / 2

    def update(self):
        super().update()
        self.update_frame()


    def set_frame(self, frame_num):
        self.current_frame = frame_num
        self.pixels = self.frames[frame_num].pixels

    def update_frame(self):
        """Update the current frame in the spritesheet to the one that represents the correct size when taking into
        account 3D coordinates and the camera"""

        if not self.camera or not self.frames or (len(self.frames) == 0):
            return False

        scale = self.half_scale_one_dist / ((self.z - self.camera.pos['z']) / 2)
        frame_idx = round(scale * len(self.frames))

        if self.current_frame == frame_idx:
            return False

        # print(f"Scale: {scale:.3} / Frame: {frame_idx}")
        self.height_2d = scale * self.frame_height
        self.width_2d = self.ratio * self.height_2d

        if frame_idx < 0:
            frame_idx = 0
        if frame_idx >= len(self.frames):
            frame_idx = len(self.frames) - 1

        self.set_frame(frame_idx)

        return True

    def load_image(self, filename, frame_width, frame_height):
        """Overrides parent"""
        images = ImageLoader.load_image(filename, frame_width, frame_height)

        if isinstance(images, list):
            self.frames = images
            image = images[0]
        else:
            image = images

        self.width = image.width
        self.height = image.height
        self.palette = image.palette
        self.num_colors = image.num_colors

    def clone(self):
        copy = Spritesheet(
            frame_width=self.frame_width,
            frame_height=self.frame_height,
            x=self.x,
            y=self.y,
            z=self.z,
            camera=self.camera
        )
        copy.is3d = self.is3d
        copy.draw_x = self.draw_x
        copy.draw_y = self.draw_y

        copy.pixels = self.pixels
        copy.palette = self.palette
        copy.width = self.width
        copy.height = self.height
        copy.horiz_z = self.horiz_z

        copy.has_alpha = self.has_alpha
        copy.alpha_color = self.alpha_color
        copy.alpha_index = self.alpha_index

        copy.frames = self.frames
        copy.current_frame = self.current_frame
        copy.frame_width = self.frame_width
        copy.frame_height = self.frame_height
        copy.ratio = self.ratio
        copy.half_scale_one_dist = self.half_scale_one_dist
        copy.palette = self.palette.clone()
        copy.lane_width = self.lane_width
        copy.speed = self.speed

        if self.camera:
            copy.set_camera(self.camera)

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
    def load_image(filename, frame_width=0, frame_height=0):
        bmp_image = bmp().load(filename)
        print(bmp_image)  # Show metadata

        width = bmp_image.width
        height = bmp_image.height
        palette = bmp_image.palette

        # palette = [colors.bytearray_to_int(colors.byte3_to_byte2(color)) for color in palette]
        palette = FramebufferPalette(palette)

        if frame_width and frame_height:
            # This is a spritesheet, so lets make frames from the pixel data without allocating new memory
            frames = []
            frame_byte_size = frame_width * frame_height  # assuming < 8 BPP
            pixel_view = memoryview(bmp_image.pixels)

            for i in range(0, len(bmp_image.pixels), frame_byte_size):
                frame = pixel_view[i:i+frame_byte_size]

                image = ImageLoader.create_image(bytearray(frame), frame_width, frame_height, palette)
                frames.append(image)

            return frames

        else:
            bytearray_pixels = bytearray(bmp_image.pixels)
            image = ImageLoader.create_image(bytearray_pixels, width, height, palette)

            return image

    @staticmethod
    def create_image(bytearray_pixels, width, height, palette):
        num_colors = len(palette)

        image_buffer = framebuf.FrameBuffer(
            bytearray_pixels,
            width,
            height,
            framebuf.GS8)

        image = Image(
            width,
            height,
            image_buffer,
            num_colors,
            palette)

        return image

    @staticmethod
    def load_as_palette(filename):
        image = ImageLoader.load_image(filename)

        return image.palette


Image = namedtuple("Image",
                   ("width",
                    "height",
                    "pixels",
                    "num_colors",
                    "palette",)
                   )
