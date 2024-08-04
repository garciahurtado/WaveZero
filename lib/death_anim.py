import gc
import math

import framebuf
import random
import utime

from framebuffer_palette import FramebufferPalette


class DeathAnim:
    def __init__(self, display):
        self.display = display
        self.width = display.width
        self.height = display.height
        self.color_mode = framebuf.GS2_HMSB
        self.player = None


        self.init_canvas()

        # Small debris sprites (4x4 each)
        self.debris_sprites = [
            bytearray([0b10101010, 0b01010101, 0b10101010, 0b01010101, 0b10101010, 0b01010101, 0b10101010, 0b01010101]),
            bytearray([0b11001100, 0b00110011, 0b11001100, 0b00110011, 0b11001100, 0b00110011, 0b11001100, 0b00110011]),
            bytearray([0b11110000, 0b11110000, 0b00001111, 0b00001111, 0b11110000, 0b11110000, 0b00001111, 0b00001111]),
            bytearray([0b10000001, 0b01000010, 0b00100100, 0b00011000, 0b00011000, 0b00100100, 0b01000010, 0b10000001]),
            bytearray([0b11111111, 0b10000001, 0b10000001, 0b10000001, 0b10000001, 0b10000001, 0b10000001, 0b11111111])
        ]
        self.explosion_colors = [0x001F, 0x003F, 0x07FF, 0x0FFF]

        gc.collect()
        print(f"Free memory before creating FX framebuf  {gc.mem_free():,} bytes")


    def init_canvas(self):
        # Create a 4-bit stage the size of the display where we will draw the FX
        size = self.display.width * self.display.height // 2
        print(f"Stage size: {size:0} bytes")
        self.canvas = framebuf.FrameBuffer(bytearray(size), self.display.width, self.display.height, self.color_mode)

    def set_player(self, player):
        # Load existing player bike sprite in two halves
        self.bike_palette = FramebufferPalette(4)
        self.bike_palette.set_rgb(0, [0, 0, 0])
        self.bike_palette.set_rgb(1, [194, 0, 255])
        self.bike_palette.set_rgb(2, [117, 0, 255])
        self.bike_palette.set_rgb(3, [0, 17, 255])

        self.bike_sprite = player.image.pixels
        self.bike_half_left = self.create_bike_half()
        self.bike_half_right = self.create_bike_half()
        self.bike_half_left.blit(self.bike_sprite, 0, 0, 0, self.bike_palette)
        self.bike_half_right.blit(self.bike_sprite, 16, 0, 0, self.bike_palette)

        self.player = player

    def create_bike_half(self):
        # Placeholder: Replace with actual left half of bike sprite loading
        return framebuf.FrameBuffer(bytearray([0xFF] * (16 * 22)), 16, 22, framebuf.GS2_HMSB)

    def draw_explosion(self, x, y, radius, frame):

        # Draw concentric squares
        for i, color in enumerate(self.explosion_colors):
            fact = i * 4
            x1 = x + random.randint(0,fact) - int(fact/2)
            y1 = y + random.randint(0,fact) - int(fact/2)
            size = radius - i * 3
            if size > 0:
                self.display.fill_rect(x1 - size // 2, y1 - size // 2, size, size, color)

        # Draw emanating lines
        num_lines = 3
        line_length = radius + 80
        for i in range(num_lines):
            angle = (i * 2 * math.pi / num_lines) + (frame * 0.2 * random.random() - 0.5)
            ex = int(x + math.cos(angle) * line_length)
            ey = int(y + math.sin(angle) * line_length)
            c = random.randint(0, len(self.explosion_colors) - 1)
            color = self.explosion_colors[c]
            self.display.line(x, y, ex, ey, color)

    def draw_debris(self, x, y, sprite):
        self.canvas.blit(framebuf.FrameBuffer(sprite, 4, 4, self.color_mode), x, y)

    def animate(self):
        # Clear the canvas
        # self.canvas.fill(0)

        # Initial explosion
        x = self.player.x + 10
        y = self.player.y + 10
        self.draw_explosion(x, y, 25, 0)
        self.display.show()
        utime.sleep(0.1)

        # Break apart animation
        debris = []
        for _ in range(10):
            debris.append({
                'x': x+random.randint(-8, 8),
                'y': y+random.randint(-8, 8),
                'dx': random.uniform(-2, 2),
                'dy': random.uniform(-2, 2),
                'sprite': random.choice(self.debris_sprites)
            })

        for frame in range(30):
            self.canvas.fill(0)

            # Draw explosion
            radius = 16 - frame // 3
            # if radius > 0:
            #     self.draw_explosion(x, y, radius, frame)

            # Update and draw debris
            # for d in debris:
            #     d['x'] += d['dx']
            #     d['y'] += d['dy']
            #     d['dy'] += 0.05  # Gravity
            #     if 0 <= d['x'] < self.width and 0 <= d['y'] < self.height:
            #         self.draw_debris(int(d['x']), int(d['y']), d['sprite'])

            # Draw broken bike parts (example: two halves moving apart)
            left_x = x - frame
            right_x = x+8 + frame
            if left_x >= 0:
                self.canvas.blit(self.bike_half_left, left_x, y, 0, self.bike_palette)  # Left half
            if right_x < self.width:
                self.canvas.blit(self.bike_half_right, right_x, y, 0, self.bike_palette)  # Right half

            # Update display
            self.display.blit(self.canvas, 0, 0, 0, self.bike_palette)
            self.display.show()
            utime.sleep(0.05)


        # Final fade to black
        for i in range(4):
            self.canvas.fill(0)
            self.display.blit(self.canvas, 0, 0, 0, self.bike_palette)
            self.display.show()
            utime.sleep(0.1)
