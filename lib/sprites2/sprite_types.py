from micropython import const
from ucollections import namedtuple
import uctypes

POS_TYPE_FAR = const(0)
POS_TYPE_NEAR = const(1)

SPRITE_PLAYER = const(0)
SPRITE_BARRIER_LEFT = const(1)
SPRITE_BARRIER_RIGHT = const(2)
SPRITE_BARRIER_RED = const(3)
SPRITE_LASER_ORB = const(4)
SPRITE_LASER_WALL = const(5)
SPRITE_LASER_WALL_POST = const(6)
SPRITE_WHITE_DOT = const(7)
SPRITE_HOLO_TRI = const(8)

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
    "blink_flip": uctypes.UINT8 | 22,    # 1 byte at offset 22
    "pos_type": uctypes.UINT8 | 23,      # 1 byte at offset 23
    "frame_width": uctypes.UINT8 | 24,   # 1 byte at offset 24
    "frame_height": uctypes.UINT8 | 25,  # 1 byte at offset 25
    "current_frame": uctypes.UINT8 | 26, # 1 byte at offset 26
    "num_frames": uctypes.UINT8 | 27,    # 1 byte at offset 27
    "lane_num": uctypes.INT8 | 28,       # 1 byte at offset 28
    "lane_mask": uctypes.UINT8 | 29,     # 1 byte at offset 29
    "draw_x": uctypes.INT8 | 30,         # 1 byte at offset 30
    "draw_y": uctypes.INT8 | 31,         # 1 byte at offset 31
}

SPRITE_DATA_SIZE = 32

def create_sprite(
    x=0, y=0, z=0, scale=1.0, speed=0.0, born_ms=0, sprite_type=0,
    visible=False, active=False, blink=False, blink_flip=False,
    pos_type=POS_TYPE_FAR, frame_width=0, frame_height=0,
    current_frame=0, num_frames=0, lane_num=0, lane_mask=0,
    draw_x=0, draw_y=0
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
    sprite.blink_flip = int(blink_flip)
    sprite.pos_type = pos_type
    sprite.frame_width = frame_width
    sprite.frame_height = frame_height
    sprite.current_frame = current_frame
    sprite.num_frames = num_frames
    sprite.lane_num = lane_num
    sprite.lane_mask = lane_mask
    sprite.draw_x = draw_x
    sprite.draw_y = draw_y

    return sprite


# Define metadata structure, these values should not change across sprites of this class
class SpriteType:
    image_path = None
    speed: int = 0
    width: int = 0
    height: int = 0
    color_depth: int = 0
    palette = None
    rotate_palette = None
    rotate_pal_freq = 5000 # milliseconds
    rotate_pal_last_change = 0
    rotate_pal_index = 0

    alpha_index: int = None
    alpha_color: int = 0
    frames = None
    num_frames: int = 0
    update_func = None
    render_func = None
    repeats: int = 0
    repeat_spacing: int = 0

    def __init__(self, **kwargs):
        self.rotate_pal_last_change = 0

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"Object does not have property named '{key}'")

    def set_alpha_color(self):
        """Get the value of the color to be used as an alpha channel when drawing the sprite
        into the display framebuffer """

        if self.alpha_index is None:
            return False

        alpha_color = self.palette.get_bytes(self.alpha_index)
        self.alpha_color = alpha_color

