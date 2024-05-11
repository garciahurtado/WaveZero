import math

from sprites.sprite_3d import Sprite3D
import framebuf
from ulab import numpy as np
from indexed_image import Image, create_image

class ScaledSprite(Sprite3D):
    """ A Scaled Sprite works similarly to a spritesheet in that it has multiple frames. These frames are generated
    when the Sprite is first created, by scaling down (or up) the original image. These frames will be used to
    show the sprite at different distances in order to simulate 3D """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if hasattr(self, 'filename'): # Will be None when cloning
            self.create_scaled_frames()
            self.set_frame(0)

    def create_scaled_frames(self):
        if self.height >= self.width:
            num_frames = self.height
        else:
            num_frames = self.width

        self.frames = []
        orig_img: Image = self.image

        # print(f"Generating {num_frames} frames")

        for f in range(0, num_frames - 2):
            if f == 0:
                f = 0.00001

            scale = f / num_frames
            if scale > 1:
                scale = 1

            new_width = math.ceil(self.width * scale)
            new_height = math.ceil(self.height * scale)


            # print(f"new pixels size: {new_width*new_height}")
            new_bytes = None
            if self.image.color_depth == 8:
                orig_pixels = np.frombuffer(orig_img.pixel_bytes, dtype=np.uint8)
                orig_pixels = orig_pixels.reshape((self.height, self.width))

                new_bytes = bytearray(new_width * new_height)
                new_buffer = framebuf.FrameBuffer(
                    new_bytes,
                    new_width,
                    new_height,
                    framebuf.GS8
                )

                new_pixels = np.frombuffer(new_bytes, dtype=np.uint8)
                new_pixels = new_pixels.reshape((new_height, new_width))

                # Copy the original pixels at scale, nearest neighbor style
                for y in range(new_height):
                    # y -= 0.5
                    for x in range(new_width):
                        # x -= 0.5
                        y_1 = int(y * scale)
                        x_1 = int(x * scale)

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


            elif self.image.color_depth == 4:
                orig_pixels = np.frombuffer(orig_img.pixel_bytes, dtype=np.uint8)

                """ Due to the byte boundary, an odd width causes an orphan half-byte at the last column, which must
                be taken into account"""
                if new_width % 2:
                    new_width += 1

                byte_size = math.floor((new_width * new_height)/2)
                new_bytes = bytearray(byte_size)
                new_buffer = framebuf.FrameBuffer(
                    new_bytes,
                    new_width,
                    new_height,
                    framebuf.GS4_HMSB
                )
                orig_pixels = self.image.pixels

                for y in range(new_height):
                    #print(f"Row {y}")
                    for x in range(0, new_width, 2):
                        """ Since we are converting from 2 bytes per pixel to 1 jump 2 at a time"""
                        x_1 = int(x / scale)
                        y_1 = int(y / scale)

                        if y_1 >= self.height:
                            y_1 = self.height - 1

                        if x_1 >= self.width:
                            x_1 = self.width - 1

                        if y_1 < 0:
                            y_1 = 0

                        if x_1 < 0:
                            x_1 = 0

                        color1 = orig_pixels.pixel(x_1, y_1)
                        color2 = orig_pixels.pixel(x_1+1, y_1)

                        new_buffer.pixel(x, y, color1)
                        new_buffer.pixel(x+1, y, color2)
            else:
                raise Exception(f"Unsupported color depth: {self.image.color_depth}")


            frame = create_image(
                new_buffer,
                memoryview(new_bytes),
                new_width,
                new_height,
                self.palette,
                self.image.color_depth)
            self.frames.append(frame)

        # Finally, the last frame is the original image at full size
        self.frames.append(self.image)


