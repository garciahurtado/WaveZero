import asyncio
import uctypes

from sprites.sprite import Sprite

POS_TYPE_FAR = 0
POS_TYPE_NEAR = 1

SPRITE_PLAYER = 2
SPRITE_BARRIER_LEFT = 10
SPRITE_BARRIER_LEFT_x2 = 20
SPRITE_BARRIER_RIGHT = 30
SPRITE_BARRIER_RIGHT_x2 = 35
SPRITE_BARRIER_RED = 40
SPRITE_LASER_ORB = 50
# SPRITE_LASER_TRI = 55
SPRITE_LASER_WALL = 60
SPRITE_LASER_WALL_x2 = 70
SPRITE_LASER_WALL_x5 = 80
SPRITE_LASER_WALL_POST = 90
SPRITE_WHITE_DOT = 100
SPRITE_WHITE_LINE = 104
SPRITE_WHITE_LINE_x2 = 106
SPRITE_WHITE_LINE_x5 = 108
SPRITE_WHITE_LINE_VERT = 120
SPRITE_WHITE_LINE_VERT_x3 = 125
SPRITE_WHITE_LINE_VERT_x6 = 130
SPRITE_ALIEN_FIGHTER = 135

SPRITE_HOLO_TRI = 200
SPRITE_TEST_SQUARE = 210
SPRITE_TEST_HEART = 220
SPRITE_HEART_SPEED = 225
SPRITE_TEST_GRID = 230
SPRITE_TEST_GRID_SPEED = 240
SPRITE_TEST_PYRAMID = 250
SPRITE_GAMEBOY = 251
SPRITE_CHERRIES = 260

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
    "active": uctypes.UINT8 | 19,        # 1 byte at offset 19
    "pos_type": uctypes.UINT8 | 20,      # 1 byte at offset 20
    "frame_width": uctypes.UINT8 | 21,   # 1 byte at offset 21
    "frame_height": uctypes.UINT8 | 22,  # 1 byte at offset 22
    "current_frame": uctypes.UINT8 | 23, # 1 byte at offset 23
    "num_frames": uctypes.UINT8 | 24,    # 1 byte at offset 24
    "lane_num": uctypes.INT8 | 25,       # 1 byte at offset 25
    "lane_mask": uctypes.UINT8 | 26,     # 1 byte at offset 26
    "draw_x": uctypes.INT8 | 27,         # 1 byte at offset 27
    "draw_y": uctypes.INT8 | 28,         # 1 byte at offset 28
    "floor_y": uctypes.INT8 | 29,        # 1 byte at offset 29
    "color_rot_idx": uctypes.UINT8 | 30, # 1 byte at offset 30
    "flags": uctypes.UINT8 | 31,         # 1 byte at offset 31

    # "x": uctypes.INT32 | 32,           # 2 bytes at offset 12 (half-float)
    # "y": uctypes.INT32 | 35,           # 2 bytes at offset 14 (half-float)
    "dir_x": uctypes.INT16 | 32,         # 2 byte at offset 32
    "dir_y": uctypes.INT16 | 34,         # 2 byte at offset 34
}

SPRITE_DATA_SIZE = 36
"""
self. = 0   # Normalized (-1 to 1) - INT
self. = 0
self. = 0   # Single scalar for magnitude - INT
"""
# Get all field names for outside use
sprite_fields = SPRITE_DATA_LAYOUT.keys()

# Add flags as "virtual" fields which are not stored directly
flags = ['flag_active',
    'flag_visible',
    'flag_blink',
    'flag_blink_flip',
    'flag_palette_rotate',
    'flag_physics']

sprite_fields = list(sprite_fields) + flags

# Clean this up like we did sprite_manager/create
def create_sprite(
    x=0, y=0, z=0, scale=1.0, speed=0.0, born_ms=0, sprite_type=0,
    pos_type=POS_TYPE_FAR, frame_width=0, frame_height=0,
    current_frame=0, num_frames=0, lane_num=0, lane_mask=0
):
    """ Creates a lightweight sprite _instance_"""
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
    sprite.pos_type = pos_type
    sprite.frame_width = frame_width
    sprite.frame_height = frame_height
    sprite.current_frame = current_frame
    sprite.num_frames = num_frames
    sprite.lane_num = lane_num
    sprite.lane_mask = lane_mask
    sprite.flags = 0
    sprite.dir_x = 0
    sprite.dir_y = 0

    return sprite

# Define metadata structure, these values should not change across sprites of this class
class SpriteType:
    # Flag constants
    FLAG_ACTIVE = 1 << 0            # 1
    FLAG_VISIBLE = 1 << 1           # 2
    FLAG_BLINK = 1 << 2             # 4
    FLAG_BLINK_FLIP = 1 << 3        # 8
    FLAG_PALETTE_ROTATE = 1 << 4    # 16
    FLAG_PHYSICS = 1 << 5           # 32

    image_path = None
    speed: int = 0
    width: int = 0
    height: int = 0
    color_depth: int = 4
    palette = None
    rotate_palette = None
    rotate_pal_freq = 1 # seconds
    rotate_pal_index = 0
    rotate_pal_timer = 0

    alpha_index: int = -1
    alpha_color: None
    dot_color = 0x000000
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
    pos_type = Sprite.POS_TYPE_FAR
    flag_physics = False

    def __init__(self, **kwargs):
        self.rotate_pal_last_change = 0

        for key in kwargs:
            value = kwargs[key]
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"Object does not have property named '{key}'")

        if self.width and self.height and not self.num_frames:
            self.num_frames = max(self.width, self.height)

    def reset(self, sprite):
        global sprite_fields
        klass = type(self)
        # SpriteType.set_flag(sprite, FLAG_PHYSICS, True)

        for attr_name in dir(klass):
            """ Only the properties present in both the class as well as the instance
            will be reset (default) """
            if attr_name in sprite_fields:

                attr_value = getattr(klass, attr_name)
                if attr_name.startswith("flag_"):
                    """ All booleans are handled via flags and constants"""
                    flag_const = getattr(SpriteType, attr_name.upper())
                    SpriteType.set_flag(sprite, flag_const, attr_value)
                else:
                    setattr(sprite, attr_name, attr_value)


        # Recalculate number of frames # REWRITE
        # if 'width' in self.defaults and 'height' in self.defaults:
        #     sprite.num_frames = max(self.width, self.height)

    def set_default(self, **kwargs):
        """
        By changing the defaults on the class object, we also change how a reset sprite will be configured
        We can use this method to change the defaults on an existing class without having to subclass it. """

        klass = type(self)
        for key, value in kwargs.items():
            print(f"Sprite Class: {klass}, key: {key}, value: {value}")
            setattr(klass, key, value)


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

    def is_time_to_rotate(self, elapsed):
        if not self.rotate_palette:
            return False

        self.rotate_pal_timer += elapsed
        if self.rotate_pal_timer >= self.rotate_pal_freq:
            self.rotate_pal_timer -= self.rotate_pal_freq
            return True
        return False

""" So that we can easily export the flags """
FLAG_ACTIVE = SpriteType.FLAG_ACTIVE
FLAG_VISIBLE = SpriteType.FLAG_VISIBLE
FLAG_BLINK = SpriteType.FLAG_BLINK
FLAG_BLINK_FLIP = SpriteType.FLAG_BLINK_FLIP
FLAG_PALETTE_ROTATE = SpriteType.FLAG_PALETTE_ROTATE
FLAG_PHYSICS = SpriteType.FLAG_PHYSICS
