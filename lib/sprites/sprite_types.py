from micropython import const
from ucollections import namedtuple
import uctypes

POS_TYPE_FAR = const(0)
POS_TYPE_NEAR = const(1)

SPRITE_DATA_LAYOUT = {
    "sprite_type": uctypes.UINT8 | 0,
    "x": uctypes.INT16 | 2,
    "y": uctypes.INT16 | 4,
    "z": uctypes.INT16 | 6,
    "speed": uctypes.FLOAT32 | 8,
    "visible": uctypes.UINT8 | 12,
    "active": uctypes.UINT8 | 13,
    "blink": uctypes.UINT8 | 14,
    "blink_flip": uctypes.UINT8 | 15,
    "pos_type": uctypes.UINT8 | 16,
    "frame_width": uctypes.UINT8 | 17,
    "frame_height": uctypes.UINT8 | 18,
    "current_frame": uctypes.UINT8 | 19,
    "lane_num": uctypes.UINT8 | 20,
    "draw_x": uctypes.INT8 | 21,
    "draw_y": uctypes.INT8 | 22,
    "num_frames": uctypes.UINT8 | 23,
    "born_ms": uctypes.UINT32 | 24,
}

def create_sprite(
    sprite_type=0,
    x=0,
    y=0,
    z=0,
    speed=0,
    visible=False,
    active=False,
    blink=False,
    blink_flip=False,
    pos_type=POS_TYPE_FAR,
    frame_width=0,
    frame_height=0,
    current_frame=0,
    lane_num=0,
    draw_x=0,
    draw_y=0,
    num_frames=0,
    born_ms=0
):
    mem = bytearray(28)  # Adjusted size for the byte layout
    sprite = uctypes.struct(uctypes.addressof(mem), SPRITE_DATA_LAYOUT)

    sprite.sprite_type = sprite_type
    sprite.x = x
    sprite.y = y
    sprite.z = z
    sprite.speed = speed
    sprite.visible = int(visible)
    sprite.active = int(active)
    sprite.blink = int(blink)
    sprite.blink_flip = int(blink_flip)
    sprite.pos_type = pos_type
    sprite.frame_width = frame_width
    sprite.frame_height = frame_height
    sprite.current_frame = current_frame
    sprite.lane_num = lane_num
    sprite.draw_x = draw_x
    sprite.draw_y = draw_y
    sprite.num_frames = num_frames
    sprite.born_ms = born_ms

    return sprite


# Define metadata structure, these values should not change across sprites of this class
class SpriteMetadata:
    image_path = None
    speed: int = 0
    width:int = 0
    height: int = 0
    color_depth: int = 0
    palette = None
    alpha: int = 0
    frames = None
    num_frames: int = 0

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"Object does not have property named '{key}'")

