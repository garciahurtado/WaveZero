import gc
import random
import framebuf
import time
import utime

from anim.animation import Animation
from colors.framebuffer_palette import FramebufferPalette
from colors.framebuffer_palette import FramebufferPalette as fp
from sprites_old.spritesheet import Spritesheet
from colors import color_util as colors
from profiler import prof

class DeathAnim(Animation):
    def __init__(self, display):
        self.display = display
        self.width = display.width
        self.height = display.height
        self.callback = None

        self.player = None
        self.elapsed_time = 0
        self.total_duration = 2000  # Total animation duration in milliseconds
        self.debris_count: int = 80
        self.debris = [None] * self.debris_count
        self.explosion_center = None
        self.running = False
        self.start_time = None
        self.speed = self.orig_speed = 300
        self.gravity = 0.0012  # Gravity (pixels per millisecond^2)
        self.base_x = 0
        self.base_y = 0

        self.debris_sprites = Spritesheet(filename='/img/debris_bits.bmp', frame_width=4, frame_height=4).frames
        self.debris_large = Spritesheet(filename='/img/debris_large.bmp', frame_width=8, frame_height=6).frames

        # Define blue and cyan colors in RGB format
        self.debris_colors_hex = [
            0x001F9F,
            0x003AA9,
            0x005CB5,
            0x0077BF,
            0x00A1CD,
            0x00FFFF,
            0xB4F0F0,
        ]

        debris_colors_int = [colors.hex_to_565(rgb, format=fp.BGR565) for rgb in self.debris_colors_hex]
        fire_colors_int = [colors.hex_to_565(rgb) for rgb in self.debris_colors_hex]

        # Create 5 separate palettes, one for each color
        self.debris_palettes = []
        self.fire_palettes = []

        for debris_c, fire_c in zip(debris_colors_int, fire_colors_int):
            palette = FramebufferPalette(2)
            palette.set_int(0, 0x0000)
            palette.set_int(1, int(debris_c))
            self.debris_palettes.append(palette)

            palette2 = FramebufferPalette(2)
            palette2.set_int(0, 0x0000)
            palette2.set_int(1, int(fire_c))
            self.fire_palettes.append(palette2)

        """Flyweight objects """
        self.debris = [None] * self.debris_count

    def start_animation(self, x, y):
        self.elapsed_time = 0
        self.start_time = utime.ticks_ms()
        self.explosion_center = (x + 16, y + 10)
        self.speed = self.orig_speed

        debris_speed = self.speed * 0.0007

        gc.collect()
        prof.start_profile("death.debris_create")

        for idx in range(self.debris_count):
            pid = self.get_random_palette_id()
            choice = random.choice([0,1,2,3]) - 1

            if choice < 0: # 1 in 4 chance
                sprite = random.choice(self.debris_large)
                max_age = int(1500 + (random.uniform(-200, 300)))
                this_speed = random.uniform(0.5, 1.5) * debris_speed
            else:
                sprite = random.choice(self.debris_sprites)
                max_age = int(1000 + (random.uniform(-200, 300)))
                this_speed = random.uniform(0.7, 1.8) * debris_speed

            self.debris[idx] = {
                'x': self.explosion_center[0] + random.randint(-8, 8),
                'y': self.explosion_center[1] + random.randint(-8, 8),
                'dx': random.uniform(-this_speed, this_speed),  # Speed in pixels per millisecond
                'dy': random.uniform(-this_speed/2, -this_speed),
                'sprite': sprite,
                'palette_id': pid,
                'max_age': max_age,
            }

        prof.end_profile("death.debris_create")

        gc.collect()
        self.check_mem()

        self.running = True

    def get_random_palette_id(self):
        idx = random.randint(0, len(self.debris_palettes) - 1)
        return idx

    def draw_explosion(self, x, y, radius):
        for i in range(16):
            palette_id = self.get_random_palette_id()
            palette = self.fire_palettes[palette_id]
            color = palette.get_int(1)

            fact = int(radius * self.elapsed_time / 100)  # Scale based on elapsed time

            x1 = x + random.randint(0, fact) - int(fact * 0.5)
            y1 = y + random.randint(0, fact) - int(fact * 0.7)

            size = int(radius - ((self.elapsed_time / 700) * (random.random()/2)))
            if size > 0:
                self.display.fill_rect(int(x1 - size // 4), int(y1 - size // 2), int(size // 2), size, color)

    def draw_debris(self, x, y, sprite, palette):
        self.display.blit(sprite, x, y, 0, palette)

    def update_and_draw(self):
        """ This is a very weird and inefficient way of doing things """
        if not self.running or not self.start_time:
            return False

        current_time = utime.ticks_ms()
        frame_time = utime.ticks_diff(current_time, self.start_time)
        delta_time = (frame_time - self.elapsed_time) * (self.speed / 1000)
        self.elapsed_time = frame_time

        """ Check whether the animation has reached its end """
        if time.ticks_diff(current_time, self.start_time) > self.total_duration:
            if self.callback:
                self.callback()

            self.running = False
            return False

        gravity = self.gravity

        # Draw explosion
        explosion_progress = min(self.elapsed_time / self.total_duration, 1)
        radius = max(16 - int(16 * explosion_progress), 0)
        radius = radius * 2
        if radius > 0:
            self.draw_explosion(*self.explosion_center, radius)

        # Update and draw debris
        for d in self.debris:
            if frame_time > d['max_age']:
                continue

            d['x'] += d['dx'] * delta_time
            d['y'] += d['dy'] * delta_time
            d['dy'] += gravity * delta_time

            palette = self.debris_palettes[d['palette_id']]

            if 0 <= d['x'] < self.width and 0 <= d['y'] < self.height:
                self.draw_debris(int(d['x']), int(d['y']), d['sprite'], palette)

        self.speed = self.speed - 6
        if self.speed < 20:
            self.speed = 20

        """ we're in charge for display rendering, because all the other tasks are waiting on this one"""
        # await asyncio.sleep_ms(50)
        return self.elapsed_time < self.total_duration


    def create_bike_half(self):
        # Placeholder: Replace with actual left half of bike sprite loading
        return framebuf.FrameBuffer(bytearray([0xFF] * (16 * 22)), 16, 22, framebuf.GS2_HMSB)

    def check_mem(self):
        print(f"Free memory:  {gc.mem_free():,} bytes")

