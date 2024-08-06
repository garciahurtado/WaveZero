import math
import random
import framebuf
import utime
from framebuffer_palette import FramebufferPalette
from sprites.spritesheet import Spritesheet
import color_util as colors

class DeathAnim:
    def __init__(self, display):
        self.display = display
        self.width = display.width
        self.height = display.height
        self.player = None
        self.elapsed_time = 0
        self.total_duration = 2500  # Total animation duration in milliseconds
        self.debris = []
        self.explosion_center = (10, 10)
        self.animation_started = False
        self.start_time = 0
        self.speed = 500

        self.debris_sprites = Spritesheet(filename='/img/debris_bits.bmp', frame_width=4, frame_height=4, color_depth=1).frames
        self.debris_large = Spritesheet(filename='/img/debris_large.bmp', frame_width=8, frame_height=6, color_depth=1).frames

        # Define blue and cyan colors in RGB format
        self.debris_colors = [
            [255, 0, 0],  # Blue
            [255, 255, 0],  # Cyan
            [255, 128, 0],  # Light Blue
            [255, 192, 0],  # Sky Blue
            [128, 64, 0],  # Steel Blue
        ]

        self.debris_colors = [colors.rgb_to_565_v2(color) for color in self.debris_colors]

        # Create 5 separate palettes, one for each color
        self.debris_palettes = []

        for color in self.debris_colors:
            color = int.from_bytes(color, "little")
            palette = FramebufferPalette(2, color_mode=FramebufferPalette.RGB565)
            palette.set_bytes(0, 0x0000)
            palette.set_bytes(1, color)
            self.debris_palettes.append(palette)

    def start_animation(self, player):
        self.player = player
        self.elapsed_time = 0
        self.start_time = utime.ticks_ms()
        self.explosion_center = (self.player.x + 10, self.player.y + 10)
        self.debris = []
        for _ in range(50):  # Increased number of debris pieces
            idx = random.randint(0, len(self.debris_palettes)-1)
            palette = self.debris_palettes[idx]
            if random.choice([0,1]):
                sprite = random.choice(self.debris_sprites)
                max_age = int(3000 + (random.uniform(-500, 500)))
            else:
                sprite = random.choice(self.debris_large)
                max_age = int(1500 + (random.uniform(-200, 200)))

            self.debris.append({
                'x': self.explosion_center[0] + random.randint(-8, 8),
                'y': self.explosion_center[1] + random.randint(-8, 8),
                'dx': random.uniform(-0.1, 0.1),  # Speed in pixels per millisecond
                'dy': random.uniform(-0.1, 0.15),
                'sprite': sprite,
                'palette': palette,
                'max_age': max_age
            })
        self.animation_started = True

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

    def draw_explosion(self, x, y, radius):
        for i in range(len(self.debris_colors) * 4):
            c = i % len(self.debris_colors)
            color = self.debris_colors[c]
            color = int.from_bytes(color, 'little')
            fact = int(i * 6 * self.elapsed_time / 1000)  # Scale based on elapsed time
            x1 = x + random.randint(0, fact) - int(fact / 3)
            y1 = y + random.randint(0, fact) - int(fact / 3)
            size = radius - (i * random.randint(3, 10))
            if size > 0:
                self.display.fill_rect(x1 - size // 2, y1 - size // 2, size, size, color)

    def draw_debris(self, x, y, sprite, palette):
        self.display.blit(sprite, x, y, 0, palette)


    def update_and_draw(self):
        if not self.animation_started:
            return False

        current_time = utime.ticks_ms()
        frame_time = utime.ticks_diff(current_time, self.start_time)
        delta_time = (frame_time - self.elapsed_time) * (self.speed / 1000)
        self.elapsed_time = frame_time


        # Draw explosion
        explosion_progress = min(self.elapsed_time / self.total_duration, 1)
        radius = max(16 - int(16 * explosion_progress), 0)
        if radius > 0:
            self.draw_explosion(*self.explosion_center, radius)

        # Update and draw debris
        for d in self.debris:
            if frame_time > d['max_age']:
                self.debris.remove(d)
                continue

            d['x'] += d['dx'] * delta_time
            d['y'] += d['dy'] * delta_time
            d['dy'] += 0.00015 * delta_time  # Gravity (pixels per millisecond^2)
            if 0 <= d['x'] < self.width and 0 <= d['y'] < self.height:
                self.draw_debris(int(d['x']), int(d['y']), d['sprite'].pixels, d['palette'])

        self.speed = self.speed - 10
        if self.speed < 50:
            self.speed = 50

        return self.elapsed_time < self.total_duration

    def is_animating(self):
        return self.animation_started and self.elapsed_time < self.total_duration
