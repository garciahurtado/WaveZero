import math

import framebuf
import uctypes
from framebuf import *
from struct import unpack

from colors.framebuffer_palette import FramebufferPalette as BufPalette
from images.indexed_image import Image, create_image
from colors import color_util as colors
from utils import aligned_buffer


class BMPReader():
    color_mode_map = {
            1 : MONO_HMSB,
            2 : GS2_HMSB,
            4 : GS4_HMSB,
            8 : GS8,
            16: RGB565,
        }

    frames = None
    with_frames = False

    def __init__(self, basedir:str=None):
        self.basedir:str = basedir
        pass

    def load(self, filename:str, frame_width=None, frame_height=None, color_mode=GS4_HMSB, progress_callback=None):
        """
        Load a BMP file and return an Image object.

        Supports single images and sprite sheets (vertical stacking only).

        :param filename: Path to the BMP file (relative from basedir)
        :param frame_width: Width of each frame in a sprite sheet (optional)
        :param frame_height: Height of each frame in a sprite sheet (optional)
        :param color_depth: Color depth of the image (default: GS4_HMSB)
        :return: Loaded Image object
        """

        if self.basedir:
            filename = self.basedir + filename

        assert color_mode in (MONO_HMSB, GS2_HMSB, GS4_HMSB, GS8, RGB565)

        with open(filename, "rb") as file:
            """Read image from BytesIO or FileIO."""
            header = self._read_header(file)
            header.ppb = 8 // header.color_depth
            header.pmask = 0xFF >> (8 - header.color_depth)

            palette, palette_bytes = self._read_palette(file, header)

            maybe_frames, pixel_bytes = self._read_pixels(file, header, frame_width, frame_height, progress_callback)

            """ We have multiple frames"""
            if type(maybe_frames) is list:
                frames = maybe_frames
                pixels = frames[0]
            else:
                frames = None
                pixels = maybe_frames

            pixel_bytes_addr = uctypes.addressof(pixel_bytes)
            loaded_image = self._as_image(header, pixels, pixel_bytes, pixel_bytes_addr, palette, palette_bytes, header.color_depth, frames)

            return loaded_image


    def _read_header(self, file):
        """
        Read and parse BMP and DIB headers from the file.

        :param file: Open file object
        :return: ImageMeta object containing header information
        """

        # BMP Header
        chunk = file.read(14)
        meta_bmp = DynamicAttr()
        meta_bmp.id, meta_bmp.size, meta_bmp.reserved1, meta_bmp.reserved2, meta_bmp.offset = unpack("<2sI2s2sI", chunk)

        # Read DIB Header and populate meta object
        meta = ImageMeta()
        header_len = unpack("<I", file.read(4))
        header_len = header_len[0]

        chunk = file.read(header_len - 4)
        (
            meta.width,
            meta.height,
            meta.planes_num,
            meta.color_depth,
            meta.compression,
            meta.raw_size,
            meta.hres,
            meta.vres,
            meta.num_colors,
            _                   # DIB_plt_important_num_info (unused)
        ) = unpack("<iiHHIIiiII", chunk[:40])  # Read first 40 bytes

        color_format = self.color_mode_map[meta.color_depth]
        meta.color_format = color_format

        return meta

    def _read_palette(self, file, header) -> (BufPalette, bytearray):
        """
        Read color palette data for indexed color modes.

        :param file: Open file object
        :param color_depth: Color depth of the image
        :param num_colors: Number of colors in the palette
        :return: FramebufferPalette object
        """
        color_depth, num_colors = header.color_depth, header.num_colors
        palette_bytes = bytearray(num_colors * 2)

        if color_depth <= 8:
            palette = BufPalette(num_colors)
            for color_idx in range(num_colors):
                """ The colors are stored in RGB format, but we need to extract the bytes as little endian"""

                color_data = file.read(4) # Read 4 bytes at a time and discard the last one (alpha)
                # print(f"palette color data RGB: 0x{color_data[0]:02x}{color_data[1]:02x}{color_data[2]:02x}")
                color_bytes = colors.byte3_to_byte2([color_data[0], color_data[1], color_data[2]])

                # print(f"color bytes: 0x{color_bytes[0]:02x}{color_bytes[1]:02x}")

                color = int.from_bytes(color_bytes[:2], "little")
                palette.set_bytes(color_idx, color)

            return palette, palette_bytes
        else:
            raise TypeError(f"Invalid color depth:{color_depth}")

    def _read_pixels(self, file, meta, frame_width=None, frame_height=None, progress_callback=None) -> [Image]:
        """
        Read pixel data from the file, handling both single images and sprite sheets.

        :param file: Open file object
        :param meta: ImageMeta object containing image metadata
        :param frame_height: Height of each frame in a sprite sheet (optional)
        :return: List of FrameBuffer objects for sprite sheets, or a single FrameBuffer for regular images
        """

        byte_data = None

        if (frame_width and frame_height) and frame_height < meta.height:
            """ This is a spritesheet"""

            self.frames = []
            num_frames = math.floor(meta.height / frame_height)

            for frame_idx in range(num_frames):
                frame_buffer, byte_data = self._create_frame_buffer(frame_width, frame_height, meta.color_format)
                self._read_frame_data(file, frame_buffer, meta, frame_height)
                self.frames.append(frame_buffer)

                if progress_callback:
                    """ Call with the ratio of the image loaded"""
                    progress_callback((frame_idx)/num_frames)

            if not meta.is_top_down:
                self.frames.reverse()

            return self.frames, byte_data

        else:
            """ normal sprite """
            frame_buffer, byte_data = self._create_frame_buffer(meta.width, meta.height, meta.color_format)
            self._read_frame_data(file, frame_buffer, meta, meta.height)

            return frame_buffer, byte_data


    def _read_frame_data(self, file, frame_buffer: FrameBuffer, header, frame_height) -> None:
        """
        Read frame data from the file and populate the FrameBuffer.

        :param file: Open file object
        :param frame_buffer: FrameBuffer object to populate
        :param header: Image metadata object
        :param frame_height: Height of one frame (optional)
        """

        width, height, color_depth, is_top_down = header.width, header.height, header.color_depth, header.is_top_down

        ppb, pmask = header.ppb, header.pmask

        for row in range(frame_height):
            y = row if is_top_down else frame_height - row - 1

            size = (width * color_depth + 7) // 8
            padded_row_size = (size + 3) // 4 * 4

            data = file.read(padded_row_size)

            for x in range(width):
                if color_depth <= 8:
                    color_index = self._extract_from_bytes(data, x, color_depth, ppb, pmask)
                    frame_buffer.pixel(x, y, color_index)
                else:
                    # For 24-bit color depth
                    offset = x * 3
                    b, g, r = data[offset:offset + 3]
                    color = (r << 16) | (g << 8) | b
                    frame_buffer.pixel(x, y, color)

    def _create_frame_buffer(self, width:int, height:int, color_format: int) -> tuple[FrameBuffer, bytearray]:
        """Create a frame buffer for storing pixel data of the image (or frame of a spritesheet)."""
        frame_size = width * height

        if color_format == framebuf.GS8:
            div = 1
        elif color_format == framebuf.GS4_HMSB:
            div = 2
        elif color_format == framebuf.GS2_HMSB:
            div = 4
        else:
            div = 1/1

        size = int(frame_size // div)
        byte_pixels = aligned_buffer(size)
        fbuffer = FrameBuffer(
            byte_pixels,
            width,
            height,
            color_format
        )
        return fbuffer, byte_pixels

    def _extract_from_bytes(self, data: bytes, index: int, color_depth, ppb, pmask) -> int:
        """
        Extract color index from byte data for indexed color modes.

        :param data: Byte data containing color information
        :param index: Index of the pixel in the image array
        :param color_depth: Color depth of the image
        :param ppb: Pixels per byte
        :param pmask: Pixel mask
        :return: Extracted color index
        """
        byte_index, pos_in_byte = divmod(index, ppb)
        shift = 8 - color_depth * (pos_in_byte + 1)

        return (data[byte_index] >> shift) & pmask

    def _as_image(self, meta, pixels, pixel_bytes, pixel_bytes_addr, palette, palette_bytes, color_depth, frames=None):
        new_image = create_image(
                meta.width,
                meta.height,
                pixels,
                pixel_bytes,
                pixel_bytes_addr,
                palette,
                palette_bytes,
                color_depth,
                frames)
        return new_image


    def _init(self):
        # Compat method
        pass

class ImageMeta():
    height = None
    planes_num = None
    color_depth = None
    color_format = None
    compression = None
    raw_size = None
    hres = None
    vres = None
    num_colors = None
    palette = None
    palette_bytes = None
    frames = None
    is_top_down = False
    ppb = None              # Pixels per byte (8 / color depth)
    pixel_mask = None       # To help with decoding binary data


class DynamicAttr(dict):
    def __getattr__(self, name):
        return self.get(name, None)

    def __setattr__(self, name, value):
        self[name] = value
