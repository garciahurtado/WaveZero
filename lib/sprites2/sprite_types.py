import asyncio

import sys
from micropython import const
from ucollections import namedtuple
import uctypes

from dump_object import dump_object

POS_TYPE_FAR = const(0)
POS_TYPE_NEAR = const(1)

SPRITE_PLAYER = const(2)
SPRITE_BARRIER_LEFT = const(10)
SPRITE_BARRIER_LEFT_x2 = const(20)
SPRITE_BARRIER_RIGHT = const(30)
SPRITE_BARRIER_RIGHT_x2 = const(35)
SPRITE_BARRIER_RED = const(40)
SPRITE_LASER_ORB = const(50)
SPRITE_LASER_WALL = const(60)
SPRITE_LASER_WALL_x2 = const(70)
SPRITE_LASER_WALL_x5 = const(80)
SPRITE_LASER_WALL_POST = const(90)
SPRITE_WHITE_DOT = const(100)
SPRITE_WHITE_LINE = const(104)
SPRITE_WHITE_LINE_x5 = const(108)
SPRITE_WHITE_LINE_VERT = const(120)
SPRITE_WHITE_LINE_VERT_x6 = const(130)

SPRITE_HOLO_TRI = const(200)

"""
    Flag Bits:
    0: active,
    1: visible,
    2: blink,
    3: blink_flip,
    4: palette_rotate
"""
SPRITE_DATA_LAYOUT = {
    # 4-byte (32-bit) fields
    "scale": uctypes.FLOAT32 | 0,        # 4 bytes at offset 0
    "speed": uctypes.FLOAT32 | 4,        # 4 bytes at offset 4
    "born_ms": uctypes.UINT32 | 8,       # 4 bytes at offset 8

    # 2-byte (16-bit) fields
    "x": uctypes.INT16 | 12,             # 2 bytes at offset 12
    "y": uctypes.INT16 | 14,             # 2 bytes at offset 14
    "z": uctypes.INT16 | 16,             # 2 bytes at offset 16

    # 1-byte (8-bit) fields
    "sprite_type": uctypes.UINT8 | 18,   # 1 byte at offset 18
    "visible": uctypes.UINT8 | 19,       # 1 byte at offset 19
    "active": uctypes.UINT8 | 20,        # 1 byte at offset 20
    "blink": uctypes.UINT8 | 21,         # 1 byte at offset 21
    "pos_type": uctypes.UINT8 | 22,      # 1 byte at offset 22
    "frame_width": uctypes.UINT8 | 23,   # 1 byte at offset 23
    "frame_height": uctypes.UINT8 | 24,  # 1 byte at offset 24
    "current_frame": uctypes.UINT8 | 25, # 1 byte at offset 25
    "num_frames": uctypes.UINT8 | 26,    # 1 byte at offset 26
    "lane_num": uctypes.INT8 | 27,       # 1 byte at offset 27
    "lane_mask": uctypes.UINT8 | 28,     # 1 byte at offset 28
    "draw_x": uctypes.INT8 | 29,         # 1 byte at offset 29
    "draw_y": uctypes.INT8 | 30,         # 1 byte at offset 30
    "flags": uctypes.UINT8 | 31,         # 1 byte at offset 31
}

SPRITE_DATA_SIZE = 32

# Get all field names for outside use
sprite_fields = SPRITE_DATA_LAYOUT.keys()

