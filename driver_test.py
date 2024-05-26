import uctypes
from ssd_1331 import SSD1331
import micropython
import utime
import time
import random
import color_util as colors
from image_loader import ImageLoader

def test_ssd1331_driver():
    print("One second pause...")
    time.sleep(1)

    """
    mp_obj_t cspin = args[0];
    mp_obj_t dcpin = args[1];
    mp_obj_t rstpin = args[2];
    mp_obj_t mosi = args[3];
    mp_obj_t sclk = args[4];
    """
    # pin_cs = Pin(1, Pin.OUT)
    # pin_dc = Pin(5, Pin.OUT, value=0)
    # pin_rst = Pin(4, Pin.OUT, value=0)
    # pin_sda = Pin(3, Pin.OUT)
    # pin_sck = Pin(2, Pin.OUT)
    # -----------------------------
    # GPIO1 (SPI0 CS)       CS
    # GPIO2 (SPI0 SCK)      SCL
    # GPIO3 (SPI0 TX)       SDA
    # GPIO4 (or any)        RES
    # GPIO5 (or any)        DC

    # cpp
    # ----
    pin_cs = 1
    pin_dc = 5
    pin_rst = 4
    pin_mosi = 3
    pin_sck = 2

    color_list = [0xFFFFFF, 0xFF0000, 0x00FF00, 0x0000FF, 0x00FFFF, 0xFF00FF]

    screen = SSD1331(pin_cs, pin_dc, pin_rst, pin_mosi, pin_sck)
    screen.set_bitrate(80_000_000)
    screen.begin(False)
    screen.fill(0xFFFFFF)
    screen.pixel(40, 40, 0x000000)

    # Let's do some fun tests


    """ Full Screens ----------------------- """
    # screen_fills(screen, color_list)

    """ Lines ----------------------- """

    # draw_lines(screen, color_list)

    """ Rectangles ----------------------- """

    # random_rectangles(screen, color_list)

    """ End """

    """ Matrix -------------------------- """
    grid_matrix(screen)

    """ Dots -------------------------- """
    # dot_fill(screen)

    """ Image -------------------------- """
    start = utime.ticks_ms()

    display_image(screen)

    end = utime.ticks_ms()
    diff = end - start
    print("")
    print(f"--- Total time: {diff}ms ---")

    # print(f"Error code: {screen.getErrorCode()}")
    print(micropython.mem_info())

""" Draw functions -------------------------------------------- """

def screen_fills(screen, color_list):
    for j in range(10):
        for i in range(len(color_list)):
            screen.fill(color_list[i])
            utime.sleep_ms(10)

    screen.vline(10, 30, 30, 0xFFFFFF)


def draw_lines(screen, color_list):
    for i in range(100):
        for y in range(50):
            color = random.choice(color_list)
            color = colors.hex_to_565(color)
            rand1 = random.randint(-25, +25)
            rand2 = random.randint(-25, +25)
            screen.line(45 + rand1, 0, 45 + rand2, 64, color)

        utime.sleep_ms(7)
        screen.fill(0x000000)

def random_rectangles(screen, color_list):
    for i in range(50):
        for y in range(50):
            color1 = random.choice(color_list)
            color2 = random.choice(color_list)

            rand1 = random.randint(-35, +35)
            rand2 = random.randint(-35, +35)
            rand3 = random.randint(-35, +35)
            rand4 = random.randint(-35, +35)
            screen.fill_rect(45 + rand1, 30 + rand3, 45 + rand2, 30 + rand4, color1)

        # utime.sleep_ms(1)
        screen.fill(0x0000)

def grid_matrix(screen):
    dir = +1

    for t in range(10):
        for i in range(2, 30):
            if dir == -1:
                i = 30 - i

            offset_x = int(-96 / 2)
            offset_y = int(-64 / 2)

            color = colors.hex_to_565(0x0000FF)

            for x in range(offset_x, 96, i):
                screen.line(x, 0, x, 64, color)

            for y in range(offset_y, 64, i):
                screen.line(0, y, 96, y, color)

            utime.sleep_ms(2)
            screen.fill(0x000000)

        dir = dir * -1

def dot_fill(screen):
    width = 96
    height = 64

    screen.fill(0x1111)

    # Create a set to store used coordinates
    used_coords = set()

    # Keep track of the number of dots placed
    dots_placed = 0

    # Total number of pixels on the screen
    total_pixels = width * height

    while dots_placed < total_pixels:
        rand_x = random.randrange(0, width)
        rand_y = random.randrange(0, height)

        # Check if the coordinate has already been used
        # if (rand_x, rand_y) not in used_coords:
        color = colors.hex_to_565(0x000000)
        screen.pixel(int(rand_x), int(rand_y), color)
        # used_coords.add((rand_x, rand_y))
        # dots_placed += 1

def display_image(screen):
    loader = ImageLoader()
    img = loader.load_image('img/laser_tri.bmp')
    img_ptr = uctypes.addressof(img.pixels)
    palette_ptr = uctypes.addressof(img.palette_bytes)

    for i in range(1000):
        x = int(random.randrange(96))
        y = int(random.randrange(64))
        screen.blit_4bit(x, y, img_ptr, 20, 20, palette_ptr)
