import gc

import uctypes
from micropython import const
import micropython

from images.image_loader import ImageLoader
from mpdb.mpdb import Mpdb
from perspective_camera import PerspectiveCamera
from scaler.const import DEBUG, DEBUG_INST, INK_RED, INK_GREEN, DEBUG_CLIP
from scaler.scaler_debugger import printc
from sprites.sprite_draw import SpriteDraw
from sprites.sprite_manager import SpriteManager
from sprites.sprite_physics import SpritePhysics
from sprites.sprite_registry import registry
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
from sprites.sprite_types import to_name
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
    pool: SpritePool = None
    grid = None
    camera: PerspectiveCamera = None
    phy: SpritePhysics = SpritePhysics()
    draw: SpriteDraw = SpriteDraw()
    max_scale = 8

    # Limiting negative drawX and drawY prevents random scaler FREEZES on clipped sprites far off the screen
    min_draw_x = -32
    # min_draw_y = -47 # This seems dependent on the sprite size (sprite height x2)
    min_draw_y = -32

    # @timed
    def __init__(self, display: ssd1331_pio, renderer, max_sprites, camera=None, grid=None):
        super().__init__(display, renderer, max_sprites, camera, grid)
        self.max_scale = None

    def update_sprite(self, sprite, meta, elapsed):
        """ 3D Only. The update function only applies to a single sprite at a time, and it is responsible for
         updating the x and y draw coordinates based on the 3D position and camera view
        """
        visible = types.get_flag(sprite, FLAG_VISIBLE)
        active = types.get_flag(sprite, FLAG_ACTIVE)

        if not active:
            self.pool.release(sprite, meta)
            return False

        """ Apply motion (FIX) """
        if sprite.speed:
            new_z = int(sprite.z + (sprite.speed * elapsed))
        else:
            new_z = sprite.z

        if sprite.z == 0:
            sprite.z = 1    # Smallest possible unit, since our coords are INT16

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

        """1. Get the Scale according to Z for a starting 2D Y. This is where the 3D perspective 'magic' happens"""

        sprite.floor_y, scale = cam.get_scale(sprite.z)
        if math.isinf(scale):
            scale = self.max_scale

        if not scale:
            self.pool.release(sprite, meta)
            return False

        """1. Add the scaled 3D Y (substract) + sprite height from the starting 2D Y. This way we scale both numbers 
        in one single operation"""

        if sprite.y or meta.height:
            """ Draw the sprite at Y - (sprite height) """
            scaled_height = int(scale * (sprite.y + meta.height))
            draw_y = sprite.floor_y - scaled_height
        else:
            draw_y = sprite.floor_y

        sprite.scale = scale

        """ We have to adjust for the fact that 3D vertical axis and 2D vertical axis run in opposite directions,
        so we add the sprite height to Y in 3D space before translating to 2D"""

        draw_x = sprite.x * scale
        draw_x -= cam.vp_x * cam.max_vp_scale * scale * 1.2 # magic number
        draw_x += self.half_width

        num_frames = sprite.num_frames
        name = to_name(sprite)

        if sprite.frame_width < 1 or sprite.frame_height < 1:
            raise ValueError(f"Either width or height are not set *(w:{sprite.frame_width},h:{sprite.frame_height})")

        if num_frames < 1:
            raise ArithmeticError(f"Invalid number of frames: {num_frames} for sprite '{name}'. Are width and height set?")

        frame_idx = self.get_frame_idx(scale, sprite.num_frames)

        sprite.draw_x = int(draw_x)
        sprite.draw_y = int(draw_y)

        # Check for out of bounds x or y
        if sprite.draw_x > self.display.width - 1:
            self.pool.release(sprite, meta)
            return False

        if sprite.draw_y > self.display.height - 1:
            self.pool.release(sprite, meta)
            return False

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
            self.update_sprite(sprite, kind, elapsed)

            # if self.update_sprite(sprite, kind, elapsed):
            #     if kind.is_time_to_rotate(elapsed):
            #         self.rotate_sprite_palette(sprite, kind)

            if not current.next:
                break
            else:
                next_node = current.next

            if not types.get_flag(sprite, FLAG_ACTIVE):
                if DEBUG_INST:
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
        """ Use the renderer to draw a single sprite on the display (or several, if multisprites)"""
        sprite_type = sprite.sprite_type
        meta = registry.sprite_metadata[sprite_type]
        images = registry.sprite_images[sprite_type]
        palette: FramebufferPalette = registry.sprite_palettes[sprite_type]

        if types.get_flag(sprite, FLAG_BLINK):
            blink_flip = types.get_flag(sprite, FLAG_BLINK_FLIP)
            types.set_flag(sprite, FLAG_BLINK_FLIP, blink_flip * -1)

        if sprite.draw_y < self.min_draw_y:
            if DEBUG_CLIP:
                printc(f"SPRITE OUT OF BOUNDS (-Y): {sprite.draw_y}")
            # Consider the sprite OOB
            self.release(sprite, meta)
            return False

        self.renderer.render_sprite(sprite, meta, images, palette)
        return True

    def spawn(self, sprite_type, *args, **kwargs):
        """
        "Spawn" a new sprite. In reality, we are just grabbing one from the pool of available sprites via get() and
        activating it.
        """
        if sprite_type not in registry.sprite_metadata.keys():
            if DEBUG:
                printc("LIST OF KNOWN SPRITE KEYS:")
                print(list(registry.sprite_metadata.keys()))

            raise IndexError(f"Unknown Sprite Type {sprite_type}")

        meta = registry.sprite_metadata[sprite_type]

        # new_sprite.x = new_sprite.y = new_sprite.z = 0
        new_sprite, idx = self.pool.get(sprite_type)
        self.phy.set_pos(new_sprite, 50, 24)

        # Set default dimensions from the metadata *before* applying kwargs
        meta = registry.sprite_metadata[sprite_type]  # Ensure meta is fetched if not already
        if hasattr(meta, 'width'):
            new_sprite.frame_width = meta.width
        if hasattr(meta, 'height'):
            new_sprite.frame_height = meta.height
        if hasattr(meta, 'num_frames'):
            new_sprite.num_frames = meta.num_frames

        # Some properties belong to the "meta" class, so they must be set separately
        if ('width' in kwargs and 'height' in kwargs):
            meta.num_frames = max(kwargs['width'], kwargs['height'])

        # Set user values passed to the create method
        for key in kwargs:
            value = kwargs[key]
            if value is not None:
                setattr(new_sprite, key, value)

        new_sprite.sprite_type = int(sprite_type)

        """ Load image and create scaling frames """
        # if sprite_type not in self.sprite_images.keys():
        #     print(f"First Sprite of Type: {sprite_type} - creating scaled images")
        #
        #     # Choose one depending on the renderer used
        #     # new_img = self.load_img_and_scale(meta, sprite_type, prescale=True)
        #     new_img = self.load_img_and_scale(meta, sprite_type, prescale=True)
        #     self.sprite_images[sprite_type] = new_img

        types.set_flag(new_sprite, FLAG_ACTIVE)
        types.set_flag(new_sprite, FLAG_VISIBLE)
        self.add_inst(new_sprite, sprite_type, idx)
        return new_sprite, idx

    # @timed
    def to_2d(self, x, y, z, vp_scale=1):
        camera = self.camera
        if camera:
            x, y = self.camera.to_2d(x, y, z, vp_scale=vp_scale)

        return x, y

    def show(self, display: framebuf.FrameBuffer):
        """ Display all the active sprites """
        current = self.pool.head

        while current:
            sprite = current.sprite

            if types.get_flag(sprite, FLAG_VISIBLE):
                self.show_sprite(sprite, display)
            current = current.next

    def start_anims(self):
        """ Start the animations of all the registered sprite types"""
        for _, type in self.sprite_classes.items():
            if type.animations:
                type.start_anim()

    def release(self, inst, sprite):
        idx = self.pool.release(inst, sprite)

    def add_inst(self, new_sprite, sprite_type, idx):
        if sprite_type not in self.sprite_inst.keys():
            self.sprite_inst[sprite_type] = []

        self.sprite_inst[sprite_type].append(idx)  # insert in the beginning, so we have correct Z values

        pass
