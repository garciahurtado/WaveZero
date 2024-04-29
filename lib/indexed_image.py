import framebuf
from ucollections import namedtuple


Image = namedtuple("Image",
           [
            "width",
            "height",
            "pixels",
            "pixel_bytes",
            "palette"
           ]
        )


def create_image(image_buffer: framebuf.FrameBuffer, pixel_bytes: bytearray, width: int, height: int, palette):
    image = Image(
        width,
        height,
        image_buffer,
        pixel_bytes,
        palette)

    return image

