"""A small Python module for BMP image processing.

- Author: Quan Lin
- License: MIT

It supports BMP image of 1/2/4/8/24-bit colour depth.

- Loading supports compression method:
    - 0(BI_RGB, no compression)
    - 1(BI_RLE8, RLE 8-bit/pixel)
    - 2(BI_RLE4, RLE 4-bit/pixel)
- Saving only supports compression method 0(BI_RGB, no compression).

Examples
--------
>>> from microbmp import MicroBMP
>>> img_24b_2x2 = MicroBMP(2, 2, 24)  # Create a 2(width) by 2(height) 24-bit image.
>>> img_24b_2x2.palette  # 24-bit image has no palette.
>>> img_24b_2x2.pixels  # Pixels are arranged horizontally (top-down) in RGB order.
bytearray(b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00')
>>> img_24b_2x2[1, 1] = 255, 255, 255  # Access 1 pixel (R, G, B): img[x, y]
>>> img_24b_2x2[0, 1, 0] = 255  # Access 1 primary colour of 1 pixel (Red): img[x, y, c]
>>> img_24b_2x2[1, 0, 1] = 255  # (Green)
>>> img_24b_2x2[0, 0, 2] = 255  # (Blue)
>>> img_24b_2x2.save("img_24b_2x2.bmp")
70
>>> new_img_24b_2x2 = MicroBMP().load("img_24b_2x2.bmp")
>>> new_img_24b_2x2.palette
>>> new_img_24b_2x2.pixels
bytearray(b'\x00\x00\xff\x00\xff\x00\xff\x00\x00\xff\xff\xff')
>>> print(new_img_24b_2x2)
BMP image, RGB, 24-bit, 2x2 pixels, 70 bytes
>>> img_1b_3x2 = MicroBMP(3, 2, 1)  # Create a 3(width) by 2(height) 1-bit image.
>>> img_1b_3x2.palette  # Each colour is in the order of (R, G, B)
[bytearray(b'\x00\x00\x00'), bytearray(b'\xff\xff\xff')]
>>> img_1b_3x2.pixels  # Each bit stores the colour index in HLSB format.
bytearray(b'\x00')
>>> " ".join([f"{bin(byte)[2:]:0>8}" for byte in img_1b_3x2.pixels])
'00000000'
>>> img_1b_3x2[1, 0] = 1  # Access 1 pixel (index): img[x, y]
>>> img_1b_3x2[1, 1] = 1
>>> img_1b_3x2[2, 1] = 1
>>> img_1b_3x2.save("img_1b_3x2.bmp")
70
>>> new_img_1b_3x2 = MicroBMP().load("img_1b_3x2.bmp")
>>> new_img_1b_3x2.palette
[bytearray(b'\x00\x00\x00'), bytearray(b'\xff\xff\xff')]
>>> new_img_1b_3x2.pixels
bytearray(b'L')
>>> " ".join([f"{bin(b)[2:]:0>8}" for b in new_img_1b_3x2.pixels])
'01001100'
>>> print(new_img_1b_3x2)
BMP image, indexed, 1-bit, 3x2 pixels, 70 bytes
"""
import math
from struct import pack, unpack

import framebuf
from micropython import const

import color_util as colors
from framebuffer_palette import FramebufferPalette

# Project Version
__version__ = const("0.3.0")
__all__ = const("MicroBMP")

from indexed_image import create_image

