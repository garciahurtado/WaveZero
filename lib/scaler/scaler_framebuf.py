import framebuf

from profiler import Profiler as prof
from ssd1331_pio import SSD1331PIO
from uctypes import addressof
from uarray import array

prof.enabled = False

class ScalerFramebuf():
    """
    Manages the various framebuffers used for rendering of scaled sprites.
    """
    display:SSD1331PIO
    max_width = SSD1331PIO.WIDTH
    height = SSD1331PIO.HEIGHT

    """ Addtl width (beyond the full width of the screen) which the framebuf will use to fit large sprites.
    In order to support very high scales, increase this number """
    extra_width = 32
    frame_width = 0
    frame_height = 0
    scratch_bytes = bytearray(height * (max_width + extra_width) * 2)  # scratch framebuf, declared early on when more memory is available
    scratch_addr = addressof(scratch_bytes)
    scratch_buffer = None
    write_addrs_all = {}
    write_addrs_curr = None # pointer to the current write addrs array

    alpha: None

    def __init__(self, display: SSD1331PIO, mode=framebuf.RGB565):
        self.frame_bytes = 0
        self.frame_bytes_cache = {}
        self.frame_sizes = [
            [4, 4],
            [8, 8],
            [16, 16],
            [32, 32],
            [64, self.max_width + self.extra_width]
        ]
        self.fill_color = 0x000000
        self.min_write_addr = addressof(self.scratch_bytes)

        self.display = display
        self.debug = True
        self.display_stride = 0
        self.display_stride_cache = {}
        self.init_buffers(mode)

        self.cache_addrs()

    def init_buffers(self, mode):
        """ These temporary buffers are used for implementing transparency. All use the same underlying bytes, arranged
        as framebuffers of different dimensions in order to optimize for different sprite sizes """

        # 2x2
        self.scratch_buffer_2 = self.make_buffer(2, 2, mode)
        self.scratch_buffer_2.fill(self.fill_color)

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
        stride = width * 2

        self.display_stride_cache[width] = stride
        self.frame_bytes_cache[height] = height * stride
        return new_buff

    def select_buffer(self, scaled_width, scaled_height):
        prof.start_profile('scaler.setup_buffers')

        """
        We implement transparency by first drawing the sprite on a scratch framebuffer.
        There are several sizes to optimize this process.

        Here we the right framebuffer based on the (scaled) sprite dimensions
        """
        max_dim = scaled_width if (scaled_width >= scaled_height) else scaled_height
        self.min_write_addr = addressof(self.scratch_bytes)

        if max_dim <= 4:
            self.scratch_buffer = self.scratch_buffer_4
            self.frame_width = self.frame_height = 4
            self.write_addrs_curr = self.write_addrs_all[4]
        elif max_dim <= 8:
            self.scratch_buffer = self.scratch_buffer_8
            self.frame_width = self.frame_height = 8
            self.write_addrs_curr = self.write_addrs_all[8]
        elif max_dim <= 16:
            self.scratch_buffer = self.scratch_buffer_16
            self.frame_width = self.frame_height = 16
            self.write_addrs_curr = self.write_addrs_all[16]
        elif max_dim <= 32:
            self.scratch_buffer = self.scratch_buffer_32
            self.frame_width = self.frame_height = 32
            self.write_addrs_curr = self.write_addrs_all[32]
        else:
            self.scratch_buffer = self.scratch_buffer_full
            self.frame_width = self.display.width + self.extra_width
            self.frame_height = self.display.height
            self.write_addrs_curr = self.write_addrs_all[64]

        self.scratch_buffer.fill(self.fill_color)
        self.display_stride = self.display_stride_cache[self.frame_width]
        # self.display_stride = self.frame_width * 2
        # self.frame_bytes = self.frame_bytes_cache[self.frame_height]
        self.frame_bytes = self.display_stride * self.frame_height

        prof.end_profile('scaler.setup_buffers')

        if self.debug:
            print(f"   INSIDE 'SELECT_BUFFER', WITH A self.write_addrs_now len of {len(self.write_addrs_curr)} ")
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

    def cache_addrs(self):
        """ Generate up to the maximum amount of write addresses (the height of the viewport) """

        for [height, width] in self.frame_sizes:
            write_base = self.min_write_addr

            display_stride = self.display_stride_cache[width]
            row_list = array("L", [0] * (height+1))

            curr_addr = write_base
            row_id = 0
            for row_id in range(height):
                row_list[row_id] = curr_addr
                curr_addr = self.next_write_addr(curr_addr, display_stride)

            """ Add null terminator """
            row_list[row_id+1] = 0x00000000

            self.write_addrs_all[height] = row_list

    def next_write_addr(self, curr_addr, stride):
        next_addr = curr_addr + stride
        return next_addr

