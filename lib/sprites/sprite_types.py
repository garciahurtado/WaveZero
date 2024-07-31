# Define the SpriteData namedtuple with additional fields for scaled sprites
from micropython import const
from ucollections import namedtuple


# SpriteData = namedtuple('SpriteData', [
#     'x', 'y', 'z', 'speed', 'visible', 'active', 'blink', 'blink_flip',
#     'pos_type', 'event_chain', 'filename', 'frame_width', 'frame_height',
#     'current_frame', 'lane_num', 'draw_x', 'draw_y', 'frames', 'num_frames'
# ])
POS_TYPE_FAR = const(0)
POS_TYPE_NEAR = const(1)

class SpriteData:
    __slots__ = ('sprite_type', 'x', 'y', 'z', 'speed', 'visible', 'active', 'blink', 'blink_flip',
                 'pos_type', 'event_chain', 'filename', 'frame_width', 'frame_height',
                 'current_frame', 'lane_num', 'draw_x', 'draw_y', 'num_frames', 'born_ms')

    def __init__(self,
                 sprite_type,
                 x:int=int(0),
                 y:int=int(0),
                 z:int=int(0),
                 speed:int=int(0),
                 visible=False,
                 active=False,
                 blink=False,
                 blink_flip:int=int(1),
                 pos_type=POS_TYPE_FAR,
                 event_chain=None,
                 filename=None,
                 frame_width:int=int(0),
                 frame_height:int=int(0),
                 current_frame:int=int(0),
                 lane_num:int=int(0),
                 draw_x:int=int(0),
                 draw_y:int=int(0),
                 num_frames:int=int(0),
                 born_ms:int=int(0),
                 ):
        self.sprite_type = sprite_type
        self.x = x
        self.y = y
        self.z = z
        self.speed = speed
        self.visible = visible
        self.active = active
        self.blink = blink
        self.blink_flip = blink_flip
        self.pos_type = pos_type
        self.event_chain = event_chain
        self.filename = filename
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.current_frame = current_frame
        self.lane_num = lane_num
        self.draw_x = draw_x
        self.draw_y = draw_y
        self.num_frames = num_frames
        self.born_ms = born_ms


    # Define metadata structure, these values should not change across sprites of this class
SpriteMetadata = namedtuple('SpriteMetadata', [
    'image_path', 'default_speed', 'width', 'height', 'color_depth', 'palette', 'alpha', 'frames', 'num_frames'
])
