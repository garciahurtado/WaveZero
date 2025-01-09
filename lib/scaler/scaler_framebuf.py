import framebuf

from profiler import Profiler as prof
from ssd1331_pio import SSD1331PIO
import uctypes

prof.enabled = False

class ScalerFramebuf():
    display:SSD1331PIO
    WIDTH = SSD1331PIO.WIDTH
    HEIGHT = SSD1331PIO.HEIGHT
    EXTRA_WIDTH_BIG = 16
    frame_width = 0
    frame_height = 0
    trans_bytes = bytearray(HEIGHT * (WIDTH + EXTRA_WIDTH_BIG) * 2)  # scratch framebuf, declared early on when more memory is available
    trans_addr = uctypes.addressof(trans_bytes)
    trans_framebuf = None

    alpha: None

    def __init__(self, display: SSD1331PIO, mode=framebuf.RGB565):
        self.display = display
        self.debug = False

        self.init_buffers(mode)

    def init_buffers(self, mode):
        """ These temporary buffers are used for implementing transparency. All use the same underlying bytes, arranged
        as framebuffers of different dimensions in order to optimize for different sprite sizes """

        # 2x2
        self.trans_framebuf_2 = framebuf.FrameBuffer(self.trans_bytes, 2, 2, mode)
        self.trans_framebuf_2.fill(0x0)

        # 4x4
        self.trans_framebuf_4 = framebuf.FrameBuffer(self.trans_bytes, 4, 4, mode)
        self.trans_framebuf_4.fill(0x0)

        # 8x8
        self.trans_framebuf_8 = framebuf.FrameBuffer(self.trans_bytes, 8, 8, mode)
        self.trans_framebuf_8.fill(0x0)

        # 16x16
        self.trans_framebuf_16 = framebuf.FrameBuffer(self.trans_bytes, 16, 16, mode)
        self.trans_framebuf_16.fill(0x0)

        # 32x32
        self.trans_framebuf_32 = framebuf.FrameBuffer(self.trans_bytes, 32, 32, mode)
        self.trans_framebuf_32.fill(0x0)

        # 96x32
        self.trans_framebuf_64 = framebuf.FrameBuffer(self.trans_bytes, 96, 64, mode)
        self.trans_framebuf_64.fill(0x0)

        # fullscreen - extra 32 px on the width to accomodate really large sprites with -x
        self.trans_framebuf_full = framebuf.FrameBuffer(self.trans_bytes, self.WIDTH + self.EXTRA_WIDTH_BIG, self.HEIGHT, mode)
        self.trans_framebuf_full.fill(0x0)

    def select_buffer(self, scaled_width, scaled_height):
        prof.start_profile('scaler.setup_buffers')

        """
        We implement transparency by first drawing the sprite on a scratch framebuffer.
        There are several sizes to optimize this process.

        Here we the right framebuffer based on the (scaled) sprite dimensions
        """
        max_dim = scaled_width if scaled_width >= scaled_height else scaled_height

        if max_dim <= 4:
            self.trans_framebuf = self.trans_framebuf_2
            self.frame_width = self.frame_width = 2
        elif max_dim <= 4:
            self.trans_framebuf = self.trans_framebuf_4
            self.frame_width = self.frame_width = 4
        elif max_dim <= 8:
            self.trans_framebuf = self.trans_framebuf_8
            self.frame_width = self.frame_width = 8
        elif max_dim <= 16:
            self.trans_framebuf = self.trans_framebuf_16
            self.frame_width = self.frame_width = 16
        elif max_dim <= 32:
            self.trans_framebuf = self.trans_framebuf_32
            self.frame_width = self.frame_width = 32
        elif False and max_dim <= 64:           # doesn't work well and is basically same as full screen
            self.trans_framebuf = self.trans_framebuf_64
            self.frame_width = 64
            self.frame_height = 64
        else:
            self.trans_framebuf = self.trans_framebuf_full
            self.frame_width = self.display.width + self.EXTRA_WIDTH_BIG
            self.frame_height = self.display.height

        self.trans_framebuf.fill(0x000000)
        self.display_stride = self.frame_width * 2

        if self.debug:
            print(f"* Will use a ({self.frame_width}x{self.frame_height}) Canvas - w/h")

        prof.end_profile('scaler.setup_buffers')
        pass

    def blit_with_alpha(self, x, y, alpha):
        """ Copy the sprite from the "scratch" framebuffer to the final one in the display.
         This is needed to implement transparency """
        prof.start_profile('scaler.blit_with_alpha')
        disp = self.display

        """ Negative x and y have already been taking into account in interp config"""
        # if y < 0:
        #     y = 0

        # if x < 0: # WILL HAVE TO BE ENABLED EVENTUALLY
        #     x = 0

        if self.debug:
            width = disp.width
            height = disp.height
            print(f" ~ BLITTING [{width}x{height}] FRAMEBUF TO x/y: {x}/{y} ")
            print(f" ~ ALPHA IS {alpha} of Type {type(alpha)}")

        if alpha is None:
            disp.write_framebuf.blit(self.trans_framebuf, x, y)
        else:
            disp.write_framebuf.blit(self.trans_framebuf, x, y, int(alpha))

        prof.end_profile('scaler.blit_with_alpha')

