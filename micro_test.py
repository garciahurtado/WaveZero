from microbmp import MicroBMP as bmp
import machine
from machine import Pin
import framebuf
import utime
from lib.ssd1331_16bit import SSD1331 as SSD
from road_grid import RoadGrid
from perspective_sprite import PerspectiveSprite
from perspective_camera import PerspectiveCamera


# Set the window size
width = 96
height = 64

# Set the initial line positions and speeds
lines = []
num_lines = 10
for i in range(num_lines):
    y = i * (height // num_lines)
    speed = (i + 1) * 0.5
    lines.append([y, speed])

def setup_display():
    # Pin layout for SSD1331 64x48 OLED display on Raspberry Pi Pico (SPI0)
    # GPIO1 (SPI0 CS)       CS
    # GPIO2 (SPI0 SCK)      SCL
    # GPIO3 (SPI0 TX)       SDA
    # GPIO4 (or any)        RES
    # GPIO5 (or any)        DC
    
    pin_cs = Pin(1, Pin.OUT)
    pin_sck = Pin(2, Pin.OUT)
    pin_sda = Pin(3, Pin.OUT)
    pin_rst = Pin(4, Pin.OUT, value=0)
    pin_dc = Pin(5, Pin.OUT, value=0)

    spi = machine.SPI(0, baudrate=24_000_000, sck=pin_sck, mosi=pin_sda, miso=None)
    ssd = SSD(spi, pin_cs, pin_dc, pin_rst, height=64, width=96)  # Create a display instance
    return ssd

def main():
    print("Display Start...")

    screen = setup_display()

    # Set the colors
    BLACK = screen.rgb(0,0,0)
    WHITE = screen.rgb(255,255,255)

    #draw_color_test(screen, WHITE)

    # Game loop
    running = True

    print("Display Initialized")

    # Initialize camera and road grid

    # Camera
    horiz_y = 16
    camera = PerspectiveCamera(width, height, vp_x=round(width / 2), vp_y=horiz_y)

    # Set up vertical and horizontal 3D lines
    grid = RoadGrid(camera, screen)

    sun = create_sun()
    sun_image = {'data':sun.rgb565(), 'width': sun.DIB_w, 'height':sun.DIB_h}

    while running:
        # Clear the screen
        screen.fill(BLACK)
        grid.draw_vert_lines()
        grid.draw_horiz_lines()
        grid.update_sway()
        draw_sun(sun_image, screen)
        
        # Update the display
        screen.show()
        
        # Delay to control the frame rate
        utime.sleep(1 / 120)

def draw_color_test(screen, white):
    screen.fill(white)
    screen.show()

    # Operate in landscape mode
    x = 0
    for y in range(96):
        screen.line(y, x, y, x+20, screen.rgb(round(255*y/96), 0, 0))
    x += 20
    for y in range(96):
        screen.line(y, x, y, x+20, screen.rgb(0, round(255*y/96), 0))
    x += 20
    for y in range(96):
        screen.line(y, x, y, x+20, screen.rgb(0, 0, round(255*y/96)))
    screen.show()

    utime.sleep(0.5)

    screen.fill(white)
    screen.show()

def draw_test_lines(screen, white):
    # Update and draw the lines
    for i in range(num_lines):
        lines[i][0] += lines[i][1]  # Update the line position
        if lines[i][0] > height:
            lines[i][0] = 0  # Reset the line position when it reaches the bottom
        
        # Calculate the line length based on perspective
        line_length = width * (1 - lines[i][0] / height)
        
        # Calculate the line position to center it horizontally
        line_pos = (width - line_length) // 2
        
        # Draw the line
        screen.hline(int(line_pos), int(lines[i][0]), int(line_length), white)

def create_sun():
    
    # Load the PNG image
    # with open('/img/sunset.bmp', 'rb') as f:
    #     png_data = f.read()
    filename = '/img/sunset_2.bmp'

    image = bmp().load(filename)

    return image


def draw_sun(image, screen):
    fb = framebuf.FrameBuffer(bytearray(image['data']), image['width'], image['height'], framebuf.RGB565)

    # Display the image on the screen
    screen.blit(fb, 39, 5)
    return

if __name__ == "__main__":
    print("Doing main...")
    main()