class MicroBMP(object):
    """MicroBMP class.

    Parameters
    ----------
    width : int, optional
        The width of the image.
        (default is `None`)
    height : int, optional
        The height of the image.
        (default is `None`)
    depth : int, optional
        The colour depth of the image, must be in (1, 2, 4, 8, 24).
        (default is `None`)
    palette : list of bytearray, optional
        The colour palette of indexed images (colour depth of 1, 2, 4, or 8).
        Images of 24-bit colour depth has no palette (None).
        Each colour is represented by a 3-element bytearray in RGB order.
        (default is `None`)

    Attributes
    ----------
    BMP_size : int
        The number of bytes the image takes from the file system.
    width : int
        The width of the image.
    height : int
        The height of the image.
    color_depth : int
        The colour depth of the image.
    compression : int
        The compression method of the image read from the file system.
    palette : list of bytearray, optional
        The colour palette of indexed images (colour depth of 1, 2, 4, or 8).
        Images of 24-bit colour depth has no palette (None).
        Each colour is represented by a 3-element bytearray in RGB order.
    parray : bytearray
        The pixel array of the image.
        The first pixel is at the top-left corner of the image (origin).
        For 1/2/4/8-bit image, the pixels are colour indices arranged in HLSB format.
        So the high bits are at the leftmost.
        For 24-bit image, the pixels are arranged horizontally (top-down) in RGB order.

    Methods
    -------
    read_io(bf_io)
        Read image from BytesIO or FileIO.
    write_io(bf_io, force_40B_DIB=False):
        Write image to BytesIO or FileIO.
    load(file_path):
        Load image from BMP file.
    save(file_path, force_40B_DIB=False):
        Save image to BMP file.

    Notes
    -----
    - To get or set the colour index of a pixel of a 1/2/4/8-bit image : `img[x, y]`
    - To get or set the `r, g, b` values of a pixel of a 24-bit image : `img[x, y]`
    - To get or set a primary colour value of a pixel of a 24-bit image : `img[x, y, c]`
    """
    frame_width: int
    frame_height: int
    frames = []

    BMP_id = bytes(bytearray(2))
    BMP_size: int
    BMP_reserved1 = bytes(bytearray(2))
    BMP_reserved2 = bytes(bytearray(2))
    BMP_offset: int

    header_len: int
    width: int
    height: int
    planes_num: int
    color_depth: int
    compression: int
    raw_size: int
    hres: int
    vres: int
    num_colors: int
    extra = None

    def __init__(self, width=None, height=None, depth:int=8, palette=None, frame_width=0, frame_height=0):
        # BMP Header
        self.BMP_id = b"BM"
        self.BMP_size = None
        self.BMP_reserved1 = b"\x00\x00"
        self.BMP_reserved2 = b"\x00\x00"
        self.BMP_offset = None

        self.frame_width = frame_width
        self.frame_height = frame_height

        # DIB Header
        self.header_len = 40
        self.width = width
        self.height = height
        self.planes_num = 1
        self.color_depth = depth
        self.compression = 0
        self.raw_size = None
        self.hres = 2835  # 72 DPI * 39.3701 inches/metre.
        self.vres = 2835
        self.num_colors = 0

        self.palette: colors.FramebufferPalette = palette

        # Pixel array
        self.pixels = None
        self.frames = []

        self.ppb = None  # Number of pixels per byte for depth <= 8.
        self.pmask = None  # Pixel Mask
        self.row_size = None
        self.padded_row_size = None

        self.initialised = False
        self._init()

    def __getitem__(self, key):
        assert self.initialised, "Image not initialised!"
        assert key[0] < self.width and key[1] < self.height, "Out of image boundary!"

        # Pixels are arranged in HLSB format with high bits being the leftmost
        pindex = key[1] * self.width + key[0]  # Pixel index
        if self.color_depth <= 8:
            return self._extract_from_bytes(self.pixels, pindex)
        else:
            pindex *= 3
            if (len(key) > 2) and (key[2] in (0, 1, 2)):
                return self.pixels[pindex + key[2]]
            else:
                return (
                    self.pixels[pindex],
                    self.pixels[pindex + 1],
                    self.pixels[pindex + 2],
                )

    def __setitem__(self, key, color):
        assert self.initialised, "Image not initialised!"
        assert key[0] < self.width and key[1] < self.height, "Out of image boundary!"

        self.pixels.pixel(key[0],key[1], color)

    def __str__(self):
        if not self.initialised:
            return repr(self)

        return "BMP image, {}, {}-bit, {}x{} pixels, {} bytes".format(
            "indexed" if self.color_depth <= 8 else "RGB",
            self.color_depth,
            self.width,
            self.height,
            self.BMP_size,
        )

    def _init(self):
        if None in (self.width, self.height, self.color_depth):
            self.initialised = False
            return self.initialised

        assert self.BMP_id == b"BM", "BMP id ({}) must be b'BM'!".format(self.BMP_id)
        assert (
            len(self.BMP_reserved1) == 2 and len(self.BMP_reserved2) == 2
        ), "Length of BMP reserved fields ({}+{}) must be 2+2!".format(
            len(self.BMP_reserved1), len(self.BMP_reserved2)
        )
        assert self.planes_num == 1, "DIB planes number ({}) must be 1!".format(
            self.planes_num
        )
        assert self.color_depth in (
            1,
            2,
            4,
            8,
            24,
        ), "Colour depth ({}) must be in (1, 2, 4, 8, 24)!".format(self.color_depth)
        assert (
                self.compression == 0
                or (self.color_depth == 8 and self.compression == 1)
                or (self.color_depth == 4 and self.compression == 2)
        ), "Colour depth + compression ({}+{}) must be X+0/8+1/4+2!".format(
            self.color_depth, self.compression
        )

        self.pixels = None
        self.frames = []
        self.num_colors = 0

        if self.color_depth <= 8:
            self.ppb = 8 // self.color_depth
            self.pmask = 0xFF >> (8 - self.color_depth)
        else:
            self.ppb = None
            self.pmask = None
            self.num_colors = 0
            self.palette = None

        if self.pixels is None:
            # Initialize the pixels array or pixel frames to zero
            if self.color_depth > 8:
                print("Only 8 BPP color depth supported")
                exit()

        print(f"Color depth: {self.color_depth} / ppb: {self.ppb}")
        plt_size: int = self.num_colors * 4
        self.BMP_offset = 14 + self.header_len + plt_size
        self.row_size = self._size_from_width(self.width)
        self.padded_row_size = self._padded_size_from_size(self.row_size)
        if self.compression == 0:
            self.raw_size = self.padded_row_size * self.height
            self.BMP_size = self.BMP_offset + self.raw_size

        self.initialised = True
        return self.initialised

    def _size_from_width(self, width):
        return (width * self.color_depth + 7) // 8

    def _padded_size_from_size(self, size):
        return (size + 3) // 4 * 4

    def _extract_from_bytes(self, data, index):
        # print(f"data size: {len(data)} / idx:{index} / ppb: {self.ppb}")
        # One formula that suits all: 1/2/4/8-bit colour depth.
        byte_index, pos_in_byte = divmod(index, self.ppb)
        shift = 8 - self.color_depth * (pos_in_byte + 1)
        return (data[byte_index] >> shift) & self.pmask

    def _fill_in_bytes(self, data, index, value):
        # One formula that suits all: 1/2/4/8-bit colour depth.
        byte_index, pos_in_byte = divmod(index, self.ppb)
        shift = 8 - self.color_depth * (pos_in_byte + 1)
        value &= self.pmask
        data[byte_index] = (data[byte_index] & ~(self.pmask << shift)) + (
            value << shift
        )

    def _decode_rle(self, bf_io):
        # Only bottom-up bitmap can be compressed.
        x: int
        y: int
        x, y = 0, self.height - 1

        while True:
            data: bytes = bf_io.read(2)
            if data[0] == 0:
                if data[1] == 0:
                    x, y = 0, y - 1
                elif data[1] == 1:
                    return
                elif data[1] == 2:
                    data = bf_io.read(2)
                    x, y = x + data[0], y - data[1]
                else:
                    num_of_pixels = data[1]
                    num_to_read = (self._size_from_width(num_of_pixels) + 1) // 2 * 2
                    data = bf_io.read(num_to_read)
                    for i in range(num_of_pixels):
                        self[x, y] = self._extract_from_bytes(data, i)
                        x += 1
            else:
                for i in range(data[0]):
                    self[x, y] = self._extract_from_bytes(bytes([data[1]]), i % self.ppb)
                    x += 1

    def read_io(self, bf_io):
        """Read image from BytesIO or FileIO.

        Parameters
        ----------
        bf_io : BytesIO or FileIO
            The input BMP image BytesIO or FileIO.

        Returns
        -------
        MicroBMP
            self.
        """
        # BMP Header
        data = bf_io.read(14)
        self.BMP_id = data[0:2]
        self.BMP_size = unpack("<I", data[2:6])[0]
        self.BMP_reserved1 = data[6:8]
        self.BMP_reserved2 = data[8:10]
        self.BMP_offset = unpack("<I", data[10:14])[0]

        # DIB Header
        data = bf_io.read(4)
        self.header_len = unpack("<I", data[0:4])[0]
        data = bf_io.read(self.header_len - 4)
        (
            self.width,
            self.height,
            self.planes_num,
            self.color_depth,
            self.compression,
            self.raw_size,
            self.hres,
            self.vres,
        ) = unpack("<iiHHIIii", data[0:28])

        if not self.frame_height or not self.frame_width:
            self.frame_width = self.width
            self.frame_height = self.height

        DIB_plt_num_info = unpack("<I", data[28:32])[0]
        DIB_plt_important_num_info = unpack("<I", data[32:36])[0]

        """ Create and populate palette """
        if self.color_depth <= 8:
            if DIB_plt_num_info == 0:
                self.num_colors = 2 ** self.color_depth
            else:
                self.num_colors = DIB_plt_num_info
            print(f"Num colors: {self.num_colors}")
            # self.palette = [None for i in range(self.num_colors)]

            self.palette_bytes = bytearray(self.num_colors*2)
            self.palette = FramebufferPalette(self.palette_bytes)

            for color_idx in range(self.num_colors):
                data = bf_io.read(4)

                # RGB format, but extract the bytes as little endian
                color_bytes = colors.byte3_to_byte2([data[0], data[1], data[2]])
                color = int.from_bytes(color_bytes, "little")
                self.palette.set_bytes(color_idx, color)

        # In case self.DIB_h < 0 for top-down format.
        if self.height < 0:
            self.height = -self.height
            is_top_down = True
        else:
            is_top_down = False

        self.pixels = None
        assert self._init(), "Failed to initialize the image!"

        """ Create and populate pixel frames """
        if self.compression == 0:
            # BI_RGB
            num_frames = math.floor(self.height / self.frame_height)
            frame_size = self.frame_width * self.frame_height

            print(f"Creating {num_frames} frames of {self.frame_width}x{self.frame_height} ")

            if self.color_depth == 8:
                format = framebuf.GS8
            elif self.color_depth == 4:
                format = framebuf.GS4_HMSB
                frame_size = int(frame_size / 2)
            else:
                format = framebuf.GS2_HMSB
                frame_size = int(frame_size / 4)

            for frame_idx in range(num_frames):
                byte_pixels = bytearray(frame_size)
                # print(f"Creating frame of size {frame_size} format: {format} {framebuf.GS4_HMSB} ({self.frame_width}x{self.frame_height})")
                buffer = framebuf.FrameBuffer(
                    byte_pixels,
                    self.frame_width,
                    self.frame_height,
                    format
                )

                frame = create_image(
                    self.frame_width,
                    self.frame_height,
                    buffer,
                    memoryview(byte_pixels),
                    self.palette,
                    memoryview(self.palette_bytes),
                    self.color_depth)

                for row in range(0, self.frame_height):
                    data = bf_io.read(self.padded_row_size)
                    y = row if is_top_down else self.frame_height - row - 1

                    for x in range(self.frame_width):
                        x = x if is_top_down else self.frame_width - x - 1
                        if self.color_depth <= 8:
                            buffer.pixel(x, y, self._extract_from_bytes(data, x))
                        else:
                            raise Exception("Only color depth <= 8bit is supported")

                self.frames.append(frame)

            if not is_top_down:
                self.frames.reverse()


            self.pixels = self.frames[0]
            self.palette = self.pixels.palette
        else:
            # BI_RLE8 or BI_RLE4
            self._decode_rle(bf_io)

        return self

    def write_io(self, bf_io, force_40B_DIB=False):
        """Write image to BytesIO or FileIO.

        Parameters
        ----------
        bf_io : BytesIO or FileIO
            The output BMP image BytesIO or FileIO.
        force_40B_DIB : bool, optional
            Force the size of DIB to be 40 bytes or not.
            (default is `False`)

        Returns
        -------
        int
            The number of bytes written to the io.
        """
        if force_40B_DIB:
            self.header_len = 40

        # Only uncompressed image is supported to write.
        self.compression = 0

        assert self._init(), "Failed to initialize the image!"

        # BMP Header
        bf_io.write(self.BMP_id)
        bf_io.write(pack("<I", self.BMP_size))
        bf_io.write(self.BMP_reserved1)
        bf_io.write(self.BMP_reserved2)
        bf_io.write(pack("<I", self.BMP_offset))
        # DIB Header
        bf_io.write(
            pack(
                "<IiiHHIIiiII",
                self.header_len,
                self.width,
                self.height,
                self.planes_num,
                self.color_depth,
                self.compression,
                self.raw_size,
                self.hres,
                self.vres,
                self.num_colors,
                self.num_colors,
            )
        )

        # Palette
        if self.color_depth <= 8:
            for colour in self.palette:
                bf_io.write(bytes([colour[2], colour[1], colour[0], 0]))

        # Pixels
        for h in range(self.height):
            # BMP last row comes first.
            y = self.height - h - 1
            if self.color_depth <= 8:
                d = 0
                for x in range(self.width):
                    self[x, y] %= self.num_colors
                    # One formula that suits all: 1/2/4/8-bit colour depth.
                    d = (d << (self.color_depth % 8)) + self[x, y]
                    if x % self.ppb == self.ppb - 1:
                        # Got a whole byte.
                        bf_io.write(bytes([d]))
                        d = 0
                if x % self.ppb != self.ppb - 1:
                    # Last byte if width does not fit in whole bytes.
                    d <<= (
                        8
                        - self.color_depth
                        - (x % self.ppb) * (2 ** (self.color_depth - 1))
                    )
                    bf_io.write(bytes([d]))
                    d = 0
            else:
                for x in range(self.width):
                    r, g, b = self[x, y]
                    bf_io.write(bytes([b, g, r]))
            # Pad row to multiple of 4 bytes with 0x00.
            bf_io.write(b"\x00" * (self.padded_row_size - self.row_size))

        num_of_bytes = bf_io.tell()
        return num_of_bytes

    def load(self, file_path):
        """Load image from BMP file.

        Parameters
        ----------
        file_path : str
            Input file full path.

        Returns
        -------
        MicroBMP
            self.
        """
        with open(file_path, "rb") as file:
            self.read_io(file)
        return self

    def save(self, file_path, force_40B_DIB=False):
        """Save image to BMP file.

        Parameters
        ----------
        file_path : str
            Output file full path.
        force_40B_DIB : bool, optional
            Force the size of DIB to be 40 bytes or not.
            (default is `False`)

        Returns
        -------
        int
            The number of bytes written to the file.
        """
        with open(file_path, "wb") as file:
            num_of_bytes = self.write_io(file, force_40B_DIB)
        return num_of_bytes
    
    def rgb(self):
        """Returns a list of RGB pixels for indexed images (<=8bit)"""
        index = 0
        while index < len(self.pixels):
            color_idx = self.pixels[index]
            color = self.palette[color_idx]
            yield color[0], color[1], color[2]
            index = index + 1

    
    def rgb565(self):
        """
        Converts a list of RGB pixels into an RGB565 encoded byte array.
        

        Returns:
            bytes: An RGB565 encoded byte array.
        """
        num_pixels = len(self.pixels)
        array_size = num_pixels * 2
        # print(f"Array size: {array_size} / palette size: {len(self.palette)}")
        rgb565_buffer = bytearray(array_size)  # Pre-allocate the buffer
        
        index = 0
        while index < len(self.pixels):
            color_idx = self.pixels[index]
            (r, g, b) = self.palette[color_idx]
            
            # Convert RGB values to 5-6-5 bit format
            r5 = (r >> 3) & 0b11111
            g6 = (g >> 2) & 0b111111
            b5 = (b >> 3) & 0b11111
            
            # Pack the 5-6-5 bit values into a 16-bit integer
            rgb565 = (r5 << 11) | (g6 << 5) | b5
            
            # Write the 16-bit integer to the buffer
            rgb565_buffer[index*2] = (rgb565 >> 8) & 0xFF
            rgb565_buffer[index*2 + 1] = rgb565 & 0xFF
            
            index += 1
        
        return rgb565_buffer