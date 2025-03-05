import gc
import math
import random

import framebuf

from colors.framebuffer_palette import FramebufferPalette
from fx.scanline_fade import ScanlineFade
from sprites.spritesheet import Spritesheet
from colors import color_util as colors


class Crash():
    x = 0
    y = 0
    particles = []
    explode_sprite: Spritesheet
    palette: FramebufferPalette
    alpha_color: int
    display: framebuf.FrameBuffer
    stage_width = 0
    stage_height = 0

    def __init__(self, display, sprite):
        self.display = display
        self.explode_sprite = sprite
        self.create_particles()
        self.stage_width = self.display.width
        self.stage_height = self.display.height

        gc.collect()
        print(f"Free memory before creating FX framebuf  {gc.mem_free():,} bytes")

        # Create a 4-bit stage the size of the display where we will draw the FX
        size = self.display.width * self.display.height // 2
        print(f"Stage size: {size:0} bytes")

        self.stage = framebuf.FrameBuffer(bytearray(size), self.display.width, self.display.height, framebuf.GS2_HMSB)

    def create_particles(self):
        gc.collect()

        bitmap = self.explode_sprite.image.pixels
        # self.palette = self.explode_sprite.palette.clone()
        # self.palette.set_rgb(1, [104, 250, 255])
        # self.palette.set_rgb(2, [90, 247, 255])
        # self.palette.set_rgb(3, [52, 235, 198])

        self.palette = self.create_palette()

        # Get the center of the bitmap
        self.center_x = self.explode_sprite.frame_width // 2
        self.center_y = self.explode_sprite.frame_height // 2

        # Create a list to store particle data
        particles = []
        new_particle = []

        # Get the particle data from the bitmap
        for x in range(0, 25, 3):
            for y in range(0, 42, 3):
                if bitmap.pixel(x, y) != 0 and round(random.random() + 0.6):
                    # Calculate the distance from the center
                    distance = math.sqrt((x - self.center_x) ** 2 + (y - self.center_y) ** 2)
                    distance = abs(distance)
                    if distance < 3:
                        distance == 3

                    if distance > 10:
                        distance == 10

                    # Calculate the angle from the center
                    angle = math.atan2(y - self.center_y, x - self.center_x)

                    # Center the particles on the source sprite
                    new_x = int(x + self.explode_sprite.x)
                    new_y = int(y + self.explode_sprite.y)

                    # Store the particle data as a tuple
                    new_particle = [new_x, new_y, distance, angle]
                    particles.append(new_particle)

        self.particles = particles

        return particles

    def create_palette(self):
        colors_hex = [  0x000000, # alpha color
                        0xFFFFFF,
                        0xFDFF30,
                        0xFD7006,
                        0xC32404,
                        0x8C0B05,
                        0x380000,
                        0x0D0909]

        #colors_rgb = [colors.hex_to_rgb(color) for color in colors_hex]
        palette = FramebufferPalette(8)
        for i, color in enumerate(colors_hex):
            palette.set_rgb(i, colors.hex_to_rgb(color))

        self.alpha_color = colors.hex_to_565(0x000000)

        return palette

    def anim_particles(self):
        particles = self.particles
        speed = 4
        center_x = self.center_x + self.explode_sprite.x
        center_y = self.center_y + self.explode_sprite.y
        rand_range = 0.6
        color_offset = 0

        # Animate the particles
        for i in range(50): # number of frames for this animation

            # Create a moving window for picking random colors from the palette
            color_offset = ((i-5) // 55) * 4
            if color_offset > 3:
                color_offset = 3
            elif color_offset < 0:
                color_offset = 0

            for i in range(len(particles)):
                x, y, distance, angle = particles[i]

                # add a bit of random
                delta = (random.random()*rand_range) - (rand_range//2)
                angle = angle + delta

                # Calculate the new position
                x += ((math.cos(angle) * distance) / 10) * speed
                y += ((math.sin(angle) * distance) / 10) * speed

                # Bounce off the walls
                if x > self.stage_width:
                    x = self.stage_width
                    angle = angle + math.pi
                elif x < 0:
                    x = 0
                    angle = angle + math.pi


                # Store the updated particle data
                particles[i] = (x, y, distance, angle)

                x = int(x)
                y = int(y)

                color_idx = random.randrange(1,3) + color_offset
                self.stage.pixel(x, y, int(color_idx))

                # Sometimes we draw single pixels, sometimes fat pixels
                size = random.choice([2, 2, 2, 2, 1, 1, 1, 1, 1, 1])  # (1-3)
                size = size + int(abs(distance)/10)

                if size > 3:
                    size = 3

                # if round(random.random()):
                self.draw_dot(x, y, color_idx, size)

            rand_range = rand_range * 0.95

            # And some rays emanating from the center
            if (random.random() * 100) > 75:
                angle = 205
                end_x = int(center_x + (random.random() * angle) - (angle/2))
                end_y = 0

                if (random.randint(0,1) +0.1) > 1:
                    # randomly invert the direction
                    end_y = self.display.height

                color1 = random.randrange(1,3)
                color2 = color1 + 1
                color3 = color1 + 2

                self.stage.line(center_x, center_y, end_x, end_y, color1)
                self.stage.line(center_x, center_y, end_x+1, end_y, color2)
                self.stage.line(center_x, center_y, end_x-1, end_y, color2)
                self.stage.line(center_x, center_y, end_x + 2, end_y, color3)
                self.stage.line(center_x, center_y, end_x - 2, end_y, color3)

            self.display.blit(self.stage, 0, 0, self.alpha_color, self.palette)
            self.display.show()
            speed = speed * 0.95

        fade_fx = ScanlineFade(self.display)
        fade_fx.start()

        self.cleanup()
        return True
    def cleanup(self):
        # End of animation
        del self.particles
        self.stage.fill(0)
        gc.collect()

    def draw_dot(self, x, y, color, size=1):
        x, y = int(x), int(y)
        coords = [[x, y]]

        if size == 2:
            coords.append([x+1,y])
            coords.append([x+1,y+1])
            coords.append([x,y+1])
        elif size == 3:
            self.stage.pixel(x, y, 0) # Center pixel transparent

            coords = []
            coords.append([x + 1, y])
            coords.append([x - 1, y])
            coords.append([x, y + 1])
            coords.append([x, y - 1])

        for x, y in coords:
            self.stage.pixel(x, y, color)


