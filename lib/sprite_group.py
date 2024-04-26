
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
    num_elements = 0

    def __init__(self, filename=None, num_elements=0, palette_gradient=None, pos_delta=None, *args, **kwargs):
        super().__init__(filename, *args, **kwargs)

        self.palette_gradient = palette_gradient
        self.pos_delta = pos_delta
        self.num_elements = num_elements

        for i in range(0, num_elements):
            if palette_gradient:
                new_palette = self.palette.clone()
                new_palette.pixel(i, 1, palette_gradient.pixel(i,0))
                self.instance_palettes.append(new_palette)

            instance = SpriteInstance(0, 0, 0, 0, 0, 0, 0)
            self.instances.append(instance)

    def update(self):
        """ Update the position of all the Sprite instances """
        super().update()

        # Check whether we need to reset to max Z
        # if self.z < self.camera.pos['z']:
        #     self.z = self.horiz_z

        for i in range(self.num_elements):
            inst = self.instances[i]

            if self.camera:
                new_z = self.z + (self.pos_delta["z"] * i)
                inst.frame_idx = self.get_frame_idx(new_z)
                inst.height = self.height_2d

                new_x = self.x + (self.pos_delta["x"]*i)
                new_y = self.y + (self.pos_delta["y"]*i)

                inst.draw_x, inst.draw_y = self.camera.to_2d(
                    new_x,
                    new_y,
                    new_z)

                inst.draw_y -= inst.height




    def show(self, display: framebuf.FrameBuffer):
        # if self.z > self.horiz_z:
        #     return False

        for i in range(len(self.instances)-1, -1, -1): # Iterate backwards through instances
            inst = self.instances[i]
            self.set_frame(inst.frame_idx)

            if False and self.instance_palettes:
                palette = self.instance_palettes[i]
            else:
                palette = self.palette


            if self.has_alpha:
                display.blit(self.pixels, int(inst.draw_x), int(inst.draw_y), self.alpha_color, palette)
            else:
                display.blit(self.pixels, inst.draw_x, inst.draw_y, -1, palette)

    def clone(self):
        new_group = SpriteGroup(
            filename=None,
            num_elements=self.num_elements,
            width=self.width,
            height=self.height,
            frame_width=self.frame_width,
            frame_height=self.frame_height,
            x=self.x,
            y=self.y,
            z=self.z,
            camera=self.camera
            )

        new_group.instances = [inst.clone() for inst in self.instances]
        new_group.width_2d = self.width_2d
        new_group.height_2d = self.height_2d
        new_group.draw_x = self.draw_x
        new_group.draw_y = self.draw_y
        new_group.min_y = self.min_y
        new_group.half_scale_one_dist = self.half_scale_one_dist
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

        return new_group

class SpriteEnemyGroup(SpriteGroup):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def update(self):
        # Check whether we need to reset Z to max Z
        if self.z > self.camera.pos['z']:
            self.z = self.horiz_z

        super().update()


class SpriteInstance:
    def __init__(self, x, y, z, draw_x, draw_y, frame_idx, height):
        self.x = x
        self.y = y
        self.z = z
        self.draw_x = draw_x
        self.draw_y = draw_y
        self.frame_idx = frame_idx
        self.height = height

    def clone(self):
        my_copy = SpriteInstance(
            self.x,
            self.y,
            self.z,
            self.draw_x,
            self.draw_y,
            self.frame_idx,
            self.height
        )
        return my_copy


