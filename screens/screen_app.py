import framebuf
from machine import Pin
from display_init import get_display

class ScreenApp:
    display: framebuf.FrameBuffer
    screens = []
    display: None
    screen_width: int = 0
    screen_height: int = 0
    #
    # pin_cs = Pin(1, Pin.OUT)
    # pin_sck = Pin(2, Pin.OUT)
    # pin_sda = Pin(3, Pin.OUT)
    # pin_rst = Pin(4, Pin.OUT, value=0)
    # pin_dc = Pin(5, Pin.OUT, value=0)

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.display = get_display()

    def load_screen(self, screen: type):
        screen.app = self
        self.screens.append(screen)

    def run(self):
        if not self.screens:
            raise AssertionError("No screens registered with app!")

        for screen in self.screens:
            screen.run()

    # def setup_native_display(self, pin_cs, pin_dc, pin_rst, pin_sda, pin_sck):
    #     self.display = Driver(pin_cs, pin_dc, pin_rst, pin_sda, pin_sck)
    #     self.display.begin(False)
    #     return self.display


