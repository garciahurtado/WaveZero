from ssd1331_pio import SSD1331PIO
import color_util
import machine
from machine import Pin

test_colors = [
    [0x88ff00, 0xffee00, 0xdd66cc, 0xbb0000, 0xee0000, 0xff0088],
    [0x00bb66, 0x00dddd, 0x00aaff, 0x0077cc, 0x0000ff, 0x7700ff],
    [0xffffff, 0xd4d4d4, 0xababab, 0x7f7f7f, 0x545454, 0x2b2b2b]
]

def setup_display():
    screen_width = 96
    screen_height = 64

    pin_cs = Pin(1, Pin.OUT)
    pin_sck = Pin(2, Pin.OUT)
    pin_sda = Pin(3, Pin.OUT)
    pin_rst = Pin(4, Pin.OUT, value=0)
    pin_dc = Pin(5, Pin.OUT, value=0)

    spi = machine.SPI(0, baudrate=62_500_000, sck=pin_sck, mosi=pin_sda, miso=None)
    display = SSD1331PIO(
        spi,
        pin_cs,
        pin_dc,
        pin_rst,
        height=screen_height,
        width=screen_width,
        pin_sck=pin_sck,
        pin_sda=pin_sda)

    # display.set_clock_divide(8)
    display.start()
    return display

def test_pattern():
    global test_colors

    display = setup_display()

    width = 96
    height = 64
    display.rect(0, 0, width, height, 0xFFFF)

    sq_width = 15
    sq_height = 15

    y = + 2
    for palette in test_colors:
        x = 0 + 2

        for color in palette:
            color = color_util.int_to_bytes(color, format=color_util.BGR565)
            rgb = color_util.byte3_to_byte2(color)
            rgb_int = int.from_bytes(rgb, 'little')

            # print(f"RGB: {rgb_int:04x}")
            display.rect(x, y, sq_width, sq_height, rgb_int, rgb_int)
            x += sq_width

        y += sq_height

    display.show()

# test_pattern()
