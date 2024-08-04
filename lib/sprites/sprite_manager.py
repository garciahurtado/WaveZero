from micropython import const
import micropython

from death_anim import DeathAnim
from image_loader import ImageLoader
from sprites.sprite_types import create_sprite, SpriteMetadata
import framebuf
import math
from ulab import numpy as np
from indexed_image import Image, create_image
from profiler import Profiler as prof, timed
from sprites.sprite_pool_lite import SpritePool
from typing import Dict, List
from uarray import array

class SpriteManager:
    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)
    display = None
    max_sprites: int = 0
    sprite_images: Dict[str, List[Image]] = {}
    sprite_palettes: Dict[str, bytes] = {}
    sprite_metadata: Dict[str, SpriteMetadata] = {}
    sprite_actions = {}
    lane_width: int = 0
    half_scale_one_dist = int(0)  # This should be set based on your camera setup
    add_frames = 0  # Number of upscaled frames to add
    pool = None
    death_anim = None

    def __init__(self, display: framebuf.FrameBuffer, max_sprites, camera=None, lane_width=None):
        self.display = display
        self.death_anim = DeathAnim(display)

        self.max_sprites = max_sprites
        self.lane_width = lane_width
        self.pool = SpritePool(200)

        if camera:
            self.set_camera(camera)

    def add_type(self, sprite_type, image_path, speed, width, height, color_depth, palette, alpha=None):
        num_frames = max(width, height) + self.add_frames
        speed = speed / 1000
        init_values = \
            {'image_path': image_path,
             'speed': speed,
             'width': width,
             'height': height,
             'color_depth': color_depth,
             'palette': palette,
             'alpha': alpha,
             'frames': [],
             'num_frames': num_frames
             }

        self.sprite_metadata[sprite_type] = SpriteMetadata(**init_values)
        print(str(self.sprite_metadata[sprite_type].image_path))

    def add_action(self, sprite_type, func):
        self.sprite_actions[sprite_type] = func


    def create(self, sprite_type, **kwargs):
        new_sprite, idx = self.pool.get(sprite_type)

        type_meta = self.sprite_metadata[sprite_type]
        new_sprite.speed = type_meta.speed
        new_sprite.frame_width = type_meta.width
        new_sprite.frame_height = type_meta.height
        new_sprite.num_frames = type_meta.num_frames

        #Set user values passed to the function
        for key, value in kwargs.items():
            if value is not None:
                setattr(new_sprite, key, value)

        new_sprite.sprite_type = sprite_type

        #Create images and frames
        if sprite_type not in self.sprite_images:
            self.sprite_images[sprite_type] = self.load_img_and_scale(type_meta, sprite_type)

        new_sprite.active = True
        new_sprite.visible = True

        return new_sprite, idx

    def load_img_and_scale(self, metadata, sprite_type):
        orig_img = ImageLoader.load_image(metadata.image_path)
        frames = []
        num_frames = metadata.num_frames

        for f in range(1, num_frames):
            scale = f / num_frames # Avoid division by zero

            new_width = math.ceil(metadata.width * scale)
            new_height = math.ceil(metadata.height * scale)

            # print(f"Scale is {scale} / w:{new_width} h:{new_height} ")

            if metadata.color_depth == 8:
                new_frame = self.scale_frame_8bit(orig_img, new_width, new_height, scale)
            elif metadata.color_depth == 4:
                new_frame = self.scale_frame_4bit(orig_img, new_width, new_height, scale)
            else:
                raise ValueError(f"Unsupported color depth: {metadata.color_depth}")

            frames.append(new_frame)

        frames.append(orig_img)  # Add original image as the last frame
        self.sprite_palettes[sprite_type] = orig_img.palette

        return frames

    def scale_frame_8bit(self, orig_img, new_width, new_height, scale):
        orig_pixels = np.frombuffer(orig_img.pixel_bytes, dtype=np.uint8)
        orig_pixels = orig_pixels.reshape((orig_img.height, orig_img.width))

        new_bytes = bytearray(new_width * new_height)
        new_buffer = framebuf.FrameBuffer(new_bytes, new_width, new_height, framebuf.GS8)
        new_pixels = np.frombuffer(new_bytes, dtype=np.uint8)
        new_pixels = new_pixels.reshape((new_height, new_width))

        for y in range(new_height):
            for x in range(new_width):
                y_1 = min(int(y / scale), orig_img.height - 1)
                x_1 = min(int(x / scale), orig_img.width - 1)
                new_pixels[y][x] = orig_pixels[y_1][x_1]

        return create_image(new_width, new_height, new_buffer, memoryview(new_bytes),
                            orig_img.palette, orig_img.palette_bytes, 8)

    def scale_frame_4bit(self, orig_img, new_width, new_height, scale):
        if new_width % 2: # Width must always be a multiple of two to that the BMP reader doesn't freak out
            new_width += 1

        # print(f"rescale: {new_width}x{new_height} scale: {scale:.4f}")

        byte_size = math.floor((new_width * new_height) / 2)
        new_bytes = bytearray(byte_size)

        new_buffer = framebuf.FrameBuffer(new_bytes, new_width, new_height, framebuf.GS4_HMSB)

        x_ratio = orig_img.width / new_width
        y_ratio = orig_img.height / new_height

        for y in range(new_height):
            for x in range(0, new_width, 2):
                x_1 = int(x * x_ratio)
                y_1 = int(y * y_ratio)
                x_2 = int((x + 1) * x_ratio)

                # Ensure we don't go out of bounds
                x_1 = min(x_1, orig_img.width - 1)
                x_2 = min(x_2, orig_img.width - 1)
                y_1 = min(y_1, orig_img.height - 1)

                color1 = orig_img.pixels.pixel(x_1, y_1)
                color2 = orig_img.pixels.pixel(x_2, y_1)

                new_buffer.pixel(x, y, color1)
                new_buffer.pixel(x + 1, y, color2)

        return create_image(new_width, new_height, new_buffer, memoryview(new_bytes),
                            orig_img.palette, orig_img.palette_bytes, 4)

    def set_camera(self, camera):
        self.camera = camera
        scale_adj = 10  # Increase this value to see bigger sprites when closer to the screen
        self.half_scale_one_dist = int(abs(self.camera.cam_z - scale_adj) / 2)

    # @timed
    def update(self, sprite, meta, elapsed):
        """The update loop is responsible for killing expired / out of bounds sprites, as well
        as updating the x and y draw coordinates based on """
        if not sprite.active:
            return False

        # prof.start_profile('update_z_speed')
        old_z = sprite.z
        new_z = sprite.z + (sprite.speed * elapsed)
        new_z = int(new_z)
        # prof.end_profile('update_z_speed')
        # print(f"new z={new_z}")

        if new_z == old_z:
            return False

        if new_z < self.camera.near:
            """Past the near clipping plane"""
            if sprite.active:  # Add this check
                self.pool.release(sprite)
            return False

        if new_z < self.camera.far and not sprite.active:
            sprite.active = True

        # prof.start_profile('cam_pos')
        draw_x, draw_y = self.to_2d(sprite.x, sprite.y + meta.height, sprite.z)
        # prof.end_profile('cam_pos')

        num_frames = sprite.num_frames

        real_z = sprite.z

        # prof.start_profile('get_frame_idx')
        frame_idx = self.get_frame_idx(int(real_z), int(self.camera.cam_z), int(num_frames),
                                       int(self.half_scale_one_dist))
        # prof.end_profile('get_frame_idx')

        sprite.z = new_z
        sprite.draw_x = draw_x
        sprite.draw_y = draw_y
        sprite.current_frame = frame_idx

        # if sprite.event_chain:
        #     sprite.event_chain.update()

        return True

    def update_all(self, elapsed):
        metas = self.sprite_metadata
        i = 0
        while i < self.pool.active_count:
            sprite = self.pool.sprites[self.pool.active_indices[i]]
            meta = metas[sprite.sprite_type]

            if self.update(sprite, meta, elapsed):
                self.update_frame(sprite)
                i += 1
            else:
                # Sprite is no longer active
                if sprite.active:
                    self.pool.release(sprite)

    def update_frame(self, sprite):
        frame_idx = self.get_frame_idx(int(sprite.z), int(self.camera.cam_z), int(sprite.num_frames),
                                       int(self.half_scale_one_dist))
        sprite.current_frame = frame_idx


    # @timed
    def show(self, sprite, display: framebuf.FrameBuffer):
        """Draw a single sprite on the display"""
        if not sprite.active:
            return False

        if sprite.blink:
            sprite.blink_flip = sprite.blink_flip * -1
            if sprite.blink_flip == -1:
                return False

        if sprite.z > self.camera.far:
            return False

        sprite_type = sprite.sprite_type
        palette = self.sprite_palettes[sprite_type]
        frame_id = sprite.current_frame

        image = self.sprite_images[sprite_type][frame_id]
        alpha = self.get_alpha(sprite_type)

        """Actions?"""
        if sprite_type in self.sprite_actions.keys():
            action = self.sprite_actions[sprite_type]
            action(display, self.camera, sprite.draw_x, sprite.draw_y, sprite.x, sprite.y, sprite.z, sprite.frame_width)

        self.do_blit(x=int(sprite.draw_x), y=int(sprite.draw_y - image.height / 2), display=display, frame=image.pixels,
                     palette=palette, alpha=alpha)

        return True

    def get_alpha(self, type):
        meta = self.sprite_metadata[type]
        return meta.alpha

    # @timed
    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer, frame, palette, alpha=None):
        if alpha is not None:
            display.blit(frame, int(x), int(y), alpha, palette)
        else:
            display.blit(frame, int(x), int(y), -1, palette)

        return True

    # @timed
    def to_2d(self, x, y, z):
        if self.camera:
            return self.camera.to_2d(x, y, z)
        else:
            return x, y

    def _get_frame_idx_short(self, sprite):
        rate = (sprite.z - self.camera.cam_z) / 2
        if rate == 0:
            rate = 0.0001  # Avoid divide by zero
        scale = abs(self.half_scale_one_dist / rate)
        frame_idx = int(scale * sprite.num_frames)
        return max(0, min(frame_idx, sprite.num_frames - 1))

    def set_lane(self, sprite, lane_num):
        lane = lane_num - 2  # [-2,-1,0,1,2]
        new_x = (lane * self.lane_width) - (sprite.frame_width / 2)
        sprite.lane_num = lane_num
        sprite.x = round(new_x)

    def get_lane(self, sprite):
        # Calculate the center of the sprite
        sprite_center = sprite.x + (sprite.frame_width / 2)

        # Calculate which lane the sprite is in
        lane = round(sprite_center / self.lane_width)

        # Convert lane to lane_num (add 2 to shift from [-2,-1,0,1,2] to [0,1,2,3,4])
        lane_num = lane + 2

        # Ensure lane_num is within valid range
        return max(0, min(4, lane_num))


    # @timed
    @micropython.viper
    def get_frame_idx(self, z: int, cam_z: int, num_frames: int, scale_dist: int) -> int:
        """ Given the Z coordinate (depth), find the scaled frame number which best represents the
        size of the object at that distance """

        rate: int = int(z - cam_z)
        if (rate >= -1) and (rate <= 1):  # Use a small threshold instead of exactly 0
            rate = 2 if rate >= 0 else -2  # Avoid divide by zero

        # Use multiplication instead of division
        scale: int = abs(int(scale_dist) * 2)
        if scale > abs(rate):
            scale = abs(rate)

        temp: int = abs(int(rate))
        scale_num: int = int(int(scale) * int(num_frames))
        frame_idx: int = int(int(scale_num) // int(temp))

        if frame_idx >= num_frames:
            return int(num_frames - 1)
        elif frame_idx < 0:
            return 0
        else:
            return int(frame_idx)

    # @timed
    def show_all(self, display: framebuf.FrameBuffer):
        for i in range(self.pool.active_count):
            sprite = self.pool.sprites[self.pool.active_indices[i]]
            self.show(sprite, display)


# Usage example
def main():
    print("Not intended to run standalone")
    exit(1)


if __name__ == "__main__":
    main()
