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
    "scale": uctypes.FLOAT32 | 8,
    "speed": uctypes.FLOAT32 | 12,
    "visible": uctypes.UINT8 | 16,
    "active": uctypes.UINT8 | 17,
    "blink": uctypes.UINT8 | 18,
    "blink_flip": uctypes.UINT8 | 19,
    "pos_type": uctypes.UINT8 | 20,
    "frame_width": uctypes.UINT8 | 21,
    "frame_height": uctypes.UINT8 | 22,
    "current_frame": uctypes.UINT8 | 23,
    "lane_num": uctypes.UINT8 | 24,
    "draw_x": uctypes.INT8 | 25,
    "draw_y": uctypes.INT8 | 26,
    "num_frames": uctypes.UINT8 | 27,
    "born_ms": uctypes.UINT32 | 28,
}

def create_sprite(
    sprite_type=0,
    x=0,
    y=0,
    z=0,
    scale=1,
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
    born_ms=0,
):
    mem = bytearray(32)  # Adjusted size for the byte layout
    sprite = uctypes.struct(uctypes.addressof(mem), SPRITE_DATA_LAYOUT)

    sprite.sprite_type = sprite_type
    sprite.x = x
    sprite.y = y
    sprite.z = z
    sprite.scale = scale
    sprite.speed = int(speed)
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
class SpriteType:
    def __init__(self, **kwargs):
        self.image_path = None
        self.speed: int = 0
        self.width: int = 0
        self.height: int = 0
        self.color_depth: int = 0
        self.palette = None
        self.alpha: int = 0
        self.frames = None
        self.num_frames: int = 0
        self.update_func = None
        self.render_func = None
        self.repeats: int = 0
        self.repeat_spacing: int = 0

        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
            else:
                raise AttributeError(f"Object does not have property named '{key}'")

