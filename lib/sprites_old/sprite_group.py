import random
import framebuf
from sprites.scaled_sprite import ScaledSprite

class SpriteGroup(ScaledSprite):
    """Represents a group of sprites that use the same image and are rendered nearby as a group. This class renders
    the sprites without needing an object for each"""

    pos_delta = {'x': 0, 'y': 0, 'z': 0}
    palette_gradient = None
    instance_palettes = []
    instances = []
    num_elements = 0
    grid = None
    z_length: int = 0

    def __init__(self, num_elements=0, palette_gradient=None, pos_delta=None, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.palette_gradient = palette_gradient
        self.pos_delta = pos_delta
        self.num_elements = num_elements

        if pos_delta and 'z' in pos_delta:
            self.z_length = int(pos_delta['z'] * (num_elements+1))

        self.create_instances()

    def create_instances(self):
        self.instances = []
        for i in range(0, self.num_elements):
            if self.palette_gradient:
                new_palette = self.frames[0].palette.clone()
                new_palette.pixel(i, 1, self.palette_gradient.pixel(i,0))
                self.instance_palettes.append(new_palette)

            instance = SpriteInstance(0, 0, 0, 0, 0, 0, 0)
            self.instances.append(instance)

    def update(self):
        """ Update the position of all the Sprite instances """
        # if self.grid:
        #     self.speed = -self.grid.speed

        super().update()

        # Check whether we need to reset
        if (self.z + self.z_length) < self.camera.cam_z:
            self.reset()

        for i in range(self.num_elements):
            inst = self.instances[i]

            if self.camera:
                new_x = self.x + (self.pos_delta["x"]*i)
                new_y = self.y + (self.pos_delta["y"]*i)
                new_z = self.z + (self.pos_delta["z"] * i)

                inst.frame_idx = self.get_frame_idx(new_z)
                inst.height = self.frames[inst.frame_idx].height

                inst.draw_x, inst.draw_y = self.camera.to_2d(
                    new_x,
                    new_y,
                    new_z)

                inst.draw_y -= inst.height

    def show(self, display: framebuf.FrameBuffer):
        if not self.visible:
            return False

        for i in range(len(self.instances)-1, -1, -1): # Iterate backwards through instances
            inst = self.instances[i]
            self.set_frame(inst.frame_idx)

            if self.instance_palettes:
                palette = self.instance_palettes[i]
            else:
                palette = self.palette

            if self.has_alpha:
                display.blit(self.image.pixels, int(inst.draw_x), int(inst.draw_y), self.alpha_color, palette)
            else:
                display.blit(self.image.pixels, inst.draw_x, inst.draw_y, -1, palette)

    def reset(self):
        lane = random.randrange(0, 5)
        self.set_lane(lane)
        self.set_frame(0)

        self.z = self.horiz_z + (200 * random.randrange(2, 10))


    def clone(self):
        copy = super().clone()
        copy.reset()
        copy.create_instances()
        return copy

class SpriteEnemyGroup(SpriteGroup):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def update(self):
        # Check whether we need to reset Z to max Z
        if self.z < self.camera.cam_z:
            self.reset()

        super().update()

class SpriteInstance:
    def __init__(self, x, y, z, draw_x, draw_y, frame_idx, height):
        self.x: int = x
        self.y: int = y
        self.z: int = z
        self.draw_x: int = draw_x
        self.draw_y: int = draw_y
        self.frame_idx: int = frame_idx
        self.height: int = height



