import gc

import uos
from images.bmp_reader import BMPReader
from colors.color_util import rgb_to_565
from images.indexed_image import Image
from framebuf import GS4_HMSB

class ImageLoader():
    """Preloads a list of images in order to cache their framebuffers (as RGB565) to later be used by Sprites"""
    img_dir = "/img"
    images = {}
    bmp_reader = BMPReader()

    progress_loaded = 0
    progress_total = 0
    progress_bar_color = rgb_to_565([24, 24, 24])
    progress_bar_bg_color = rgb_to_565([12, 12, 12])

    @staticmethod
    def load_images(images, display):
        # Get a list of all BMP files in the specified directory
        bmp_files = [file for file in uos.listdir(ImageLoader.img_dir) if file.endswith(".bmp")]
        image_names = [one_image["name"] for one_image in images]

        # Load each BMP file as a Sprite and add it to the sprites list
        file_list = [file for file in list(set(image_names) & set(bmp_files))]

        total_size = 0
        for one_file in file_list:
            filename = f"{ImageLoader.img_dir}/{one_file}"

            # https://docs.pycom.io/firmwareapi/micropython/uos/
            total_size += ImageLoader.get_size(filename)

        ImageLoader.progress_total = total_size
        ImageLoader.progress_loaded = 0

        print(f"Loading {total_size:,} bytes of images")
        print(f"Before loading all images: {gc.mem_free():,} bytes")

        for image in images:
            file = image['name']
            print(f"Loading {file} ({image['width']}x{image['height']})")

            image_path = f"{ImageLoader.img_dir}/{file}"
            color_depth = image['color_depth'] if 'color_depth' in image else None

            image_size = ImageLoader.get_size(image_path)
            callback = lambda percent: ImageLoader.update_progress(display, percent, image_size)

            if 'width' in image and 'height' in image:
                ImageLoader.load_image(image_path, frame_width=image['width'], frame_height=image['height'], color_depth=color_depth, progress_callback=callback)
            else:
                ImageLoader.load_image(image_path, color_depth=color_depth, progress_callback=callback)

            ImageLoader.progress_loaded += image_size
            ImageLoader.update_progress(display)


    @staticmethod
    def get_size(filename):
        stat = uos.stat(filename)

        # https://docs.pycom.io/firmwareapi/micropython/uos/
        size = stat[6]
        return size

    @staticmethod
    def update_progress(display, ratio=1, image_size=0):
        delta = ratio * image_size
        if delta == 0:
            return False

        progress_loaded = ImageLoader.progress_loaded + delta
        progress_total = ImageLoader.progress_total
        if progress_total == 0:
            progress_total = 0.001

        bar_width = 76
        bar_height = 4
        filled_width = int((progress_loaded / progress_total) * bar_width)
        filled_width = filled_width if filled_width < bar_width else bar_width


        display.fill(0)
        display.rect(10, 30, bar_width, bar_height, ImageLoader.progress_bar_bg_color, True)
        display.rect(10, 30, int(filled_width), bar_height, ImageLoader.progress_bar_color, True)
        display.show()

    @staticmethod
    def load_image(filename, frame_width=0, frame_height=0, color_depth=GS4_HMSB, progress_callback=None, prescale=True) -> Image:
        # First of all, check the cache
        if filename in ImageLoader.images.keys():
            image = ImageLoader.images[filename]
            return image

        reader = ImageLoader.bmp_reader
        reader.color_depth = color_depth

        if frame_width and frame_height:
            """ Image is a spritesheet"""
            image = reader.load(filename, frame_width, frame_height, progress_callback=progress_callback)
        else:
            image = reader.load(filename, progress_callback=progress_callback)

        ImageLoader.images[filename] = image
        return image

        # if frame_width and frame_height:
        #     # This is a spritesheet, so lets make frames from the pixel data without allocating new memory
        #     ImageLoader.images[filename] = reader.frames
        #     return reader.frames
        #
        # else:
        #     ImageLoader.images[filename] = reader.frames[0]
        #     return reader.frames[0]


    @staticmethod
    def load_as_palette(filename):
        image = ImageLoader.load_image(filename)

        return image.palette


