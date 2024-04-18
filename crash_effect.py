import asyncio
import gc
import math
import random

import framebuf

from sprite import Sprite, Spritesheet


class DeathEffect():
    x = 0
    y = 0
    particles = []
    explode_sprite: Spritesheet
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
        print(f"Free memory before main loop:  {gc.mem_free():,} bytes")

        # Create a 1-bit stage the size of the display where we will draw the FX
        size = self.display.width * self.display.height / 2
        print(f"Stage size: {size:0} bytes")
        stage = bytearray(int(size))
        self.stage = framebuf.FrameBuffer(stage, self.display.width, self.display.height, framebuf.GS4_HMSB)

    def create_particles(self):
        bitmap = self.explode_sprite.pixels

        # Get the center of the bitmap
        self.center_x = self.explode_sprite.frame_width // 2
        self.center_y = self.explode_sprite.frame_height // 2

        # Create a list to store particle data
        particles = []

        # Get the particle data from the bitmap
        for x in range(0, 25, 3):
            for y in range(0, 42, 3):
                if bitmap.pixel(x, y) != 0 and round(random.random()):
                    # Calculate the distance from the center
                    distance = math.sqrt((x - self.center_x) ** 2 + (y - self.center_y) ** 2)
                    if distance < 4:
                        distance == 4

                    # Calculate the angle from the center
                    angle = math.atan2(y - self.center_y, x - self.center_x)

                    # Center the particles on the source sprite
                    new_x = x + self.explode_sprite.x
                    new_y = y + self.explode_sprite.y

                    # Store the particle data as a tuple
                    particles.append((new_x, new_y, distance, angle))

        print(f"Num particles created: {len(particles)}")

        self.particles = particles
        return particles

    def anim_particles(self):
        particles = self.particles
        speed = 5
        center_x = self.center_x + self.explode_sprite.x
        center_y = self.center_y + self.explode_sprite.y

        # Animate the particles
        for i in range(60): # number of frames for this animation
            for i in range(len(particles)):
                x, y, distance, angle = particles[i]

                # add a bit of random
                range = 0.2
                angle = angle + (random.random()*range -(range/2))

                # Calculate the new position
                x += (math.cos(angle) * distance / 10) * (speed + random.random()*2)
                y += (math.sin(angle) * distance / 10) * (speed + random.random()*2)

                # Bounce off the walls
                if x > self.stage_width:
                    x = self.stage_width
                    angle = angle + math.pi
                elif x < 0:
                    x = 0
                    angle = angle + math.pi
                elif y > self.stage_height:
                    y = self.stage_height
                    angle = angle + math.pi
                elif y < 0:
                    y = 0
                    angle = angle + math.pi


                # Store the updated particle data
                particles[i] = (x, y, distance, angle)

                color = random.randrange(0,4)
                self.stage.pixel(int(x), int(y), color)

                # Sometimes we draw single pixels, sometimes fat pixels
                size = random.choice([1, 1, 1, 1, 1, 1, 2, 2, 2, 3])  # (1-3)
                # if round(random.random()):
                self.draw_dot(x, y, color, size)

            # throw some random scanlines too
            num_lines = random.randrange(1,3)
            for i in range(num_lines):
                y = random.randrange(0, self.stage_height)
                self.stage.line(0, y, self.stage_width, y, 0)

            # And some rays emanating from the center
            if (random.random() * 100) > 80:
                end_x = int(center_x + (random.random() * 150) - 75)
                end_y = 0

                if random.randint(0,2):
                    # randomly invert the line
                    end_y = self.display.height

                self.stage.line(center_x, center_y, end_x, end_y, 1)
                self.stage.line(center_x, center_y, end_x+1, end_y, 2)
                self.stage.line(center_x, center_y, end_x-1, end_y, 2)

            self.display.blit(self.stage, 0, 0, self.explode_sprite.alpha_color, self.explode_sprite.palette)
            self.display.show()
            speed = speed * 0.97

        # End of animation
        self.particles = []
        self.stage.fill(0)

        return True

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