# Clean this up like we did sprite_manager/create
def create_sprite(
    x=0, y=0, z=0, scale=1.0, speed=0.0, born_ms=0, sprite_type=0,
    visible=False, active=False, blink=False, blink_flip=False,
    pos_type=POS_TYPE_FAR, frame_width=0, frame_height=0,
    current_frame=0, num_frames=0, lane_num=0, lane_mask=0,
    draw_x=0, draw_y=0, width=0, height=0
):
    mem = bytearray(SPRITE_DATA_SIZE)
    sprite = uctypes.struct(uctypes.addressof(mem), SPRITE_DATA_LAYOUT)

    # Set 4-byte fields
    sprite.scale = scale
    sprite.speed = speed
    sprite.born_ms = born_ms

    # Set 2-byte fields
    sprite.x = x
    sprite.y = y
    sprite.z = z

    # Set 1-byte fields
    sprite.sprite_type = sprite_type
    sprite.visible = int(visible)
    sprite.active = int(active)
    sprite.blink = int(blink)
    # sprite.blink_flip = int(blink_flip)
    sprite.pos_type = pos_type
    sprite.frame_width = frame_width
    sprite.frame_height = frame_height
    sprite.current_frame = current_frame
    sprite.num_frames = num_frames
    sprite.lane_num = lane_num
    sprite.lane_mask = lane_mask
    sprite.draw_x = draw_x
    sprite.draw_y = draw_y
    sprite.flags = 0

    return sprite


# Define metadata structure, these values should not change across sprites of this class
class SpriteType:
    # Flag constants
    FLAG_ACTIVE = 1 << 0  # 1
    FLAG_VISIBLE = 1 << 1  # 2
    FLAG_BLINK = 1 << 2  # 4
    FLAG_BLINK_FLIP = 1 << 3  # 8
    FLAG_PALETTE_ROTATE = 1 << 4  # 16

    image_path = None
    speed: int = 0
    width: int = 0
    height: int = 0
    color_depth: int = 4
    palette = None
    rotate_palette = None
    rotate_pal_freq = 5000 # milliseconds
    rotate_pal_last_change = 0
    rotate_pal_index = 0

    alpha_index: int = -1
    alpha_color: int = 0
    frames = None
    num_frames: int = 0
    upscale_width = None
    upscale_height = None
    update_func = None
    render_func = None
    repeats: int = 0
    repeat_spacing: int = 0
    stretch_width: int = 0
    stretch_height: int = 0
    animations = []
    defaults = []

    def __init__(self, **kwargs):
        self.rotate_pal_last_change = 0

        for key in kwargs:
            value = kwargs[key]
            if hasattr(self, key):
                self.defaults.append(key)
                setattr(self, key, value)
            else:
                raise AttributeError(f"Object does not have property named '{key}'")

        if self.width and self.height and not self.num_frames:
            self.num_frames = max(self.width, self.height)

    def reset(self, sprite):
        global sprite_fields

        for key in self.defaults:
            if key in sprite_fields:
                default = getattr(self, key)
                setattr(sprite, key, default)

        # Recalculate number of frames
        if 'width' in self.defaults and 'height' in self.defaults:
            sprite.num_frames = max(self.width, self.height)

    def set_alpha_color(self):
        """Get the value of the color to be used as an alpha channel when drawing the sprite
        into the display framebuffer """

        if self.alpha_index is None:
            return False

        alpha_color = self.palette.get_bytes(self.alpha_index)
        self.alpha_color = alpha_color

    @staticmethod
    def set_flag(sprite, flag, value=True):
        if value:
            sprite.flags |= flag
        else:
            sprite.flags &= ~flag

    @staticmethod
    def unset_flag(sprite, flag):
        return SpriteType.set_flag(sprite, flag, False)

    @staticmethod
    def get_flag(sprite, flag):
        res = bool(sprite.flags & flag)

        return res

    def start_anim(self):
        for anim in self.animations:
            asyncio.run(anim.run())

""" So that we can easily export the flags """
FLAG_ACTIVE = SpriteType.FLAG_ACTIVE
FLAG_VISIBLE = SpriteType.FLAG_VISIBLE
FLAG_BLINK = SpriteType.FLAG_BLINK
FLAG_BLINK_FLIP = SpriteType.FLAG_BLINK_FLIP
FLAG_PALETTE_ROTATE = SpriteType.FLAG_PALETTE_ROTATE
