import gc

from micropython import const
import micropython

from death_anim import DeathAnim
from images.image_loader import ImageLoader
from perspective_camera import PerspectiveCamera
from sprites2.sprite_types import SpriteType, SPRITE_DATA_LAYOUT
import framebuf
import math
from images.indexed_image import Image, create_image
from sprites2.sprite_pool_lite import SpritePool
from typing import Dict, List
from profiler import Profiler as prof
import utime as time
from dump_object import dump_object

class SpriteManager:
    POS_TYPE_FAR = const(0)
    POS_TYPE_NEAR = const(1)
    display = None

    sprite_images: Dict[str, List[Image]] = {}
    sprite_palettes: Dict[str, bytes] = {}
    sprite_metadata: Dict[str, SpriteType] = {}
    sprite_classes: Dict[int, SpriteType] = {}
    sprite_actions = {}
    lane_width: int = 0
    half_scale_one_dist = int(0)  # This should be set based on your camera setup
    add_frames = 0  # Number of upscaled frames to add (scale > 1)
    pool = None
    grid = None
    camera: PerspectiveCamera = None

    def __init__(self, display: framebuf.FrameBuffer, max_sprites, camera=None, lane_width=None, grid=None):
        self.display = display

        self.max_sprites = max_sprites
        self.lane_width = lane_width
        self.grid = grid

        self.check_mem()
        self.pool = SpritePool(self.max_sprites)

        if camera:
            self.set_camera(camera)

    def add_type(self, **kwargs):
        """ These arguments are mandatory """
        sprite_type = kwargs['sprite_type']
        if 'sprite_class' in kwargs.keys():
            sprite_class = kwargs['sprite_class']
        else:
            sprite_class = SpriteType

        """ Register the new class """
        self.sprite_classes[sprite_type] = sprite_class

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
            'stretch_height']

        for arg in kwargs.keys():
            if arg not in (defaults + must_have):
                raise AttributeError(f"'{arg}' is not a valid argument for add_type")

        default_args = {key: kwargs[key] for key in kwargs}
        """ We dont need these for SpriteType initialization """
        if 'sprite_type' in default_args.keys():
            del default_args['sprite_type']
        if 'sprite_class' in default_args.keys():
            del default_args['sprite_class']

        type_obj = sprite_class(**default_args)

        # print(dump_object(type_obj))
        self.sprite_metadata[sprite_type] = type_obj

    def add_action(self, sprite_type, func):
        self.sprite_actions[sprite_type] = func

    def get_class_properties(self, cls):
        props = {}
        names = [attr for attr in dir(cls)
                if not callable(getattr(cls, attr))
                and not attr.startswith("__")]

        for name in names:
            props[name] = getattr(cls, name)

        return props

    def create(self, sprite_type, **kwargs):
        new_sprite, idx = self.pool.get(sprite_type)
        new_sprite.x = new_sprite.y = new_sprite.z = 0

        if sprite_type not in self.sprite_classes.keys():
            raise IndexError(f"Sprite type {sprite_type} is not defined")

        class_name = self.sprite_classes[sprite_type]
        class_attrs = self.get_class_properties(class_name)
        class_meta = self.sprite_metadata[sprite_type]

        # Set defaults for properties both in the sprite class as well as in the sprite entity
        for name, val in class_attrs.items():
            if name in SPRITE_DATA_LAYOUT.keys():
                setattr(new_sprite, name, val)
            new_sprite.speed = class_meta.speed
            new_sprite.frame_width = class_meta.width
            new_sprite.frame_height = class_meta.height
            new_sprite.num_frames = class_meta.num_frames

        #Set user values passed to the function
        for key, value in kwargs.items():
            if value is not None:
                setattr(new_sprite, key, value)

        new_sprite.sprite_type = sprite_type

        #Create images and frames
        if sprite_type not in self.sprite_images:
            self.sprite_images[sprite_type] = self.load_img_and_scale(class_meta, sprite_type)

        new_sprite.active = True
        return new_sprite, idx

    def load_img_and_scale(self, meta, sprite_type):
        orig_img = ImageLoader.load_image(meta.image_path, meta.width, meta.height)
        if isinstance(orig_img, list):
            orig_img = orig_img[0]

        frames = []
        num_frames = meta.num_frames

        for f in range(1, num_frames):
            scale = f / num_frames # Avoid division by zero

            new_width = math.ceil(meta.width * scale)
            new_height = math.ceil(meta.height * scale)

            # print(f"Scale is {scale} / w:{new_width} h:{new_height} ")

            new_frame = self.scale_frame(orig_img, new_width, new_height, meta.color_depth)
            frames.append(new_frame)

        frames.append(orig_img)  # Add original image as the last frame

        """Do we need to add upscale frames? (scale > 1)"""
        if ((meta.stretch_width and meta.stretch_width > meta.width) or
            (meta.stretch_height and meta.stretch_height > meta.height)):

            width_gap = meta.stretch_width - meta.width
            height_gap = meta.stretch_height - meta.height

            add_width_frames = 0
            add_height_frames = 0

            if width_gap > height_gap:
                add_width_frames = max(width_gap, height_gap)
            else:
                add_height_frames = max(width_gap, height_gap)

            print(f"+++ Adding {add_width_frames + add_height_frames} +++")

            for f in range(0, add_width_frames):
                pass

            for f in range(0, add_height_frames):
                pass


        self.sprite_palettes[sprite_type] = orig_img.palette
        meta.palette = orig_img.palette
        self.set_alpha_color(meta)

        return frames

    def scale_frame(self, orig_img, new_width, new_height, color_depth):
        if color_depth not in [4, 8]:
            raise ValueError(f"Unsupported color depth: {color_depth}")

        if new_width % 2 and color_depth == 4:  # Width must be even for 4-bit images
            new_width += 1

        byte_size = (new_width * new_height) // (8 // color_depth)
        new_bytes = bytearray(byte_size)

        if color_depth == 4:
            buffer_format = framebuf.GS4_HMSB
        else:  # 8-bit
            buffer_format = framebuf.GS8

        new_buffer = framebuf.FrameBuffer(new_bytes, new_width, new_height, buffer_format)

        x_ratio = orig_img.width / new_width
        y_ratio = orig_img.height / new_height

        for y in range(new_height):
            for x in range(0, new_width, 2 if color_depth == 4 else 1):
                x_1 = min(int(x * x_ratio), orig_img.width - 1)
                y_1 = min(int(y * y_ratio), orig_img.height - 1)

                color1 = orig_img.pixels.pixel(x_1, y_1)
                new_buffer.pixel(x, y, color1)

                if color_depth == 4:
                    x_2 = min(int((x + 1) * x_ratio), orig_img.width - 1)
                    color2 = orig_img.pixels.pixel(x_2, y_1)
                    new_buffer.pixel(x + 1, y, color2)

        return create_image(new_width, new_height, new_buffer, memoryview(new_bytes),
                            orig_img.palette, orig_img.palette_bytes, color_depth)

    def set_camera(self, camera):
        self.camera = camera
        scale_adj = 10  # Increase this value to see bigger sprites when closer to the screen
        self.half_scale_one_dist = int(abs(self.camera.cam_z - scale_adj) / 2)

    # @timed
    def update_sprite(self, sprite, meta, elapsed):
        """The update function only applies to a single sprite at a time, and it is responsible for killing expired
        / out of bounds sprites, as well as updating the x and y draw coordinates based on the 3D position and camera view
        """
        if not sprite.active:
            return False

        if not sprite.speed:
            return False

        #prof.start_profile('mgr.update_z_speed')
        new_z = sprite.z + (sprite.speed * elapsed)
        #prof.end_profile('mgr.update_z_speed')

        if new_z == sprite.z:
            return False

        sprite.z = int(new_z)
        if sprite.z == 0:
            sprite.z = 1

        cam = self.camera

        if new_z < cam.far and not sprite.visible:
            sprite.visible = True

        """ The rest of the calculations are only relevant for visible sprites within the frustrum"""

        disp = self.display

        if not sprite.visible:
            return True

        if new_z < cam.near:
            """Past the near clipping plane"""
            self.pool.release(sprite)
            return False

        prof.start_profile('mgr.sprite_scale')
        draw_y, scale= cam.get_scale(sprite.z)
        # draw_y = cam.get_y(sprite.z)

        if scale > 1:
            scale = 1

        sprite.scale = scale
        prof.end_profile('mgr.sprite_scale')

        # the scalars below are pretty much trial and error "magic" numbers
        # vp_scale = ((cam.max_vp_scale) * sprite.scale) + 0.8

        """ We have to adjust for the fact that 3D vertical axis and 2D vertical axis run in opposite directions,
        so we add the sprite height to Y in 3D space before translating to 2D"""

        # draw_x, draw_y = self.to_2d(sprite.x, sprite.y, sprite.z)

        """ in 3D space, distance between floor and vp Y, when scale = 1 """
        self.half_height = disp.height // 2
        self.half_width = disp.width // 2
        ground_height = disp.height - cam.vp_y

        # print(f"GROUND HEIGHT: {ground_height} cam vp y: {cam.vp_y}")

        # real_y = ground_height - cam.vp_y + sprite.y
        # y_factor = cam.get_y_factor(-real_y)

        prof.start_profile('mgr.sprite_scale_post')

        # print(f"real_y: {real_y} / factor: {y_Factor} / {}")
        # my_y = (cam.vp_y * scale) + cam.vp_y# magic number

        x_factor = math.pi
        draw_x = (sprite.x * scale) + self.half_width - ((cam.vp_x * x_factor) * scale)
        prof.end_profile('mgr.sprite_scale_post')

        # print(f"NEW Y: {my_y} / OLD Y: {draw_y}")

        # draw_y = draw_y + self.camera.vp_y

        #prof.start_profile('mgr.height_adjust')
        height = math.ceil(meta.height * sprite.scale)
        # draw_y -= height
        #prof.end_profile('mgr.height_adjust')

        #prof.start_profile('mgr.get_frame_idx')
        frame_idx = self.get_frame_idx(sprite.scale, sprite.num_frames)
        #prof.end_profile('mgr.get_frame_idx')

        # print(f"Z: {sprite.z}, scale: {sprite.scale} / DRAW Y : {draw_y}")

        sprite.draw_x = int(draw_x)
        # sprite.draw_y = int(draw_y - self.camera.screen_height)
        sprite.draw_y = draw_y

        sprite.current_frame = frame_idx

        return True

    def update(self, elapsed):
        metas = self.sprite_metadata
        current = self.pool.head
        while current:
            sprite = current.sprite
            meta = metas[sprite.sprite_type]

            self.update_sprite(sprite, meta, elapsed)

            next_node = current.next
            if not sprite.active:
                self.pool.release(sprite)

            current = next_node



    # @timed
    def show_sprite(self, sprite, display: framebuf.FrameBuffer):
        """Draw a single sprite on the display (or several, if multisprites)"""
        sprite_type = sprite.sprite_type

        if not sprite.visible:
            return False

        if sprite.blink:
            sprite.blink_flip = sprite.blink_flip * -1
            if sprite.blink_flip == -1:
                return False

        meta = self.sprite_metadata[sprite_type]
        alpha = meta.alpha_color

        palette = self.sprite_palettes[sprite_type]

        frame_id = sprite.current_frame # 255 sometimes ???
        # frame_id = 0

        image = self.sprite_images[sprite_type][frame_id]

        """Actions?"""
        # if sprite_type in self.sprite_actions.keys():
        #     action = self.sprite_actions[sprite_type]
        #     action(display, self.camera, sprite.draw_x, sprite.draw_y, sprite.x, sprite.y, sprite.z, sprite.frame_width)

        start_y = int(sprite.draw_y)
        start_x = sprite.draw_x

        """ Drawing a single image or a row of them? repeats 0 and 1 mean the same thing (one image) """
        if meta.repeats < 2:
            self.do_blit(x=int(sprite.draw_x), y=start_y, display=display, frame=image.pixels,
                         palette=palette, alpha=alpha)
        else:
            """Draw horizontal clones of this sprite"""
            for i in range(0, meta.repeats):
                x = start_x + (meta.repeat_spacing * sprite.scale * i)
                self.do_blit(x=round(x), y=start_y, display=display, frame=image.pixels,palette=palette, alpha=alpha)

        return True

    # @timed
    def do_blit(self, x: int, y: int, display: framebuf.FrameBuffer, frame, palette, alpha=None):
        if alpha is not None:
            display.blit(frame, int(x), int(y), alpha, palette)
        else:
            display.blit(frame, int(x), int(y), -1, palette)

        return True

    # @timed
    def to_2d(self, x, y, z, vp_scale=1):
        prof.start_profile('mgr.to_2d')

        camera = self.camera
        if camera:
            x, y = self.camera.to_2d(x, y, z, vp_scale=vp_scale)

        prof.end_profile('mgr.to_2d')
        return x, y


    def set_lane(self, sprite, lane_num):
        meta = self.get_meta(sprite)

        return self.grid.set_lane(sprite, lane_num, meta.repeats, meta.repeat_spacing)

    def get_lane(self, sprite):
        """
        Return the lane a sprite is in, based on its X coordinate.
        Values returned are in range [0,1,2,3,4]
        """
        norm_x = (self.lane_width * 2.5) - sprite.x
        # Calculate the center of the sprite
        sprite_center = norm_x - (sprite.frame_width / 2)

        # Calculate which lane the center of the sprite is in
        lane_num = round(sprite_center / self.lane_width)

        # Convert lane to lane_num (add 2 to shift from [-2,-1,0,1,2] to [0,1,2,3,4])
        # lane_num = lane + 2

        # Ensure lane_num is within valid range
        return max(0, min(4, lane_num))

    def get_meta(self, sprite):
        meta = self.sprite_metadata[sprite.sprite_type]
        return meta

    def set_alpha_color(self, sprite_type: SpriteType):
        """Get the value of the color to be used as an alpha channel when drawing the sprite
        into the display framebuffer """

        if sprite_type.alpha_index in(None, -1):
            return False

        alpha_color = sprite_type.palette.get_bytes(sprite_type.alpha_index)
        sprite_type.alpha_color = alpha_color

    # @micropython.viper
    def get_frame_idx(self, scale:float, num_frames:int):
        if num_frames < 1:
            raise ArithmeticError(f"Invalid number of frames: {num_frames}. Are width and height set?")
        frame_idx:int = scale * num_frames
        return int(min(frame_idx, num_frames - 1))


    # @timed
    def show(self, display: framebuf.FrameBuffer):
        """ Display all the active sprites """
        current = self.pool.head
        while current:
            sprite = current.sprite
            if sprite.visible:
                self.show_sprite(sprite, display)
            current = current.next

    def start_anims(self):
        """ Start the animations of all the registered sprite types"""
        for _, type in self.sprite_classes.items():
            if type.animations:
                type.start_anim()

    def check_mem(self):
        gc.collect()
        print(micropython.mem_info())


# Usage example
def main():
    print("Not intended to run standalone")
    exit(1)


if __name__ == "__main__":
    main()
