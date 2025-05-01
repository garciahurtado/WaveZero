import gc

import uctypes
from micropython import const
import micropython

from images.image_loader import ImageLoader
from mpdb.mpdb import Mpdb
from perspective_camera import PerspectiveCamera
from scaler.const import DEBUG, DEBUG_INST, INK_RED
from scaler.scaler_debugger import printc
from sprites.sprite_draw import SpriteDraw
from sprites.sprite_manager import SpriteManager
from sprites.sprite_physics import SpritePhysics
from sprites.sprite_types import SpriteType, FLAG_PHYSICS
from sprites.sprite_types import SpriteType as types
from sprites.sprite_types import FLAG_VISIBLE, FLAG_ACTIVE, FLAG_BLINK, FLAG_BLINK_FLIP
import framebuf
from colors.framebuffer_palette import FramebufferPalette
import math
from images.indexed_image import Image, create_image
from sprites.sprite_pool_lite import SpritePool
from typing import Dict, List
from profiler import Profiler
import ssd1331_pio
from framebuf import FrameBuffer

from utils import pprint, pprint_pure

prof = Profiler()

class SpriteManager3D(SpriteManager):
    """
    This sprite manager extends the base manager to add support for 3D sprites, which have a Z coordinate, and a
    set of frames that can be used to simulate scaled sizes at a distance
    """
    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)

    half_scale_one_dist = int(0)  # This should be set based on your camera setup
    add_frames = 0  # Number of upscaled frames to add (scale > 1)
    pool = None
    grid = None
    camera: PerspectiveCamera = None
    phy: SpritePhysics = SpritePhysics()
    draw: SpriteDraw = SpriteDraw()

    def load_img_and_scale(self, meta, sprite_type):
        orig_img = ImageLoader.load_image(
            filename=meta.image_path,
            frame_width=meta.width,
            frame_height=meta.height,
            with_downscales=True
        )

        if isinstance(orig_img, list):
            orig_img = orig_img[0]

        frames = []
        num_frames = meta.num_frames
        num_frames = 10 # DEBUG!!

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

    # @timed
    def update_sprite(self, sprite, meta, elapsed):
        """ 3D Only. The update function only applies to a single sprite at a time, and it is responsible for
         updating the x and y draw coordinates based on the 3D position and camera view
        """
        visible = types.get_flag(sprite, FLAG_VISIBLE)
        active = types.get_flag(sprite, FLAG_ACTIVE)

        if not active:
            if DEBUG_INST:
                print(" -- Sprite not active! --")
            return False

        """ Apply motion (FIX) """
        if sprite.speed:
            new_z = int(sprite.z + (sprite.speed * elapsed))
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

        sprite.floor_y, scale = cam.get_scale(sprite.z)

        """1. Add the scaled 3D Y (substract) + sprite height from the starting 2D Y. This way we scale both numbers 
        in one single operation"""


        if sprite.y or meta.height:
            """ Draw the sprite at Y - (sprite height) """
            scaled_height = int(scale * (sprite.y + meta.height))
            draw_y = sprite.floor_y - scaled_height
        else:
            draw_y = sprite.floor_y

        # @TODO
        # if draw_y < 0:
        #     print(f"NEGATIVE DRAW Y: {draw_y} / sc: {scale} / z: {sprite.z} / height: {meta.height} ")

        sprite.scale = scale

        # the scalars below are pretty much trial and error "magic" numbers
        # vp_scale = ((cam.max_vp_scale) * sprite.scale)

        """ We have to adjust for the fact that 3D vertical axis and 2D vertical axis run in opposite directions,
        so we add the sprite height to Y in 3D space before translating to 2D"""


        draw_x = sprite.x * scale
        draw_x -= cam.vp_x * cam.max_vp_scale * scale * 1.2 # magic number
        draw_x += self.half_width

        frame_idx = self.get_frame_idx(scale, sprite.num_frames)

        sprite.draw_x = int(draw_x)
        sprite.draw_y = int(draw_y)

        sprite.current_frame = frame_idx

        return True

    def update(self, elapsed):
        """
        ellapsed should be in milliseconds
        """
        # DEPRECATE (but not deprecated yet): this method should be deprecated and useful functionality replicated

        kinds = self.sprite_metadata
        current = self.pool.head

        while current:
            sprite = current.sprite
            sprite_id = sprite.sprite_type
            kind = self.get_meta(sprite)

            if self.update_sprite(sprite, kind, elapsed):
                if kind.is_time_to_rotate(elapsed):
                    self.rotate_sprite_palette(sprite, kind)

            if not current.next:
                break

            next_node = current.next

            if not types.get_flag(sprite, FLAG_ACTIVE):
                printc("!!!SPRITE NOT ACTIVE, RELEASING!!!", INK_RED)
                self.pool.release(sprite, kind)

            current = next_node

        """ Check for and update actions for all sprite types"""

        if self.sprite_actions:

            for sprite_type in self.sprite_actions.keys():
                inst = self.sprite_inst[sprite_type]
                actions = self.sprite_actions.for_sprite(sprite_type)
                for action in actions:
                    func = getattr(self.sprite_actions, __name__)
                    # func.__self__ =
                    func(inst, elapsed)

                    # action(self.camera, sprite.draw_x, sprite.draw_y, sprite.x, sprite.y, sprite.z, sprite.frame_width)

    def rotate_sprite_palette(self, sprite, meta):
        sprite.color_rot_idx = (sprite.color_rot_idx + 1) % len(meta.rotate_palette)

    # @timed
    def show_sprite(self, sprite, display: framebuf.FrameBuffer):
        """Draw a single sprite on the display (or several, if multisprites)"""
        # sprite_type = sprite.sprite_id
        sprite_type = sprite.sprite_type

        if not types.get_flag(sprite, FLAG_VISIBLE):
            if DEBUG:
                print(">>> SPRITE IS INVISIBLE!!!")
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

        start_x = sprite.draw_x
        start_y = sprite.draw_y

        """ Drawing a single image or a row of them? repeats 0 and 1 mean the same thing (one image) """

        if meta.repeats < 2:
            self.do_blit(x=start_x, y=start_y, display=display, frame=image.pixels,
                         palette=palette, alpha=alpha)
        else:
            """Also draw horizontal clones of this sprite, if needed """
            for i in range(0, meta.repeats):
                x = start_x + (meta.repeat_spacing * sprite.scale * i)
                self.do_blit(x=round(x), y=start_y, display=display, frame=image.pixels,palette=palette, alpha=alpha)

        return True

    def spawn(self, sprite_type, *args, **kwargs):
        """
        "Spawn" a new sprite. In reality, we are just grabbing one from the pool of available sprites via get() and
        activating it.
        """
        if sprite_type not in self.sprite_classes.keys():
            raise IndexError(f"Unknown Sprite Type {sprite_type}")

        meta = self.sprite_metadata[sprite_type]

        # new_sprite.x = new_sprite.y = new_sprite.z = 0
        new_sprite, idx = self.pool.get(sprite_type, meta)
        self.phy.set_pos(new_sprite, 50, 24)

        self.sprite_inst[sprite_type].append(idx) # insert in the beginning, so we have correct Z values

        # Set user values passed to the create method
        for key in kwargs:
            value = kwargs[key]
            if value is not None:
                setattr(new_sprite, key, value)

        # Some properties belong to the "meta" class, so they must be set separately
        if ('width' in kwargs and 'height' in kwargs):
            meta.num_frames = max(kwargs['width'], kwargs['height'])

        new_sprite.sprite_type = sprite_type

        """ Load image and create scaling frames """
        if sprite_type not in self.sprite_images.keys():
            print(f"First Sprite of Type: {sprite_type} - creating scaled images")

            new_img = self.load_img_and_scale(meta, sprite_type)
            self.sprite_images[sprite_type] = new_img

        types.set_flag(new_sprite, FLAG_ACTIVE)
        types.set_flag(new_sprite, FLAG_VISIBLE)

        return new_sprite, idx

    # @timed
    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer, frame, palette, alpha=None):
        if alpha is not None:
            display.blit(frame, x, y, alpha, palette)
        else:
            display.blit(frame, x, y, -1, palette)

        return True

    # @timed
    def to_2d(self, x, y, z, vp_scale=1):
        camera = self.camera
        if camera:
            x, y = self.camera.to_2d(x, y, z, vp_scale=vp_scale)

        return x, y

    # @micropython.viper
    def get_frame_idx(self, scale:float, num_frames:int):
        return 0 # debugging / deprecate

        if num_frames <= 0:
            raise ArithmeticError(f"Invalid number of frames: {num_frames}. Are width and height set?")

        frame_idx = int(scale * num_frames)
        ret = min(max(frame_idx, 0), num_frames - 1)
        return ret

    def show(self, display: framebuf.FrameBuffer):
        """ Display all the active sprites """
        current = self.pool.head

        while current:
            sprite = current.sprite

            if types.get_flag(sprite, FLAG_VISIBLE):
                # sprite.sprite_id = sprite.sprite_type
                self.show_sprite(sprite, display)
            current = current.next

    def start_anims(self):
        """ Start the animations of all the registered sprite types"""
        for _, type in self.sprite_classes.items():
            if type.animations:
                type.start_anim()

    def release(self, inst, sprite):
        idx = self.pool.release(inst, sprite)
