import gc

import uctypes
from micropython import const
import micropython

from images.image_loader import ImageLoader
from mpdb.mpdb import Mpdb
from perspective_camera import PerspectiveCamera
from scaler.const import DEBUG, DEBUG_INST, INK_RED, INK_GREEN, DEBUG_CLIP, INK_CYAN, DEBUG_UPDATE
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
        cam = self.camera

        if not active:
            self.pool.release(sprite, meta)
            return False

        """ Apply motion (FIX) """
        if sprite.speed:
            new_z = int(sprite.z + (sprite.speed * elapsed))
        else:
            new_z = sprite.z

        if sprite.z < cam.near:
            """Past the near clipping plane"""
            self.pool.release(sprite, meta)
            return False

        if sprite.z == 0:
            sprite.z = 1    # Smallest possible unit, since our coords are INT16

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

        """1. Get the Scale according to Z for a starting 2D Y. This is where the 3D perspective 'magic' happens"""

        sprite.floor_y, scale = cam.get_scale(sprite.z)
        if math.isinf(scale):
            scale = self.max_scale

        if not scale:
            self.pool.release(sprite, meta)
            return False

        self.set_draw_xy(sprite, meta.height, scale)

        # Check for out of bounds x or y. This should probably be integrated with the clipping logic in sprite_scaler

        if sprite.draw_x < self.min_draw_x:
            self.pool.release(sprite, meta)
            return False
        if sprite.draw_x > self.display.width - 1:
            self.pool.release(sprite, meta)
            return False

        """ Check that draw_y is within bounds """
        if sprite.draw_y < self.min_draw_y:
            self.pool.release(sprite, meta)
            return False
        elif sprite.draw_y > self.display.height - 1:
            self.pool.release(sprite, meta)
            return False

        """ Add some useful debugging statements """
        if DEBUG_UPDATE:
            printc(f"SPRITE 3D UPDATE :", INK_CYAN)
            print(f"draw_x: {sprite.draw_x}, draw_y: {sprite.draw_y}")
            print(f"scale: {sprite.scale}")
            print(f"speed: {sprite.speed}")
            print(f"elapsed: {elapsed}")
            print(f"active: {active}")
            print(f"visible: {visible}")

        return True

    def set_draw_xy(self, sprite, sprite_height, scale: float = 1):
        """ Perform the 3D perspective calculations to get the display x,y from the instance's x,y,z,
        using the camera for perspective configuration """
        cam = self.camera

        """1. Add the scaled 3D Y (substract) + sprite height from the starting 2D Y. This way we scale both numbers 
            in one single operation"""
        if sprite.y or sprite_height:
            """ Draw the sprite at Y - (sprite height) """
            scaled_height = int(scale * (sprite.y + sprite_height))
            draw_y = sprite.floor_y - scaled_height
        else:
            draw_y = sprite.floor_y
        sprite.scale = scale

        """ We have to adjust for the fact that 3D vertical axis and 2D vertical axis run in opposite directions,
            so we add the sprite height to Y in 3D space before translating to 2D"""
        draw_x = sprite.x * scale
        draw_x -= cam.vp_x * cam.max_vp_scale * scale * 1.2  # magic number
        draw_x += self.half_width
        num_frames = sprite.num_frames
        name = to_name(sprite)

        if sprite.frame_width < 1 or sprite.frame_height < 1:
            raise ValueError(f"Either width or height are not set *(w:{sprite.frame_width},h:{sprite.frame_height})")
        if num_frames < 1:
            raise ArithmeticError(
                f"Invalid number of frames: {num_frames} for sprite '{name}'. Are width and height set?")

        frame_idx = self.get_frame_idx(scale, sprite.num_frames)
        sprite.current_frame = frame_idx
        sprite.draw_x = int(draw_x)
        sprite.draw_y = int(draw_y)

    def rotate_sprite_palette(self, sprite, meta):
        sprite.color_rot_idx = (sprite.color_rot_idx + 1) % len(meta.rotate_palette)

    # @timed
    def to_2d(self, x, y, z, vp_scale=1):
        camera = self.camera
        if camera:
            x, y = self.camera.to_2d(x, y, z, vp_scale=vp_scale)

        return x, y

    def start_anims(self):
        """ Start the animations of all the registered sprite types"""
        for _, type in self.sprite_classes.items():
            if type.animations:
                type.start_anim()

    def release(self, inst, sprite):
        idx = self.pool.release(inst, sprite)

