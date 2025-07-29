import framebuf
from profiler import prof
from scaler.dma_chain import DMAChain
from screens.screen import PixelBounds
from ssd1331_pio import SSD1331PIO
from uctypes import addressof
from scaler.const import DEBUG, DEBUG_DISPLAY, DEBUG_DMA_ADDR
from utils import aligned_buffer
from profiler import timed

class ScalerFramebuf:
    """
    Manages the various framebuffers used for rendering of scaled sprites.
    """
    """ Addtl width (beyond the full width of the screen) which the framebuf will use to calculate bounds.
        In order to support very high scales, increase this number to avoid early clipping. This is only a number and 
         does not cost additional framebuffer memory since nothing is drawn here. """
    extra_width = extra_height = 64

    """ Because we can only read source pixels in whole rows, even when upscaling, if the upscaled pixel falls in the 
    middle of the bounds, we have to have an additional buffer to render the out of bounds portion. This margin should
    never need to be more than (max_scale / 2) """
    extra_subpx_top = extra_subpx_left = 32

    display:SSD1331PIO
    max_width = int(SSD1331PIO.WIDTH) + extra_subpx_left
    max_height = int(SSD1331PIO.HEIGHT) + extra_subpx_top

    frame_width = 0
    frame_height = 0
    scratch_size = max_width * max_height * 2
    aligned_b = aligned_buffer(scratch_size)
    scratch_bytes = aligned_b  # scratch framebuf, claiming a large chunk of memory early
    scratch_addr = addressof(aligned_b)
    scratch_buffer = None
    display_stride = 0

    scratch_buffer_4: framebuf
    scratch_buffer_8: framebuf
    scratch_buffer_16: framebuf
    scratch_buffer_24: framebuf
    scratch_buffer_32: framebuf
    scratch_buffer_48: framebuf
    scratch_buffer_64: framebuf
    scratch_buffer_full: framebuf

    def __init__(self, scaler, display: SSD1331PIO, mode=framebuf.RGB565):
        self.scaler = scaler
        self.display = display
        bounds_left = -(self.extra_width // 2)
        bounds_right = int(display.width) + (self.extra_width / 2)
        bounds_top = -(self.extra_height // 2)
        bounds_bottom = int(display.height) + (self.extra_height / 2)

        self.bounds = PixelBounds(
            bounds_left,
            bounds_right,
            bounds_top,
            bounds_bottom,
        )

        self.frame_bytes = 0
        self.frame_sizes = [
            [4, 4],
            [8, 8],
            [16, 16],
            [24, 24],
            [32, 32],
            [48, 48],
            [64, 64],
            [self.max_height, self.max_width]
        ]
        self.fill_color = 0x0
        self.min_write_addr = addressof(self.scratch_bytes)

        self.init_buffers(mode)

    def init_buffers(self, mode):
        """ These temporary buffers are used for implementing transparency. All use the same underlying bytes, arranged
        as framebuffers of different dimensions in order to optimize for different sprite sizes """

        # 4x4
        self.scratch_buffer_4 = self.make_buffer(4, 4, mode)

        # 8x8
        self.scratch_buffer_8 = self.make_buffer(8, 8, mode)

        # 16x16
        self.scratch_buffer_16 = self.make_buffer(16, 16, mode)

        # 24x24
        self.scratch_buffer_24 = self.make_buffer(24, 24, mode)

        # 32x32
        self.scratch_buffer_32 = self.make_buffer(32, 32, mode)

        # 48x48
        self.scratch_buffer_48 = self.make_buffer(48, 48, mode)

        # 64x64
        self.scratch_buffer_64 = self.make_buffer(64, 64, mode)

        # fullscreen - extra 32 px on the width to accommodate really large sprites with -x (or -y)
        self.scratch_buffer_full = self.make_buffer(self.max_width, self.max_height, mode)

    def make_buffer(self, width, height, mode):
        new_buff = framebuf.FrameBuffer(self.scratch_bytes, width, height, mode)
        new_buff.fill(self.fill_color)

        return new_buff

    #@timed
    def select_buffer(self, scaled_width, scaled_height):
        """
        We implement transparency by first drawing the sprite on a scratch framebuffer, and then using the first color
        index as alpha on the blitting to the final framebuf.
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
        elif max_dim <= 24:
            self.scratch_buffer = self.scratch_buffer_24
            self.frame_width = self.frame_height = 24
        elif max_dim <= 32:
            self.scratch_buffer = self.scratch_buffer_32
            self.frame_width = self.frame_height = 32
        elif max_dim <= 48:
            self.scratch_buffer = self.scratch_buffer_48
            self.frame_width = self.frame_height = 48
        elif max_dim <= 64:
            self.scratch_buffer = self.scratch_buffer_64
            self.frame_width = self.frame_height = 64
        else:
            """ Full Screen buffer """
            self.scratch_buffer = self.scratch_buffer_full
            self.frame_width = self.max_width
            self.frame_height = self.max_height

        self.scratch_buffer.fill(self.fill_color)
        self.display_stride = self.frame_width * 2
        self.frame_bytes = self.display_stride * self.frame_height

        dma:DMAChain = self.scaler.dma
        if DEBUG_DMA_ADDR:
            print(f"............................................")
            print(f":  In scaler_framebuf.select_buffer        :")
            print(f"............................................")
            print(f"    FINAL IMG w/h:              {scaled_width} x {scaled_height} ({scaled_width * scaled_height})")
            print(f"    SELECTED FB w/h:            {self.frame_width} x {self.frame_height}  ({self.frame_width * self.frame_height})")
            print(f"    SELECTED FB WRITE STRIDE:   {self.display_stride} bytes")
            print(f"    FRAME TOTAL BYTES:          {self.frame_bytes} bytes")

    def blit_with_alpha(self, x, y, alpha):
        """ Copy the sprite from the "scratch" framebuffer to the final one in the display.
         This is needed to implement transparency """

        if DEBUG_DISPLAY:
            print(f"--> BLITTING TO X/Y: {x},{y} <--")

        """ Negative x and y have already been taking into account in interp config"""
        if alpha is None:
            self.display.blit(self.scratch_buffer, x, y)
        else:
            self.display.blit(self.scratch_buffer, x, y, alpha)

    def next_write_addr(self, curr_addr, stride):
        next_addr = curr_addr + stride
        return next_addr
