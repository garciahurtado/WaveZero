from micropython import const
import framebuf
import gc
import uctypes

from ssd1331_16bit import SSD1331

class DoubleBufferDriver():
    buffer0 = None
    buffer1 = None
    framebuf0: framebuf = None
    framebuf1: framebuf = None
    read_buffer = None
    write_buffer = None
    write_framebuf: framebuf = None
    read_framebuf: framebuf = None
    fps = None
    paused = True
    driver:SSD1331 = None

    HEIGHT: int = const(64)
    WIDTH: int = const(96)

    swap = 1 # flip flop to select buffer 0 or buffer 1

    def __init__(self, spi, pin_cs, pin_dc, pin_rs, pin_sck, pin_sda, height=HEIGHT, width=WIDTH):
        self.spi = spi
        self.pin_cs = pin_cs
        self.pin_dc = pin_dc
        self.pin_rs = pin_rs
        self.pin_sck = pin_sck
        self.pin_sda = pin_sda
        self.height = height
        self.width = width

        mode = framebuf.RGB565
        gc.collect()

        self.buffer0 = bytearray(self.height * self.width * 2)  # RGB565 is 2 bytes
        self.framebuf0 = framebuf.FrameBuffer(self.buffer0, self.width, self.height, mode)
        self.framebuf0.fill(0x0)

        self.buffer1 = bytearray(self.height * self.width * 2)  # RGB565 is 2 bytes
        self.framebuf1 = framebuf.FrameBuffer(self.buffer1, self.width, self.height, mode)
        self.framebuf1.fill(0x0)

        # Set starting alias to each buffer
        self.write_buffer = self.buffer0
        self.read_buffer = self.buffer1

        self.write_framebuf = self.framebuf0
        self.read_framebuf = self.framebuf1

    def start(self):
        return self.begin()

    def begin(self):
        self.driver = SSD1331(self.spi, self.pin_cs, self.pin_dc, self.pin_rs, height=self.height, width=self.width)
        self.driver.begin()
        # self.driver.set_color_depth(16)
        # self.driver.set_bitrate(250_000_000)
        # self.driver.change_mode(0) # Normal
        self.driver.xfill([0,0,0])

    def show(self):
        return self.finish_frame()

    def finish_frame(self):
        self.swap_buffers()

        if self.swap == 0:
            self.driver.blit_16(0, 0, self.width, self.height, uctypes.addressof(self.buffer0))
        else:
            self.driver.blit_16(0, 0, self.width, self.height, uctypes.addressof(self.buffer0))

    def swap_buffers(self):
        # self.read_buffer, self.write_buffer = self.write_buffer, self.read_buffer
        # self.read_addr, self.write_addr = self.write_addr, self.read_addr
        self.read_framebuf, self.write_framebuf = self.write_framebuf, self.read_framebuf
        self.swap = abs(self.swap - 1)

        # print(f" <<< SWAPPING BUFFERS >>> addr: {self.read_addr:016x}")

    def __getattr__(self, name):
        """ Proxy calls to framebuf and native C++ driver, so that the API is a little friendlier.
        First we look for methods of framebuf, and if one is not found, we look in the driver."""
        # if hasattr(self.write_framebuf, name):
        #     func = getattr(self.write_framebuf, name)
        #     return func
        # else:
        if hasattr(self.driver, name):
            func = getattr(self.driver, name)
            return func
        else:
            raise AttributeError(f"No method named '{name}' in driver")

