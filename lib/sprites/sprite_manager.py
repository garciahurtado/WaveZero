from micropython import const
import micropython
from ucollections import namedtuple
from image_loader import ImageLoader
from sprites.sprite_types import SpriteData, SpriteMetadata
import framebuf
import math
from ulab import numpy as np
import utime
from indexed_image import Image, create_image
from profiler import Profiler as prof, timed


class SpriteManager:
    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)

    def __init__(self, display: framebuf.FrameBuffer, max_sprites, camera=None, lane_width=None):
        self.display = display
        self.max_sprites = max_sprites
        self.active_sprites = []
        self.sprite_images = {}  # Flyweight store for shared image data
        self.sprite_palettes = {}
        self.sprite_metadata = {}  # Store for sprite type metadata
        self.sprite_actions = {}  # Store for sprite type metadata
        self.lane_width = lane_width
        self.half_scale_one_dist = int(0)  # This should be set based on your camera setup
        self.add_frames = 0 # Number of upscaled frames to add

        if camera:
            self.set_camera(camera)

    def add_type(self, sprite_type, image_path, default_speed, width, height, color_depth, palette, alpha=None):
        num_frames = max(width, height) + self.add_frames

        self.sprite_metadata[sprite_type] = SpriteMetadata(
            image_path=image_path,
            default_speed=default_speed,
            width=width,
            height=height,
            color_depth=color_depth,
            palette=palette,
            alpha=alpha,
            frames=[],
            num_frames=num_frames
        )

    def add_action(self, sprite_type, func):
        self.sprite_actions[sprite_type] = func

    def create(self, sprite_type, x=0, y=0, z=0, speed=None):
        # if len(self.sprites) >= self.max_sprites:
        #     return None  # No available sprites in the pool

        metadata = self.sprite_metadata.get(sprite_type)
        if metadata is None:
            # Invalid sprite type
            print(f"{sprite_type} is not a registered Sprite")
            return None

        if speed is None:
            speed = metadata.default_speed

        if sprite_type not in self.sprite_images:
            self.sprite_images[sprite_type] = self.create_scaled_frames(metadata, sprite_type)
        new_sprite = SpriteData(
            sprite_type=sprite_type,
            x=x, y=y, z=z,
            speed=speed,
            visible=True, active=True,
            blink=False, blink_flip=1,
            pos_type=self.POS_TYPE_FAR,
            event_chain=None,
            frame_width=metadata.width,
            frame_height=metadata.height,
            num_frames=metadata.num_frames,
            born_ms=utime.ticks_ms()
        )

        self.active_sprites.append(new_sprite)
        return len(self.active_sprites) - 1  # Return the index of the new sprite

    def create_scaled_frames(self, metadata, sprite_type):
        orig_img = ImageLoader.load_image(metadata.image_path)
        frames = []
        num_frames = metadata.num_frames

        for f in range(num_frames - 1):
            scale = (f + 0.00001) / (num_frames - 1)  # Avoid division by zero
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
        if new_width % 2:
            new_width += 1

        byte_size = math.floor((new_width * new_height) / 2)
        new_bytes = bytearray(byte_size)
        new_buffer = framebuf.FrameBuffer(new_bytes, new_width, new_height, framebuf.GS4_HMSB)

        for y in range(new_height):
            for x in range(0, new_width, 2):
                x_1 = int(x / scale)
                y_1 = int(y / scale)
                color1 = orig_img.pixels.pixel(x_1, y_1)
                color2 = orig_img.pixels.pixel(min(x_1 + 1, orig_img.width - 1), y_1)
                new_buffer.pixel(x, y, color1)
                new_buffer.pixel(x + 1, y, color2)

        return create_image(new_width, new_height, new_buffer, memoryview(new_bytes),
                            orig_img.palette, orig_img.palette_bytes, 4)

    def set_camera(self, camera):
        self.camera = camera
        scale_adj = 10  # Increase this value to see bigger sprites when closer to the screen
        self.half_scale_one_dist = int(abs(self.camera.cam_z - scale_adj) / 2)

    # @timed
    def update(self, sprite, elapsed):
        """The update loop is responsible for killing expired / out of bounds sprites, as well
        as updating the x and y draw coordinates based on """
        if not sprite.active:
            return False

        old_z = sprite.z
        new_z = sprite.z + (sprite.speed * (elapsed / 1000))
        if new_z == old_z:
            return False

        if new_z < self.camera.near:
            """Past the near clipping plane"""
            sprite.active = False
            sprite.visible = False
            self.active_sprites.remove(sprite)
            return False

        draw_x, draw_y = self.pos(sprite)
        num_frames = sprite.num_frames
        real_z = sprite.z
        frame_idx = self.get_frame_idx(real_z, num_frames)

        sprite.z = new_z
        sprite.draw_x = draw_x
        sprite.draw_y = draw_y
        sprite.current_frame = frame_idx

        # if sprite.event_chain:
        #     sprite.event_chain.update()

        return True

    # @timed
    def show(self, sprite, display: framebuf.FrameBuffer):
        """Draw a single sprite on the display"""
        if not sprite.visible:
            return False

        if sprite.blink:
            sprite.blink_flip = sprite.blink_flip * -1
            if sprite.blink_flip == -1:
                return False

        sprite_type = sprite.sprite_type
        palette = self.sprite_palettes[sprite_type]
        frame_id = sprite.current_frame

        image = self.sprite_images[sprite_type][frame_id]
        alpha = self.get_alpha(sprite_type)

        """Actions?"""
        if sprite_type in self.sprite_actions.keys():
            action = self.sprite_actions[sprite_type]
            action(display, self.camera, sprite.draw_x, sprite.draw_y, sprite.x,  sprite.y,  sprite.z, sprite.frame_width)

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
    def pos(self, sprite):
        if self.camera:
            return self.camera.to_2d(int(sprite.x), int(sprite.y), int(sprite.z))
        else:
            return sprite.x, sprite.y

    def _get_frame_idx_short(self, sprite):
        rate = (sprite.z - self.camera.cam_z) / 2
        if rate == 0:
            rate = 0.0001  # Avoid divide by zero
        scale = abs(self.half_scale_one_dist / rate)
        frame_idx = int(scale * sprite.num_frames)
        return max(0, min(frame_idx, sprite.num_frames - 1))

    def set_lane(self, index, lane_num):
        if index >= len(self.active_sprites):
            return

        sprite = self.active_sprites[index]
        lane = lane_num - 2  # [-2,-1,0,1,2]
        new_x = (lane * self.lane_width) - (sprite.frame_width / 2)
        sprite.lane_num = lane_num
        sprite.x = round(new_x)
        self.active_sprites[index] = sprite

    def update_all(self, elapsed):

        for sprite in self.active_sprites:
            self.update(sprite, elapsed)
            self.update_frame(sprite)

    def update_frame(self, sprite):
        frame_idx = self.get_frame_idx(sprite.z, sprite.num_frames)
        sprite.current_frame = frame_idx

    # @timed
    @micropython.native
    def get_frame_idx(self, z, num_frames):
        """ Given the Z coordinate (depth), find the scaled frame number which best represents the
        size of the object at that distance """


        rate = (z - self.camera.cam_z) / 2
        if abs(rate) < 0.0001:  # Use a small threshold instead of exactly 0
            rate = 0.0001  # Avoid divide by zero

        scale = abs(self.half_scale_one_dist / rate)
        if scale > 1:
            scale = 1

        frame_idx = int(scale * num_frames)

        if frame_idx >= num_frames:
            return num_frames - 1
        elif frame_idx < 0:
            return 0
        else:
            return frame_idx

    # @timed
    def show_all(self, display: framebuf.FrameBuffer):
        for sprite in self.active_sprites:
            self.show(sprite, display)


# Usage example
def main():
    print("Not intended to run standalone")
    exit(1)


if __name__ == "__main__":
    main()
