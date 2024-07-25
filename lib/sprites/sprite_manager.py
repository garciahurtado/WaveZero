from micropython import const
from ucollections import namedtuple
from image_loader import ImageLoader
import framebuf
import math
from ulab import numpy as np
from indexed_image import Image, create_image

# Define the SpriteData namedtuple with additional fields for scaled sprites
SpriteData = namedtuple('SpriteData', [
    'x', 'y', 'z', 'speed', 'visible', 'active', 'blink', 'blink_flip',
    'pos_type', 'event_chain', 'filename', 'frame_width', 'frame_height',
    'current_frame', 'lane_num', 'draw_x', 'draw_y', 'frames', 'num_frames'
])

# Define metadata structure
SpriteMetadata = namedtuple('SpriteMetadata', [
    'image_path', 'default_speed', 'width', 'height', 'color_depth', 'palette'
])

class SpriteManager:
    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)
    
    def __init__(self, display: framebuf.FrameBuffer, max_sprites, camera=None, lane_width=None):
        self.display = display
        self.max_sprites = max_sprites
        self.sprites = []
        self.sprite_images = {}  # Flyweight store for shared image data
        self.sprite_palettes = {}
        self.sprite_metadata = {}  # Store for sprite type metadata
        self.lane_width = lane_width
        self.half_scale_one_dist = 0  # This should be set based on your camera setup

        if camera:
            self.set_camera(camera)

    def add_type(self, sprite_type, image_path, default_speed, width, height, color_depth, palette):
        self.sprite_metadata[sprite_type] = SpriteMetadata(
            image_path=image_path,
            default_speed=default_speed,
            width=width,
            height=height,
            color_depth=color_depth,
            palette=palette
        )

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

        sprite = {
            'x': x, 'y': y, 'z': z, 'speed': speed,
            'visible': True, 'active': True,
            'blink': False, 'blink_flip': 1,
            'pos_type': self.POS_TYPE_FAR,
            'event_chain': None,
            'frame_width': metadata.width,
            'frame_height': metadata.height,
            'current_frame': 0,
            'lane_num': 0,
            'draw_x': 0, 'draw_y': 0,
            'num_frames': len(self.sprite_images[sprite_type]),
            'meta': metadata,
            'type': sprite_type,
        }

        self.sprites.append(sprite)
        return len(self.sprites) - 1  # Return the index of the new sprite

    def create_scaled_frames(self, metadata, sprite_type):
        orig_img = ImageLoader.load_image(metadata.image_path)
        frames = []
        num_frames = max(metadata.width, metadata.height)

        for f in range(num_frames - 1):
            scale = (f + 0.00001) / num_frames  # Avoid division by zero
            new_width = math.ceil(metadata.width * scale)
            new_height = math.ceil(metadata.height * scale)

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
                x_1 = min(int(x / scale), orig_img.width - 1)
                y_1 = min(int(y / scale), orig_img.height - 1)
                color1 = orig_img.pixels.pixel(x_1, y_1)
                color2 = orig_img.pixels.pixel(min(x_1 + 1, orig_img.width - 1), y_1)
                new_buffer.pixel(x, y, color1)
                new_buffer.pixel(x + 1, y, color2)

        return create_image(new_width, new_height, new_buffer, memoryview(new_bytes),
                            orig_img.palette, orig_img.palette_bytes, 4)

    def set_camera(self, camera):
        self.camera = camera
        scale_adj = 10 # Increase this value to see bigger sprites when closer to the screen
        self.half_scale_one_dist = abs(self.camera.pos['z']-scale_adj) / 2

    def update(self, sprite, elapsed):
        if not sprite['active']:
            return False

        new_z = sprite['z'] + (sprite['speed'] * elapsed)
        
        if new_z > 4000 or new_z < -40:  # Using constants from Sprite3D
            sprite['active'] = False
            sprite['visible'] = False
            return False

        draw_x, draw_y = self.pos(sprite)
        frame_idx = self.get_frame_idx(sprite)

        sprite['z'] = new_z
        sprite['draw_x'] = int(draw_x)
        sprite['draw_y'] = int(draw_y)
        sprite['current_frame'] = frame_idx

        # if sprite['event_chain']:
        #     sprite['event_chain'].update()

        return True

    def show(self, index, display: framebuf.FrameBuffer):
        if index >= len(self.sprites):
            return False

        sprite = self.sprites[index]
        if not sprite['visible']:
            return False

        if sprite['blink']:
            sprite['blink_flip'] = sprite['blink_flip'] * -1
            if self.sprites[index]['blink_flip'] == -1:
                return False

        type = sprite['type']
        palette = self.sprite_palettes[type]
        frame_id = sprite['current_frame']

        image = self.sprite_images[type][frame_id]

        self.do_blit(x=int(sprite['draw_x']), y=int(sprite['draw_y'] - image.height / 2), display=display, frame=image.pixels, palette=palette, alpha=None)
        return True

    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer, frame, palette, alpha=None):
        if alpha:
            #print(f"x/y: {x},{y} / alpha:{self.alpha_color}")
            display.blit(frame, int(x), int(y), self.alpha_color, palette, alpha=alpha)
        else:
            display.blit(frame, int(x), int(y), -1, palette)

        return True

    def pos(self, sprite):
        if self.camera:
            return self.camera.to_2d(int(sprite['x']), int(sprite['y'] + sprite['frame_height']), int(sprite['z']))
        else:
            return sprite['x'], sprite['y']

    def _get_frame_idx_short(self, sprite):
        rate = (sprite['z'] - self.camera.pos['z']) / 2
        if rate == 0:
            rate = 0.0001  # Avoid divide by zero
        scale = abs(self.half_scale_one_dist / rate)
        frame_idx = int(scale * sprite['num_frames'])
        return max(0, min(frame_idx, sprite['num_frames'] - 1))

    def set_lane(self, index, lane_num):
        if index >= len(self.sprites):
            return

        sprite = self.sprites[index]
        lane = lane_num - 2  # [-2,-1,0,1,2]
        new_x = (lane * self.lane_width) - (sprite.frame_width / 2)
        sprite['lane_num'] = lane_num
        sprite['x'] = round(new_x)
        self.sprites[index] = sprite

    def update_all(self, elapsed):

        for i, sprite in enumerate(self.sprites):
            sprite = self.sprites[i]
            self.update(sprite, elapsed)
            self.update_frame(sprite)

            self.sprites[i] = sprite

    def update_frame(self, sprite):
        frame_idx = self.get_frame_idx(sprite)
        sprite['current_frame'] = frame_idx

    def get_frame_idx(self, sprite):
        """ Given the Z coordinate (depth), find the scaled frame number which best represents the
        size of the object at that distance """

        num_frames = sprite['num_frames']
        real_z = sprite['z']

        rate = (real_z - self.camera.pos['z']) / 2
        if rate == 0:
            rate = 0.0001 # Avoid divide by zero

        scale = abs(self.half_scale_one_dist / rate)
        frame_idx = int(scale * num_frames)

        if frame_idx > num_frames - 1:
            frame_idx = num_frames - 1

        if frame_idx < 0:
            frame_idx = 0

        return frame_idx

    def show_all(self, display: framebuf.FrameBuffer):
        for i in range(len(self.sprites)):
            self.show(i, display)

# Usage example
def main():
    print("Not intended to run standalone")
    exit(1)

if __name__ == "__main__":
    main()
