import framebuf
from ucollections import namedtuple


Image = namedtuple("Image",
           (
            "width",
            "height",
            "pixels",
            "pixel_bytes",
            "palette",
            "palette_bytes",
            "color_depth",
            "frames"
           )
        )


def create_image(
        width: int,
        height: int,
        pixels: framebuf.FrameBuffer,
        pixel_bytes: bytearray,
        palette,
        palette_bytes: bytearray,
        color_depth: int,
        frames=None):

    image = Image(
        width,
        height,
        pixels,
        pixel_bytes,
        palette,
        palette_bytes,
        color_depth,
        frames)

    return image

