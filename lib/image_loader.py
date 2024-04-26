import gc

from ucollections import namedtuple
import uos
from microbmp import MicroBMP as bmp
from color_util import FramebufferPalette
import color_util as colors
import framebuf

class ImageLoader():
    """Preloads a list of images in order to cache their framebuffers (as RGB565) to later be used by Sprites"""
    img_dir = "/img"
    images = {}

    @staticmethod
    def load_images(images, display):
        # Get a list of all BMP files in the specified directory
        bmp_files = [file for file in uos.listdir(ImageLoader.img_dir) if file.endswith(".bmp")]
        image_names = [one_image["name"] for one_image in images]

        print(f"Before counting bytes: {gc.mem_free():,} bytes")

        # Load each BMP file as a Sprite and add it to the sprites list
        file_list = [file for file in list(set(image_names) & set(bmp_files))]

        total_size = 0
        for one_file in file_list:
            filename = f"{ImageLoader.img_dir}/{one_file}"

            # https://docs.pycom.io/firmwareapi/micropython/uos/
            total_size += ImageLoader.get_size(filename)
        loaded_size = 0

        print(f"Loading {total_size:,} bytes of images")
        print(f"Before loading all images: {gc.mem_free():,} bytes")

        for image in images:
            gc.collect()

            file = image['name']
            print(f"Loading {file}")
            print(f"Before loading image: {gc.mem_free():,} bytes")

            image_path = f"{ImageLoader.img_dir}/{file}"
            if 'width' in image and 'height' in image:
                ImageLoader.load_image(image_path, frame_width=image['width'], frame_height=image['height'])
            else:
                ImageLoader.load_image(image_path)

            loaded_size += ImageLoader.get_size(image_path)
            ImageLoader.update_progress(display, loaded_size, total_size)

    @staticmethod
    def get_size(filename):
        stat = uos.stat(filename)

        # https://docs.pycom.io/firmwareapi/micropython/uos/
        size = stat[6]
        return size

    @staticmethod
    def update_progress(display, loaded_size, total_size):
        bar_width = 76
        filled_width = (loaded_size / total_size) * bar_width
        my_color = colors.rgb_to_565([64, 64, 64])

        display.fill(0)
        display.rect(10, 30, bar_width, 5, my_color)
        display.rect(10, 30, int(filled_width), 5, my_color, True)
        display.show()

    @staticmethod
    def load_image(filename, frame_width=0, frame_height=0):
        # First of all, check the cache
        if filename in ImageLoader.images:
            return ImageLoader.images[filename]

        bmp_image = bmp().load(filename)
        print(bmp_image)  # Show metadata

        width = bmp_image.width
        height = bmp_image.height
        palette = bmp_image.palette # List of RGB tuples

        # palette = [colors.bytearray_to_int(colors.byte3_to_byte2(color)) for color in palette]
        palette = FramebufferPalette(palette)

        if frame_width > 0 and frame_height > 0:
            # This is a spritesheet, so lets make frames from the pixel data without allocating new memory
            frames = []
            frame_byte_size = frame_width * frame_height  # assuming < 8 BPP
            pixel_view = memoryview(bmp_image.pixels)

            for i in range(0, len(bmp_image.pixels), frame_byte_size):
                frame = ImageLoader.create_image(
                    bytearray(pixel_view[i:i+frame_byte_size]),
                    frame_width,
                    frame_height,
                    palette)
                frames.append(frame)

            image = frames

        else:
            image = ImageLoader.create_image(bytearray(bmp_image.pixels), width, height, palette)

        ImageLoader.images[filename] = image
        return image

    @staticmethod
    def create_image(bytearray_pixels, width, height, palette):
        num_colors = palette.num_colors

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
