import gc

import uctypes
from micropython import const
import micropython

from dump_object import dump_object
from images.image_loader import ImageLoader
from perspective_camera import PerspectiveCamera
from sprites2.sprite_types import SpriteType, SPRITE_DATA_LAYOUT
from sprites2.sprite_types import SpriteType as types
from sprites2.sprite_types import FLAG_VISIBLE, FLAG_ACTIVE, FLAG_BLINK, FLAG_BLINK_FLIP, FLAG_PALETTE_ROTATE
import framebuf
from color.framebuffer_palette import FramebufferPalette
import math
from images.indexed_image import Image, create_image
from sprites2.sprite_pool_lite import SpritePool
from typing import Dict, List
from profiler import Profiler as prof
import ssd1331_pio

class SpriteManager:
    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)
    display = None

    sprite_images: Dict[str, List[Image]] = {}
    sprite_palettes: Dict[str, FramebufferPalette] = {}
    sprite_metadata: Dict[str, SpriteType] = {}
    sprite_classes: Dict[int, callable] = {}
    sprite_actions = {}
    sprites_by_type: Dict[str, list] = {}
    half_scale_one_dist = int(0)  # This should be set based on your camera setup
    add_frames = 0  # Number of upscaled frames to add (scale > 1)
    pool = None
    grid = None
    camera: PerspectiveCamera = None

    def __init__(self, display: ssd1331_pio, max_sprites, camera=None, grid=None):
        self.display = display

        self.max_sprites = max_sprites
        self.grid = grid

        self.check_mem()
        self.pool = SpritePool(self.max_sprites)

        if camera:
            self.set_camera(camera)

        self.half_height = display.height // 2
        self.half_width = display.width // 2

    def add_type(self, **kwargs):
        """ These arguments are mandatory """
        sprite_type = kwargs['sprite_type']

        if 'sprite_class' in kwargs:
            sprite_class: callable = kwargs['sprite_class']
        else:
            sprite_class: callable = SpriteType

        """ Register the new class """
        self.sprite_classes[sprite_type] = sprite_class

        must_have = ['sprite_type', 'sprite_class']
        defaults = [
            'image_path',
            'speed',
            'width',
            'height',
            'color_depth',
            'palette',
            'alpha_index',
            'alpha_color',
            'repeats',
            'repeat_spacing',
            'stretch_width',
            'stretch_height']

        for arg in kwargs:
            if arg not in (defaults + must_have):
                raise AttributeError(f"'{arg}' is not a valid argument for add_type")

        default_args = {key: kwargs.get(key) for key in kwargs}

        """ We dont need these for SpriteType initialization """
        if 'sprite_type' in default_args.keys():
            del default_args['sprite_type']
        if 'sprite_class' in default_args.keys():
            del default_args['sprite_class']

        type_obj = sprite_class(**default_args)

        for key in default_args.keys():
            if key in dir(sprite_class):
                value = default_args[key]
                setattr(type_obj, key, value)

        self.sprite_metadata[sprite_type] = type_obj
        self.sprites_by_type[sprite_type] = []

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

    def create(self, sprite_type, *args, **kwargs):
        if sprite_type not in self.sprite_classes.keys():
            raise IndexError(f"Sprite type {sprite_type} is not defined")

        prof.start_profile('mgr.set_initial_vars')
        meta = self.sprite_metadata[sprite_type]
        prof.end_profile('mgr.set_initial_vars')

        prof.start_profile('mgr.pool_get')
        # new_sprite.x = new_sprite.y = new_sprite.z = 0
        new_sprite, idx = self.pool.get(sprite_type, meta)
        prof.end_profile('mgr.pool_get')

        self.sprites_by_type[sprite_type].append(idx)

        # Set user values passed to the create method
        prof.start_profile('mgr.set_kwargs')

        for key in kwargs:
            value = kwargs[key]
            if value is not None:
                setattr(new_sprite, key, value)
        prof.end_profile('mgr.set_kwargs')

        # Some properties belong to the meta class, so they must be set separately

        if ('width' in kwargs and 'height' in kwargs):
            meta.num_frames = max(kwargs['width'], kwargs['height'])

        new_sprite.sprite_type = sprite_type

        """ Load image and create scaling frames """
        if sprite_type not in self.sprite_images:
            print(f"sprite type: {sprite_type} - creating scaled images")
            prof.start_profile('mgr.create_images')
            new_img = self.load_img_and_scale(meta, sprite_type)
            self.sprite_images[sprite_type] = new_img
            prof.end_profile('mgr.create_images')

        prof.start_profile('mgr.set_flags')
        types.set_flag(new_sprite, FLAG_ACTIVE)
        types.set_flag(new_sprite, FLAG_VISIBLE)
        prof.end_profile('mgr.set_flags')

        return new_sprite, idx

    def load_img_and_scale(self, meta, sprite_type):
        orig_img = ImageLoader.load_image(meta.image_path, meta.width, meta.height)
        if isinstance(orig_img, list):
            orig_img = orig_img[0]

        frames = []
        num_frames = meta.num_frames

        for f in range(1, num_frames):
            scale = f / num_frames # Avoid division by zero

            new_width = math.ceil(meta.width * scale)
            new_height = math.ceil(meta.height * scale)

            new_frame = self.scale_frame(orig_img, new_width, new_height, meta.color_depth)
            frames.append(new_frame)

        frames.append(orig_img)  # Add original image as the last frame

        """Do we need to add upscale frames? (scale > 1)"""
        if ((meta.stretch_width and meta.stretch_width > meta.width) or
            (meta.stretch_height and meta.stretch_height > meta.height)):

            width_gap = meta.stretch_width - meta.width
            height_gap = meta.stretch_height - meta.height

            add_width_frames = 0
            add_height_frames = 0

            if width_gap > height_gap:
                add_width_frames = max(width_gap, height_gap)
            else:
                add_height_frames = max(width_gap, height_gap)

            for f in range(0, add_width_frames):
                pass

            for f in range(0, add_height_frames):
                pass

        self.sprite_palettes[sprite_type] = orig_img.palette
        meta.palette = orig_img.palette
        self.set_alpha_color(meta)

        return frames

    def scale_frame(self, orig_img, new_width, new_height, color_depth):
        if color_depth not in [4, 8]:
            raise ValueError(f"Unsupported color depth: {color_depth}")

        if new_width % 2 and color_depth == 4:  # Width must be even for 4-bit images
            new_width += 1

        byte_size = (new_width * new_height) // (8 // color_depth)
        new_bytes = bytearray(byte_size)
        new_bytes_addr = uctypes.addressof(new_bytes)

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

        return create_image(new_width, new_height, new_buffer, new_bytes, new_bytes_addr,
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
        visible = types.get_flag(sprite, FLAG_VISIBLE)
        active = types.get_flag(sprite, FLAG_ACTIVE)

        if not active:
            return False

        if sprite.speed:
            prof.start_profile('mgr.update_z_speed')
            new_z = int(sprite.z + (sprite.speed * elapsed))
            prof.end_profile('mgr.update_z_speed')
        else:
            new_z = sprite.z

        if sprite.z == 0:
            sprite.z = 1

        cam = self.camera

        if sprite.z < cam.far and not visible:
            types.set_flag(sprite, FLAG_VISIBLE)
        elif new_z == sprite.z and sprite.scale:
            """ We check for sprite.scale to give static sprites that just spawned a change to calculate its render 
            attributes once. """
            """ Nothing more needs to change, since it hasn't moved"""
            return False
        else:
            sprite.z = new_z

        """ The rest of the calculations are only relevant for visible sprites within the frustrum"""
        if not visible:
            return True

        if sprite.z < cam.near:
            """Past the near clipping plane"""
            self.pool.release(sprite, meta)
            return False

        """1. Get the Scale according to Z for a starting 2D Y"""
        prof.start_profile('mgr.sprite_scale')
        sprite.floor_y, scale = cam.get_scale(sprite.z)
        prof.end_profile('mgr.sprite_scale')


        """1. Add the scaled 3D Y (substract) + sprite height from the starting 2D Y. This way we scale both numbers 
        in one single operation"""
        prof.start_profile('mgr.sprite_height_adjust')
        #
        if sprite.y or meta.height:
            """ Draw the sprite at Y - (sprite height) """
            scaled_height = int(scale * (sprite.y + meta.height))
            draw_y = sprite.floor_y - scaled_height
        else:
            draw_y = sprite.floor_y

        prof.end_profile('mgr.sprite_height_adjust')

        # @TODO
        # if draw_y < 0:
        #     print(f"NEGATIVE DRAW Y: {draw_y} / sc: {scale} / z: {sprite.z} / height: {meta.height} ")

        sprite.scale = scale

        # the scalars below are pretty much trial and error "magic" numbers
        # vp_scale = ((cam.max_vp_scale) * sprite.scale)

        """ We have to adjust for the fact that 3D vertical axis and 2D vertical axis run in opposite directions,
        so we add the sprite height to Y in 3D space before translating to 2D"""

        prof.start_profile('mgr.sprite_scale_post')
        draw_x = sprite.x * scale
        draw_x -= cam.vp_x * cam.max_vp_scale * scale * 1.2 # magic number
        draw_x += self.half_width
        prof.end_profile('mgr.sprite_scale_post')

        prof.start_profile('mgr.get_frame_idx')

        frame_idx = self.get_frame_idx(scale, sprite.num_frames)
        prof.end_profile('mgr.get_frame_idx')

        sprite.draw_x = int(draw_x)
        sprite.draw_y = int(draw_y)

        sprite.current_frame = frame_idx

        return True

    def update(self, elapsed):
        metas = self.sprite_metadata
        current = self.pool.head
        while current:
            prof.start_profile('mgr.update()')
            sprite = current.sprite
            meta = metas[sprite.sprite_type]

            if self.update_sprite(sprite, meta, elapsed):
                if meta.is_time_to_rotate(elapsed):
                    self.rotate_sprite_palette(sprite, meta)

            next_node = current.next

            if not types.get_flag(sprite, FLAG_ACTIVE):
                self.pool.release(sprite, meta)

            current = next_node

            prof.end_profile('mgr.update()')

        """ Check for and update actions for all sprite types"""
        if self.sprite_actions:

            for sprite_type in self.sprite_actions.keys():
                sprites = self.sprites_by_type[sprite_type]
                actions = self.sprite_actions[sprite_type]
                for action in actions:
                    action.update(sprites, elapsed)

                action(self.camera, sprite.draw_x, sprite.draw_y, sprite.x, sprite.y, sprite.z, sprite.frame_width)

    def rotate_sprite_palette(self, sprite, meta):
        sprite.color_rot_idx = (sprite.color_rot_idx + 1) % len(meta.rotate_palette)

    # @timed
    def show_sprite(self, sprite, display: framebuf.FrameBuffer):
        """Draw a single sprite on the display (or several, if multisprites)"""
        sprite_type = sprite.sprite_type

        if not types.get_flag(sprite, FLAG_VISIBLE):
            return False

        if types.get_flag(sprite, FLAG_BLINK):
            blink_flip = types.get_flag(sprite, FLAG_BLINK_FLIP)
            types.set_flag(sprite, FLAG_BLINK_FLIP, blink_flip * -1)

        meta = self.sprite_metadata[sprite_type]

        alpha = meta.alpha_color
        palette:FramebufferPalette = self.sprite_palettes[sprite_type]

        # if meta.rotate_palette:
        #     color = meta.rotate_palette[sprite.color_rot_idx]
        #     # Apply the rotated color to the sprite's palette
        #     palette.set_int(0, color)

        frame_id = sprite.current_frame # 255 sometimes ???
        image = self.sprite_images[sprite_type][frame_id]

        start_y = sprite.draw_y
        start_x = sprite.draw_x

        """ Drawing a single image or a row of them? repeats 0 and 1 mean the same thing (one image) """

        if meta.repeats < 2:
            self.do_blit(x=start_x, y=start_y, display=display, frame=image.pixels,
                         palette=palette, alpha=alpha)
        else:
            """Draw horizontal clones of this sprite"""
            for i in range(0, meta.repeats):
                x = start_x + (meta.repeat_spacing * sprite.scale * i)
                self.do_blit(x=round(x), y=start_y, display=display, frame=image.pixels,palette=palette, alpha=alpha)

        return True

    # @timed
    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer, frame, palette, alpha=None):
        if alpha is not None:
            display.blit(frame, x, y, alpha, palette)
        else:
            display.blit(frame, x, y, -1, palette)

        return True

    # @timed
    def to_2d(self, x, y, z, vp_scale=1):
        print(f"MGR calling 2D X/Y/Z: {x} {y} {z}")
        prof.start_profile('mgr.to_2d')

        camera = self.camera
        if camera:
            x, y = self.camera.to_2d(x, y, z, vp_scale=vp_scale)

        prof.end_profile('mgr.to_2d')
        return x, y


    def set_lane(self, sprite, lane_num):
        meta = self.get_meta(sprite)

        return self.grid.set_lane(sprite, lane_num, meta.repeats, meta.repeat_spacing)

    def get_meta(self, sprite):
        meta = self.sprite_metadata[sprite.sprite_type]
        return meta

    def set_alpha_color(self, sprite_type: SpriteType):
        """Get the value of the color to be used as an alpha channel when drawing the sprite
        into the display framebuffer """

        if sprite_type.alpha_index in(None, -1):
            return False

        alpha_color = sprite_type.palette.get_bytes(sprite_type.alpha_index)
        sprite_type.alpha_color = alpha_color

    # @micropython.viper
    def get_frame_idx(self, scale:float, num_frames:int):
        if num_frames <= 0:
            raise ArithmeticError(f"Invalid number of frames: {num_frames}. Are width and height set?")

        prof.start_profile('mgr.get_frame_idx.mult')
        frame_idx = int(scale * num_frames)
        prof.end_profile('mgr.get_frame_idx.mult')
        prof.start_profile('mgr.get_frame_idx.min')
        ret = min(max(frame_idx, 0), num_frames - 1)
        prof.end_profile('mgr.get_frame_idx.min')

        return ret


    # @timed
    def show(self, display: framebuf.FrameBuffer):
        """ Display all the active sprites """
        current = self.pool.head

        while current:
            sprite = current.sprite
            #
            # print(f"VISIBLE: {SpriteType.get_flag(sprite, SpriteType.FLAG_VISIBLE)}")
            # print(f"ACTIVE:  {SpriteType.get_flag(sprite, SpriteType.FLAG_ACTIVE)}")

            if types.get_flag(sprite, FLAG_VISIBLE):
                self.show_sprite(sprite, display)
            current = current.next

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
