import gc
from profiler import prof, timed

import uctypes
from micropython import const
import micropython

from images.image_loader import ImageLoader
from perspective_camera import PerspectiveCamera
from scaler.const import DEBUG, INK_GREEN, INK_BLUE, DEBUG_CLIP, DEBUG_INST, INK_RED, INK_YELLOW
from scaler.scaler_debugger import printc
from sprites.sprite_draw import SpriteDraw
from sprites.sprite_physics import SpritePhysics
from sprites.sprite_registry import registry
from sprites.sprite_types import SpriteType
from sprites.sprite_types import SpriteType as types
from sprites.sprite_types import FLAG_VISIBLE, FLAG_ACTIVE, FLAG_BLINK, FLAG_BLINK_FLIP
import framebuf
from colors.framebuffer_palette import FramebufferPalette
import math
from images.indexed_image import Image, create_image
from sprites.sprite_pool_lite import SpritePool
from typing import Dict, List
from profiler import prof
import ssd1331_pio
from utils import pprint

class SpriteManager:
    """
    Base SpriteManager, intented to be extended in display specific classes, like SpriteManager2D and SpriteManager3D.
    This class will not work on its own, since it depends on specific implementations of certain methods.
    """

    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)
    display = None
    bounds = None

    sprite_images: Dict[str, List[Image]] = {}
    sprite_palettes: Dict[str, FramebufferPalette] = {}
    sprite_metadata: Dict[str, SpriteType] = {}
    sprite_classes: Dict[str, callable] = {}
    sprite_actions = {}
    sprite_inst: Dict[str, list] = {}
    half_scale_one_dist = int(0)  # This should be set based on your camera setup
    pools = []
    grid = None
    camera: PerspectiveCamera = None
    phy: SpritePhysics = SpritePhysics()
    draw: SpriteDraw = SpriteDraw()
    renderer = None

    # Limiting negative drawX and drawY prevents random scaler FREEZES on when clipped sprites fall far off the screen
    min_draw_x = -32    # This seems dependent on the sprite size (sprite height x2)
    max_draw_x = None   # will be calculated once the display is initialized
    min_draw_y = -32
    max_draw_y = None
    max_scale = 8

    def __init__(self, display: ssd1331_pio, renderer, max_sprites, camera=None, grid=None):
        self.display = display
        self.renderer = renderer

        self.max_sprites = max_sprites

        self.max_draw_x = display.width
        self.max_draw_y = display.height

        self.grid = grid

        self.check_mem()

        pool = SpritePool(self.max_sprites)
        pool.mgr = self # Remove 2-way dependency
        self.pools.append(pool)
        self.pool = pool # hack for now, until we refactor

        if camera:
            self.set_camera(camera)

        self.half_height = display.height // 2
        self.half_width = display.width // 2
        # self.sprite_actions = Actions(display=display, camera=camera, mgr=self)

    def add_type(self, **kwargs):
        """ SpriteType registry """
        sprite_type = kwargs['sprite_type']

        assert sprite_type, "Cannot add type without sprite_type"

        if DEBUG:
            printc(f"Adding new type {sprite_type}", INK_BLUE)

        """ Look for the actual Python class, or default to SpriteType """
        if 'sprite_class' in kwargs:
            sprite_class: callable = kwargs['sprite_class']
        else:
            sprite_class: callable = SpriteType

        """ Register the new class """
        self.sprite_classes[sprite_type] = sprite_class

        """ These arguments are mandatory """
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
            'stretch_height',
            'dot_color']

        for arg in kwargs:
            if arg not in (defaults + must_have):
                raise AttributeError(f"'{arg}' is not a valid argument for add_type")

        default_args = {key: kwargs.get(key) for key in kwargs}

        """ We dont need these for SpriteType initialization """
        if 'sprite_type' in default_args.keys():
            del default_args['sprite_type']
        if 'sprite_class' in default_args.keys():
            del default_args['sprite_class']

        class_obj = sprite_class(**default_args)
        registry.sprite_metadata[sprite_type] = class_obj
        # self.renderer.add_type(sprite_type, class_obj)

        """ set the default values that will be used when creating new instances (reset) """
        for key in default_args.keys():
            if key in dir(sprite_class):
                value = default_args[key]
                setattr(class_obj, key, value)

        self.sprite_inst[sprite_type] = []

    def set_camera(self, camera):
        self.camera = camera
        scale_adj = 10  # Increase this value to see bigger sprites when closer to the screen
        self.half_scale_one_dist = int(abs(self.camera.cam_z - scale_adj) / 2)

    def rotate_sprite_palette(self, sprite, meta):
        sprite.color_rot_idx = (sprite.color_rot_idx + 1) % len(meta.rotate_palette)

    def to_2d(self, x, y, z, vp_scale=1):
        camera = self.camera
        if camera:
            x, y = self.camera.to_2d(x, y, z, vp_scale=vp_scale)

        return x, y

    def set_lane(self, sprite, lane_num):
        meta = self.get_meta(sprite)
        return self.grid.set_lane(sprite, lane_num, meta.repeats, meta.repeat_spacing)

    def get_meta(self, inst):
        meta = registry.sprite_metadata[inst.sprite_type]
        return meta

    def get_palette(self, sprite_type):
        pal = registry.sprite_palettes[sprite_type]
        return pal

    # @micropython.viper
    def get_frame_idx(self, scale:float, num_frames:int):
        """ Returns a frame index, which is nothing more than the id of the element in num_frames relative to scale,
        which is very easy since scale 1 is 100%, so we can just multiply

        scale = s, num_frames = n:
        frame_idx = s * n
        """
        frame_idx = int(scale * num_frames)
        ret = min(max(frame_idx, 0), num_frames - 1)
        return ret

    def start_anims(self):
        """ Start the animations of all the registered sprite types"""
        for _, type in self.sprite_classes.items():
            if type.animations:
                type.start_anim()

    def release(self, sprite, meta):
        idx = self.pool.release(sprite, meta)
    def check_mem(self):
        gc.collect()
        print(micropython.mem_info())

    def update(self, elapsed):
        """
        elapsed should be in milliseconds
        """
        current = self.pool.head

        # Step 1: Update sprites and collect any that become inactive.
        inactive_sprites_to_release = []
        while current:
            sprite = current.sprite
            kind = self.get_meta(sprite)
            self.update_sprite(sprite, kind, elapsed)

            if not types.get_flag(sprite, FLAG_ACTIVE):
                inactive_sprites_to_release.append((sprite, kind))

            current = current.next

        # Step 2: Now, safely release all the collected inactive sprites.
        if inactive_sprites_to_release:
            if DEBUG_INST:
                printc(f"... releasing {len(inactive_sprites_to_release)} sprites ...", INK_YELLOW)
            for sprite, kind in inactive_sprites_to_release:
                self.pool.release(sprite, kind)

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

    def update_sprite(self, sprite, meta, elapsed):
        raise NotImplementedError("update_sprite() method must be overridden in child class.")

    def show(self, display: framebuf.FrameBuffer):
        """ Display all the active sprites """
        current = self.pool.head

        while current:
            sprite = current.sprite

            if types.get_flag(sprite, FLAG_VISIBLE):
                self.show_sprite(sprite, display)
            current = current.next

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
            return False

        self.renderer.render_sprite(sprite, meta, images, palette)
        return True

    def add_pool(self, sprite_type, size):
        raise NotImplementedError("add_pool() method must be overridden in child class.")

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
        new_sprite.scale = 1
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
        if 'width' in kwargs and 'height' in kwargs:
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
        # self.set_draw_xy(new_sprite, meta.height)
        self.add_inst(new_sprite, sprite_type, idx)
        return new_sprite, idx

    def add_inst(self, new_sprite, sprite_type, idx):
        if sprite_type not in self.sprite_inst.keys():
            self.sprite_inst[sprite_type] = []

        self.sprite_inst[sprite_type].append(idx)  # insert in the beginning, so we have correct Z values

        pass

# Usage example
def main():
    print("Not intended to run standalone")
    exit(1)


if __name__ == "__main__":
    main()
