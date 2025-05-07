import gc

import uctypes
from micropython import const
import micropython

from images.image_loader import ImageLoader
from perspective_camera import PerspectiveCamera
from scaler.const import DEBUG, INK_GREEN, INK_BLUE
from scaler.scaler_debugger import printc
from sprites.sprite_draw import SpriteDraw
from sprites.sprite_physics import SpritePhysics
from sprites.sprite_types import SpriteType
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
from utils import pprint

prof = Profiler()

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

    def __init__(self, display: ssd1331_pio, renderer, max_sprites=0, camera=None, grid=None):
        self.display = display
        self.renderer = renderer

        self.max_sprites = max_sprites
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
        sprite_type = str(kwargs['sprite_type'])

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
        self.renderer.add_type(sprite_type, class_obj)

        self.sprite_metadata[sprite_type] = class_obj

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

    # @timed
    def to_2d(self, x, y, z, vp_scale=1):
        camera = self.camera
        if camera:
            x, y = self.camera.to_2d(x, y, z, vp_scale=vp_scale)

        return x, y

    def set_lane(self, sprite, lane_num):
        meta = self.get_meta(sprite)
        return self.grid.set_lane(sprite, lane_num, meta.repeats, meta.repeat_spacing)

    def get_meta(self, inst):
        meta = self.sprite_metadata[str(inst.sprite_type)]
        return meta

    def get_palette(self, sprite_type):
        sprite_type = str(sprite_type)
        pal = self.sprite_palettes[sprite_type]
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

    def release(self, inst, sprite):
        idx = self.pool.release(inst, sprite)

    def check_mem(self):
        gc.collect()
        print(micropython.mem_info())

    def update(self, elapsed):
        """ Update ALL the sprites that this manager is responsible for """
        if not elapsed:
            return

        kinds = self.sprite_metadata
        current = self.pool.head
        while current:
            sprite = current.sprite
            kind = kinds[str(sprite.sprite_type)]

            if not types.get_flag(sprite, FLAG_ACTIVE):
                self.pool.release(sprite, kind)

            self.update_sprite(sprite, kind, elapsed)

            current = current.next

    def update_sprite(self, sprite, meta, elapsed):
        raise NotImplementedError("update_sprite() method must be overridden in child class.")

    def show(self, display: framebuf.FrameBuffer):
        """ Displays all the sprites in this manager on the screen """
        raise NotImplementedError("show() method must be overridden in child class.")

    def show_sprite(self, sprite, display: framebuf.FrameBuffer):
        raise NotImplementedError("show_sprite() method must be overridden in child class.")

    def add_pool(self, sprite_type, size):
        raise NotImplementedError("add_pool() method must be overridden in child class.")

    def spawn(self, sprite_type, *args, **kwargs):
        raise NotImplementedError("spawn() method must be overridden in child class.")

# Usage example
def main():
    print("Not intended to run standalone")
    exit(1)


if __name__ == "__main__":
    main()
