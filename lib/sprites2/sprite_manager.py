import gc

from micropython import const
import micropython

from death_anim import DeathAnim
from images.image_loader import ImageLoader
from perspective_camera import PerspectiveCamera
from sprites2.sprite_types import SpriteType, SPRITE_DATA_LAYOUT
import framebuf
import math
from images.indexed_image import Image, create_image
from sprites2.sprite_pool_lite import SpritePool
from typing import Dict, List
from profiler import Profiler as prof
import utime as time

class SpriteManager:
    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)
    display = None
    max_sprites: int = 0
    sprite_images: Dict[str, List[Image]] = {}
    sprite_palettes: Dict[str, bytes] = {}
    sprite_metadata: Dict[str, SpriteType] = {}
    sprite_classes: Dict[int, SpriteType] = {}
    sprite_actions = {}
    lane_width: int = 0
    half_scale_one_dist = int(0)  # This should be set based on your camera setup
    add_frames = 0  # Number of upscaled frames to add
    pool = None
    grid = None
    camera: PerspectiveCamera = None

    def __init__(self, display: framebuf.FrameBuffer, max_sprites, camera=None, lane_width=None, grid=None):
        self.display = display

        self.max_sprites = max_sprites
        self.lane_width = lane_width
        self.grid = grid

        self.check_mem()
        self.pool = SpritePool(self.max_sprites)

        if camera:
            self.set_camera(camera)

    def add_type(self, sprite_type, sprite_class, image_path, speed, width, height, color_depth, palette=None, alpha_index=-1, alpha_color=0, repeats=0, repeat_spacing=0):
        num_frames = max(width, height) + self.add_frames

        speed = speed
        init_values = \
            {   'image_path': image_path,
                'speed': speed,
                'width': width,
                'height': height,
                'color_depth': color_depth,
                'palette': palette,
                'alpha_index': alpha_index,
                'alpha_color': alpha_color,
                'num_frames': num_frames,
                'repeats': repeats,
                'repeat_spacing': repeat_spacing,
             }


        self.sprite_classes[sprite_type] = sprite_class
        # names = init_values.values()
        type_obj = sprite_class(**(init_values))
        self.sprite_metadata[sprite_type] = type_obj

        print("Sprite registered: " + str(self.sprite_metadata[sprite_type].image_path))

    def add_action(self, sprite_type, func):
        self.sprite_actions[sprite_type] = func

    def get_class_properties(self, cls):
        props = {}
        names = [attr for attr in dir(cls)
                if not callable(getattr(cls, attr))
                and not attr.startswith("__")]

        for name in names:
            props[name] = getattr(cls, name)

        return props


    def create(self, sprite_type, **kwargs):
        new_sprite, idx = self.pool.get(sprite_type)
        new_sprite.x = new_sprite.y = new_sprite.z = 0

        if sprite_type not in self.sprite_classes.keys():
            raise IndexError(f"Sprite type {sprite_type} is not defined")

        class_name = self.sprite_classes[sprite_type]
        class_attrs = self.get_class_properties(class_name)
        class_meta = self.sprite_metadata[sprite_type]

        # Set defaults for properties both in the sprite class as well as in the sprite entity
        for name, val in class_attrs.items():
            if name in SPRITE_DATA_LAYOUT.keys():
                setattr(new_sprite, name, val)
            new_sprite.speed = class_meta.speed
            new_sprite.frame_width = class_meta.width
            new_sprite.frame_height = class_meta.height
            new_sprite.num_frames = class_meta.num_frames

        #Set user values passed to the function
        for key, value in kwargs.items():
            if value is not None:
                setattr(new_sprite, key, value)

        new_sprite.sprite_type = sprite_type

        #Create images and frames
        if sprite_type not in self.sprite_images:
            self.sprite_images[sprite_type] = self.load_img_and_scale(class_meta, sprite_type)

        new_sprite.active = True
        return new_sprite, idx

    def load_img_and_scale(self, metadata, sprite_type):
        orig_img = ImageLoader.load_image(metadata.image_path, metadata.width, metadata.height)
        if isinstance(orig_img, list):
            orig_img = orig_img[0]

        frames = []
        num_frames = metadata.num_frames

        for f in range(1, num_frames):
            scale = f / num_frames # Avoid division by zero

            new_width = math.ceil(metadata.width * scale)
            new_height = math.ceil(metadata.height * scale)

            # print(f"Scale is {scale} / w:{new_width} h:{new_height} ")

            new_frame = self.scale_frame(orig_img, new_width, new_height, metadata.color_depth)
            frames.append(new_frame)

        frames.append(orig_img)  # Add original image as the last frame
        self.sprite_palettes[sprite_type] = orig_img.palette
        metadata.palette = orig_img.palette
        self.set_alpha_color(metadata)

        return frames

    def scale_frame(self, orig_img, new_width, new_height, color_depth):
        if color_depth not in [4, 8]:
            raise ValueError(f"Unsupported color depth: {color_depth}")

        if new_width % 2 and color_depth == 4:  # Width must be even for 4-bit images
            new_width += 1

        byte_size = (new_width * new_height) // (8 // color_depth)
        new_bytes = bytearray(byte_size)

        if color_depth == 4:
            buffer_format = framebuf.GS4_HMSB
        else:  # 8-bit
            buffer_format = framebuf.GS8

        new_buffer = framebuf.FrameBuffer(new_bytes, new_width, new_height, buffer_format)

        x_ratio = orig_img.width / new_width
        y_ratio = orig_img.height / new_height

        for y in range(new_height):
            for x in range(0, new_width, 2 if color_depth == 4 else 1):
                x_1 = min(int(x * x_ratio), orig_img.width - 1)
                y_1 = min(int(y * y_ratio), orig_img.height - 1)

                color1 = orig_img.pixels.pixel(x_1, y_1)
                new_buffer.pixel(x, y, color1)

                if color_depth == 4:
                    x_2 = min(int((x + 1) * x_ratio), orig_img.width - 1)
                    color2 = orig_img.pixels.pixel(x_2, y_1)
                    new_buffer.pixel(x + 1, y, color2)

        return create_image(new_width, new_height, new_buffer, memoryview(new_bytes),
                            orig_img.palette, orig_img.palette_bytes, color_depth)

    def set_camera(self, camera):
        self.camera = camera
        scale_adj = 10  # Increase this value to see bigger sprites when closer to the screen
        self.half_scale_one_dist = int(abs(self.camera.cam_z - scale_adj) / 2)

    # @timed
    def update_sprite(self, sprite, meta, elapsed):
        """The update function only applies to a single sprite at a time, and it is responsible for killing expired
        / out of bounds sprites, as well as updating the x and y draw coordinates based on the 3D position and camera view
        """
        if not sprite.active:
            return False

        if not sprite.speed:
            return False

        #prof.start_profile('update_z_speed')
        new_z = sprite.z + (sprite.speed * elapsed)
        #prof.end_profile('update_z_speed')

        if new_z == sprite.z:
            return False

        sprite.z = int(new_z)
        if sprite.z == 0:
            sprite.z = 1

        if new_z < self.camera.far and not sprite.visible:
            sprite.visible = True

        """ The rest of the calculations are only relevant for visible sprites"""

        if not sprite.visible:
            return True

        if new_z < self.camera.near:
            """Past the near clipping plane"""
            if sprite.active:  # Add this check
                self.pool.release(sprite)
            return False

        scale = self.camera.calculate_scale(sprite.z)

        if scale > 1:
            scale = 1

        sprite.scale = scale

        #prof.start_profile('cam_pos')

        # the scalars below are pretty much trial and error "magic" numbers
        vp_scale = ((self.camera.max_vp_scale) * sprite.scale) + 0.8

        """ We have to adjust for the fact that 3D vertical axis and 2D vertical axis run in opposite directions,
        so we add the sprite height to Y in 3D space before translating to 2D"""

        draw_x, draw_y = self.to_2d(sprite.x, sprite.y, sprite.z, vp_scale=vp_scale)
        # draw_x = (sprite.scale * sprite.x * self.camera.aspect_ratio) + self.camera.half_width
        # draw_y = (sprite.scale * sprite.y * self.camera.aspect_ratio)
        # draw_y = ((self.display.height - self.camera.vp_y) * sprite.scale ) + self.camera.vp_y
        # draw_y = (y * focal_length) / z
        # print(f"draw X: {draw_x} new Draw X: {new_draw_x}")
        # print(f"draw Y: {draw_y} new Draw Y: {new_draw_y}")
         # , _newdraw_y) = self.to_2d(sprite.x, sprite.y, sprite.z, vp_scale=vp_scale)

        # draw_x, draw_y = self.to_2d(sprite.x, sprite.y, sprite.z)

        # print(f"calc draw coords: frameheight: {sprite.frame_height} / height: {height} / sprite.y : {sprite.y}")
        # height = round(sprite.frame_height * sprite.scale)

        #prof.end_profile('cam_pos')

        num_frames = meta.num_frames

        real_z = sprite.z

        #prof.start_profile('get_frame_idx')
        frame_idx = self.get_frame_idx(real_z, int(self.camera.cam_z), num_frames,
                                       self.half_scale_one_dist)
        #prof.end_profile('get_frame_idx')

        sprite.draw_x = int(draw_x)
        sprite.draw_y = int(draw_y)

        sprite.current_frame = frame_idx

        return True

    def update(self, elapsed):
        metas = self.sprite_metadata
        i = 0
        while i < self.pool.active_count:
            sprite = self.pool.sprites[self.pool.active_indices[i]]
            meta = metas[sprite.sprite_type]

            if self.update_sprite(sprite, meta, elapsed):
                self.update_frame(sprite)

            if not sprite.active:
                self.pool.release(sprite)

            i += 1


    def update_frame(self, sprite):
        frame_idx = self.get_frame_idx(int(sprite.z), int(self.camera.cam_z), int(sprite.num_frames),
                                       int(self.half_scale_one_dist))
        sprite.current_frame = frame_idx


    # @timed
    def show_sprite(self, sprite, display: framebuf.FrameBuffer):
        """Draw a single sprite on the display (or several, if multisprites)"""
        sprite_type = sprite.sprite_type

        if not sprite.visible:
            return False

        if sprite.blink:
            sprite.blink_flip = sprite.blink_flip * -1
            if sprite.blink_flip == -1:
                return False

        meta = self.sprite_metadata[sprite_type]
        alpha = meta.alpha_color

        palette = self.sprite_palettes[sprite_type]

        frame_id = sprite.current_frame # 255 ???
        # frame_id = 0

        image = self.sprite_images[sprite_type][frame_id]

        """Actions?"""
        # if sprite_type in self.sprite_actions.keys():
        #     action = self.sprite_actions[sprite_type]
        #     action(display, self.camera, sprite.draw_x, sprite.draw_y, sprite.x, sprite.y, sprite.z, sprite.frame_width)

        start_y = int(sprite.draw_y)
        start_x = sprite.draw_x

        """ Drawing a single image or a row of them? """
        if meta.repeats < 2:
            self.do_blit(x=int(sprite.draw_x), y=start_y, display=display, frame=image.pixels,
                         palette=palette, alpha=alpha)
        else:
            """Draw horizontal clones of this sprite"""
            for i in range(0, meta.repeats):
                x = start_x + (meta.repeat_spacing * sprite.scale * i)
                self.do_blit(x=int(x), y=start_y, display=display, frame=image.pixels,palette=palette, alpha=alpha)

        return True

    # @timed
    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer, frame, palette, alpha=None):
        if alpha is not None:
            display.blit(frame, int(x), int(y), alpha, palette)
        else:
            display.blit(frame, int(x), int(y), -1, palette)

        return True

    # @timed
    def to_2d(self, x, y, z, vp_scale=1):
        camera = self.camera
        if camera:
            return self.camera.to_2d(x, y, z, vp_scale=vp_scale)
        else:
            return x, y

    def _get_frame_idx_short(self, sprite):
        rate = (sprite.z - self.camera.cam_z) / 2
        if rate == 0:
            rate = 0.0001  # Avoid divide by zero
        scale = abs(self.half_scale_one_dist / rate)
        frame_idx = int(scale * sprite.num_frames)
        return max(0, min(frame_idx, sprite.num_frames - 1))

    def set_lane(self, sprite, lane_num, repeats=0, spacing=0):
        return self.grid.set_lane(sprite, lane_num, repeats=0, spacing=0)

    def get_lane(self, sprite):
        """
        Return the lane a sprite is in, based on its X coordinate.
        Values returned are in range [0,1,2,3,4]
        """
        norm_x = (self.lane_width * 2.5) - sprite.x
        # Calculate the center of the sprite
        sprite_center = norm_x - (sprite.frame_width / 2)

        # Calculate which lane the center of the sprite is in
        lane_num = round(sprite_center / self.lane_width)

        # Convert lane to lane_num (add 2 to shift from [-2,-1,0,1,2] to [0,1,2,3,4])
        # lane_num = lane + 2

        # Ensure lane_num is within valid range
        return max(0, min(4, lane_num))

    def set_alpha_color(self, sprite_type: SpriteType):
        """Get the value of the color to be used as an alpha channel when drawing the sprite
        into the display framebuffer """

        if sprite_type.alpha_index in(None, -1):
            return False

        alpha_color = sprite_type.palette.get_bytes(sprite_type.alpha_index)
        sprite_type.alpha_color = alpha_color

    # @timed
    # @micropython.viper
    def get_frame_idx(self, z: int, cam_z: int, num_frames: int, scale_dist: int) -> int:
        """ Given the Z coordinate (depth), find the scaled frame number which best represents the
        size of the object at that distance """

        #prof.start_profile('frame.calc_rate')
        rate: int = int(z - cam_z)
        if (rate >= -1) and (rate <= 1):  # Use a small threshold instead of exactly 0
            rate = 2 if rate >= 0 else -2  # Avoid divide by zero
        #prof.end_profile()

        #prof.start_profile('frame.calc_scale')
        # Use multiplication instead of division
        scale: int = abs(int(scale_dist) * 2)
        if scale > abs(rate):
            scale = abs(rate)
        #prof.end_profile()

        #prof.start_profile('frame.calc_frame_idx')
        temp = abs((rate))
        scale_num = int(scale) * (num_frames)
        frame_idx: int = (scale_num) // int(temp)
        #prof.end_profile()

        # print(f"z: {z} / frame idx: {frame_idx} / num_frames: {num_frames}")

        if frame_idx >= num_frames and num_frames > 0:
            return int(num_frames - 1)
        elif frame_idx < 0:
            return 0
        else:
            return int(frame_idx)

    # @timed
    def show(self, display: framebuf.FrameBuffer):
        """ Display all the active sprites """
        for i in range(self.pool.active_count):
            sprite = self.pool.sprites[self.pool.active_indices[i]]

            if sprite.visible:
                self.show_sprite(sprite, display)

    def start_anims(self):
        """ Start the animations of all the registered sprite types"""
        for _, type in self.sprite_classes.items():
            if type.animations:
                type.start_anim()

    def check_mem(self):
        gc.collect()
        print(micropython.mem_info())


# Usage example
def main():
    print("Not intended to run standalone")
    exit(1)


if __name__ == "__main__":
    main()
