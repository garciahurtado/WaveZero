
import framebuf
from collections import namedtuple

from color_util import FramebufferPalette
from sprite import Sprite, Spritesheet


class SpriteGroup(Spritesheet):
    """Represents a group of sprites that use the same image and are rendered nearby as a group. This class renders
    the sprites without needing an object for each"""

    pos_delta = {'x': 0, 'y': 0, 'z': 0}
    palette_gradient: FramebufferPalette = None
    instance_palettes = []
    instances = []
    filename: None

    def __init__(self, filename=None, num_elements=0, palette_gradient=None, pos_delta=None, *args, **kwargs):
        super().__init__(filename, *args, **kwargs)

        self.palette_gradient = palette_gradient
        self.pos_delta = pos_delta

        for i in range(num_elements):
            # if palette_gradient:
            #     new_palette = self.palette.clone()
            #     new_palette.set_bytes(0, palette_gradient[i])
            #     self.instance_palettes.append(new_palette)

            instance = SpriteInstance(0, 0, 0, 0, 0, 0)
            self.instances.append(instance)

    def update(self):
        """ Update the position of all the Sprite instances """
        super().update()

        for i in range(len(self.instances)):
            pos = self.instances[i]

            if self.camera:
                pos.draw_x, pos.draw_y = self.camera.to_2d(
                    self.x + (self.pos_delta["x"]*i),
                    self.y + (self.pos_delta["y"]*i) + self.height,
                    self.z + (self.pos_delta["z"]*i))

                pos.frame_idx = self.get_frame_idx(self.z + (self.pos_delta["z"]*i))

    def show(self, display: framebuf.FrameBuffer):
        # if self.z > self.horiz_z:
        #     return False

        palette = self.palette
        for i in range(len(self.instances)-1, -1, -1): # Iterate backwards
            pos = self.instances[i]
            self.set_frame(pos.frame_idx)
            # print(f"Pos idx: {pos.frame_idx}")

            # if self.instance_palettes:
            #     palette = self.instance_palettes[i]
            # else:
            #     palette = self.palette


            if self.has_alpha:
                display.blit(self.pixels, pos.draw_x, pos.draw_y, self.alpha_color, palette)
            else:
                display.blit(self.pixels, pos.draw_x, pos.draw_y, -1, palette)

    def clone(self):
        new_group = SpriteGroup(
            filename=None,
            num_elements=0,
            width=self.width,
            height=self.height,
            frame_width=self.frame_width,
            frame_height=self.frame_height,
            x=self.x,
            y=self.y,
            z=self.z,
            )

        new_group.instances = [inst.clone() for inst in self.instances]
        new_group.width_2d = self.width_2d
        new_group.height_2d = self.height_2d
        new_group.draw_x = self.draw_x
        new_group.draw_y = self.draw_y
        new_group.min_y = self.min_y
        new_group.half_scale_one_dist = self.half_scale_one_dist
        new_group.height = self.height
        new_group.width = self.width
        new_group.horiz_z = self.horiz_z
        new_group.is3d = True
        new_group.speed = self.speed
        new_group.lane_width = self.lane_width
        new_group.frames = self.frames
        new_group.pixels = self.pixels
        new_group.pos_delta = self.pos_delta
        new_group.palette = self.palette
        new_group.palette_gradient = self.palette_gradient
        new_group.instance_palettes = self.instance_palettes

        print(f"Copied {len(new_group.instances)} instances")

        return new_group

class SpriteInstance:
    def __init__(self, x, y, z, draw_x, draw_y, frame_idx):
        self.x = x
        self.y = y
        self.z = z
        self.draw_x = draw_x
        self.draw_y = draw_y
        self.frame_idx = frame_idx

    def clone(self):
        my_copy = SpriteInstance(
            self.x,
            self.y,
            self.z,
            self.draw_x,
            self.draw_y,
            self.frame_idx,
        )
        return my_copy


