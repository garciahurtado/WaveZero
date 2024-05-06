import gc
import uos
from microbmp import MicroBMP as microbmp
import color_util as colors

class ImageLoader():
    """Preloads a list of images in order to cache their framebuffers (as RGB565) to later be used by Sprites"""
    img_dir = "/img"
    images = {}
    bmp_reader = microbmp()

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
        loaded_size = 0

        # print(f"Loading {total_size:,} bytes of images")
        print(f"Before loading all images: {gc.mem_free():,} bytes")

        for image in images:
            file = image['name']
            print(f"Loading {file}")

            image_path = f"{ImageLoader.img_dir}/{file}"
            color_depth = image['color_depth'] if 'color_depth' in image else None

            if 'width' in image and 'height' in image:
                ImageLoader.load_image(image_path, frame_width=image['width'], frame_height=image['height'], color_depth=color_depth)
            else:
                ImageLoader.load_image(image_path, color_depth=color_depth)

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
    def load_image(filename, frame_width=0, frame_height=0, color_depth=8):
        # First of all, check the cache
        if filename in ImageLoader.images.keys():
            frames = ImageLoader.images[filename]
            return frames

        print(f"Loading BMP: {filename}")

        reader = ImageLoader.bmp_reader
        reader.frame_width = reader.width = frame_width
        reader.frame_height = reader.height = frame_height
        reader.color_depth = color_depth
        reader._init()

        gc.collect()
        reader.load(filename)

        print(reader)  # Show metadata

        if frame_width and frame_height:
            # This is a spritesheet, so lets make frames from the pixel data without allocating new memory
            ImageLoader.images[filename] = reader.frames
            return reader.frames

        else:
            ImageLoader.images[filename] = reader.frames[0]
            return reader.frames[0]


    @staticmethod
    def load_as_palette(filename):
        image = ImageLoader.load_image(filename)

        return image.palette


