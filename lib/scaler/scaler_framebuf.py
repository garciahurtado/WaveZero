import framebuf

from profiler import Profiler as prof
from ssd1331_pio import SSD1331PIO
from uctypes import addressof

prof.enabled = False

class ScalerFramebuf():
    """
    Manages the various framebuffers used for rendering of scaled sprites.
    """
    display:SSD1331PIO
    WIDTH = SSD1331PIO.WIDTH
    HEIGHT = SSD1331PIO.HEIGHT
    EXTRA_WIDTH_BIG = 16 # Addtl width (beyond the full width of the screen) which the framebuf will use to fit large sprites
    frame_width = 0
    frame_height = 0
    scratch_bytes = bytearray(HEIGHT * (WIDTH + EXTRA_WIDTH_BIG) * 2)  # scratch framebuf, declared early on when more memory is available
    scratch_addr = addressof(scratch_bytes)
    scratch_buffer = None

    alpha: None

    def __init__(self, display: SSD1331PIO, mode=framebuf.RGB565):
        self.display = display
        self.debug = False
        self.frame_bytes = 0
        self.frame_bytes_cache = {}
        self.display_stride_cache = {}
        self.fill_color = 0x0

        self.init_buffers(mode)

        self.min_write_addr = addressof(self.scratch_bytes)
        self.display_stride = 0

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

        # 96x32
        self.scratch_buffer_64 = self.make_buffer(96, 64, mode)
        self.scratch_buffer_64.fill(self.fill_color)

        # fullscreen - extra 32 px on the width to accommodate really large sprites with -x
        self.scratch_buffer_full = self.make_buffer(self.WIDTH + self.EXTRA_WIDTH_BIG, self.HEIGHT, mode)
        self.scratch_buffer_full.fill(self.fill_color)

    def make_buffer(self, width, height, mode):
        new_buff = framebuf.FrameBuffer(self.scratch_bytes, width, height, mode)
        new_buff.fill(self.fill_color)
        stride = width * 2
        self.display_stride_cache[width] = stride
        self.frame_bytes_cache[width] = height * stride
        return new_buff
        
    def select_buffer(self, scaled_width, scaled_height):
        prof.start_profile('scaler.setup_buffers')

        """
        We implement transparency by first drawing the sprite on a scratch framebuffer.
        There are several sizes to optimize this process.

        Here we the right framebuffer based on the (scaled) sprite dimensions
        """
        max_dim = scaled_width if scaled_width >= scaled_height else scaled_height

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
            self.frame_width = self.display.width + self.EXTRA_WIDTH_BIG
            self.frame_height = self.display.height

        self.scratch_buffer.fill(self.fill_color)
        self.display_stride = self.display_stride_cache[self.frame_width]
        self.frame_bytes = self.frame_bytes_cache[self.frame_width]

        if self.debug:
            print(f"* Will use a ({self.frame_width}x{self.frame_height}) Canvas - w/h")

        prof.end_profile('scaler.setup_buffers')

    def blit_with_alpha(self, x, y, alpha):
        """ Copy the sprite from the "scratch" framebuffer to the final one in the display.
         This is needed to implement transparency """
        prof.start_profile('scaler.blit_with_alpha')

        """ Negative x and y have already been taking into account in interp config"""

        if self.debug:
            width = self.display.width
            height = self.display.height
            print(f" ~ BLITTING [{width}x{height}] FRAMEBUF TO x/y: {x}/{y} ")
            print(f" ~ ALPHA IS {alpha} of Type {type(alpha)}")

        if alpha is None:
            self.display.write_framebuf.blit(self.scratch_buffer, x, y)
        else:
            self.display.write_framebuf.blit(self.scratch_buffer, x, y, alpha)

        prof.end_profile('scaler.blit_with_alpha')

