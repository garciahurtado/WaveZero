import math

from image_loader import ImageLoader
from sprite_3d import Sprite3D
import framebuf
from ulab import numpy as np
from indexed_image import Image, create_image

class ScaledSprite(Sprite3D):
    frames = []
    current_frame:int = 0
    filename: str = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.width and self.height:
            self.ratio = self.width / self.height

        if self.filename: # Will be None when cloning
            self.set_frame(0)
            self.create_scaled_frames()

    def create_scaled_frames(self):
        if self.height >= self.width:
            num_frames = self.height - 1
        else:
            num_frames = self.width - 1

        self.frames = []
        orig_img: Image = self.image

        print(f"Generating {num_frames} frames")

        for f in range(1, num_frames + 1):
            scale = f / num_frames
            if scale > 1:
                scale = 1

            new_width = round(self.width * scale)
            new_height = round(self.height * scale)

            orig_pixels = np.frombuffer(orig_img.pixel_bytes, dtype=np.uint8)

            # print(f"new pixels size: {new_width*new_height}")
            new_bytes = None
            if self.image.color_depth == 8:
                orig_pixels = orig_pixels.reshape((self.height, self.width))

                new_bytes = bytearray(new_width * new_height)
                new_pixels = np.frombuffer(new_bytes, dtype=np.uint8)
                new_pixels = new_pixels.reshape((new_height, new_width))

                # Copy the original pixels at scale, nearest neighbor style
                for y in range(new_height):
                    # y -= 0.5
                    for x in range(new_width):
                        # x -= 0.5
                        y_1 = round(y * scale)
                        x_1 = round(x * scale)

                        if y_1 >= self.height:
                            y_1 = self.height - 1

                        if x_1 >= self.width:
                            x_1 = self.width - 1

                        if y_1 < 0:
                            y_1 = 0

                        if x_1 < 0:
                            x_1 = 0

                        # print(f"x/y: {x},{y} // x1/y1: {x_1} {y_1}")
                        new_pixels[y][x] = orig_pixels[y_1][x_1]

                new_buffer = framebuf.FrameBuffer(
                    new_bytes,
                    new_width,
                    new_height,
                    framebuf.GS8
                )

            elif self.image.color_depth == 4:
                new_bytes = bytearray(int((new_width * new_height)))
                new_buffer = framebuf.FrameBuffer(
                    new_bytes,
                    new_width,
                    new_height,
                    framebuf.GS4_HMSB
                )

                for y in range(new_height):
                    for x in range(0, new_width):
                        x_1 = int(x / scale)
                        y_1 = int(y / scale)

                        cell_num = (y_1 * self.width) + x_1
                        idx = int(cell_num / 2)
                        value = orig_pixels[int(idx)]

                        # if cell_num % 2:
                        #     value = value >> 4
                        # else:
                        #     value = value << 4
                        #     value = value >> 4

                        new_buffer.pixel(x, y, int(value))

            # print(f"Making scaled frame:: {new_width} x {new_height}")

            frame = create_image(
                new_buffer,
                memoryview(new_bytes),
                new_width,
                new_height,
                self.palette,
                self.image.color_depth)
            self.frames.append(frame)

        self.set_frame(0)

