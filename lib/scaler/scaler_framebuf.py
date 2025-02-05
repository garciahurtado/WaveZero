import framebuf
from uarray import array

from profiler import Profiler as prof
from ssd1331_pio import SSD1331PIO
from uctypes import addressof

prof.enabled = False

class ScalerFramebuf():
    """
    Manages the various framebuffers used for rendering of scaled sprites.
    """
    """ Addtl width (beyond the full width of the screen) which the framebuf will use to fit large sprites.
        In order to support very high scales, increase this number to avoid early clipping """
    extra_width = extra_height = 32

    display:SSD1331PIO
    max_width = SSD1331PIO.WIDTH
    height = max_height = int(SSD1331PIO.HEIGHT)

    debug = False
    frame_width = 0
    frame_height = 0
    scratch_size = height * (max_width + extra_width) * 2
    scratch_bytes = bytearray(scratch_size)  # scratch framebuf, declared early on when more memory is available
    scratch_addr = addressof(scratch_bytes)
    scratch_buffer = None
    write_addrs_all = {}
    display_stride = 0

    def __init__(self, display: SSD1331PIO, mode=framebuf.RGB565):
        self.display = display

        self.frame_bytes = 0
        self.frame_sizes = [
            [4, 4],
            [8, 8],
            [16, 16],
            [32, 32],
            [64, self.max_width + self.extra_width]
        ]
        self.fill_color = 0x000000
        self.min_write_addr = addressof(self.scratch_bytes)

        self.init_buffers(mode)

    def init_buffers(self, mode):
        """ These temporary buffers are used for implementing transparency. All use the same underlying bytes, arranged
        as framebuffers of different dimensions in order to optimize for different sprite sizes """

        # 4x4
        self.scratch_buffer_4 = self.make_buffer(4, 4, mode)
        self.scratch_buffer_4.fill(self.fill_color)

        # 8x8
        self.scratch_buffer_8 = self.make_buffer(8, 8, mode)
        self.scratch_buffer_8.fill(self.fill_color)

        # 16x16
        self.scratch_buffer_16 = self.make_buffer(16, 16, mode)
        self.scratch_buffer_16.fill(self.fill_color)

        # 32x32
        self.scratch_buffer_32 = self.make_buffer(32, 32, mode)
        self.scratch_buffer_32.fill(self.fill_color)

        # 96x64
        self.scratch_buffer_64 = self.make_buffer(96, 64, mode)
        self.scratch_buffer_64.fill(self.fill_color)

        # fullscreen - extra 32 px on the width to accommodate really large sprites with -x
        self.scratch_buffer_full = self.make_buffer(self.max_width + self.extra_width, self.height, mode)
        self.scratch_buffer_full.fill(self.fill_color)

    def make_buffer(self, width, height, mode):
        new_buff = framebuf.FrameBuffer(self.scratch_bytes, width, height, mode)
        new_buff.fill(self.fill_color)

        return new_buff

    def select_buffer(self, scaled_width, scaled_height):
        prof.start_profile('scaler.select_buffer')

        """
        We implement transparency by first drawing the sprite on a scratch framebuffer.
        There are several sizes to optimize this process.

        Here we pick the right framebuffer based on the scaled sprite dimensions
        """
        max_dim = scaled_width if (scaled_width >= scaled_height) else scaled_height
        self.min_write_addr = addressof(self.scratch_bytes)

        if max_dim <= 4:
            self.scratch_buffer = self.scratch_buffer_4
            self.frame_width = self.frame_height = 4
        elif max_dim <= 8:
            self.scratch_buffer = self.scratch_buffer_8
            self.frame_width = self.frame_height = 8
        elif max_dim <= 16:
            self.scratch_buffer = self.scratch_buffer_16
            self.frame_width = self.frame_height = 16
        elif max_dim <= 32:
            self.scratch_buffer = self.scratch_buffer_32
            self.frame_width = self.frame_height = 32
        else:
            self.scratch_buffer = self.scratch_buffer_full
            self.frame_width = self.display.width + self.extra_width
            self.frame_height = self.display.height

        self.scratch_buffer.fill(self.fill_color)
        # self.display_stride = self.display_stride_cache[self.frame_width]
        self.display_stride = self.frame_width * 2
        # self.frame_bytes = self.frame_bytes_cache[self.frame_height]
        self.frame_bytes = self.display_stride * self.frame_height

        prof.end_profile('scaler.select_buffer')

        if self.debug:
            print(f"   INSIDE 'SELECT_BUFFER', WITH len(write_addrs_all): {len(self.write_addrs_all)} ")
            print(f"   FOR w/h: {scaled_width}, {scaled_height} a frame height of {self.frame_height}")
            print(f"   SELECTED STRIDE: {self.display_stride}")
            print(f"   FRAME BYTES: {self.frame_bytes}")

    def blit_with_alpha(self, x, y, alpha):
        """ Copy the sprite from the "scratch" framebuffer to the final one in the display.
         This is needed to implement transparency """

        """ Negative x and y have already been taking into account in interp config"""
        if alpha is None:
            self.display.write_framebuf.blit(self.scratch_buffer, x, y)
        else:
            self.display.write_framebuf.blit(self.scratch_buffer, x, y, alpha)

    def next_write_addr(self, curr_addr, stride):
        next_addr = curr_addr + stride
        return next_addr

