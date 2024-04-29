from image_loader import ImageLoader
from sprite_3d import Sprite3D


class Spritesheet(Sprite3D):

    ratio = 0
    half_scale_one_dist = 0
    lane_width = 0
    palette = None

    def __init__(self, frame_width=None, frame_height=None, lane_width=None, *args, **kwargs):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.lane_width = lane_width

        if self.frame_width and self.frame_height:
            self.ratio = self.frame_width / self.frame_height

        super().__init__(*args, **kwargs)
        print(f"Spritesheet init'd with {len(self.frames)} frames")

        if self.pixels:
            self.set_frame(0)

    def update(self):
        super().update()
        self.update_frame()

    def _clone(self):
        copy = Spritesheet(
            frame_width=self.frame_width,
            frame_height=self.frame_height,
            x=self.x,
            y=self.y,
            z=self.z,
            camera=self.camera
        )
        copy.is3d = self.is3d
        copy.draw_x = self.draw_x
        copy.draw_y = self.draw_y

        copy.pixels = self.pixels
        copy.palette = self.palette
        copy.width = self.width
        copy.height = self.height
        copy.horiz_z = self.horiz_z

        copy.has_alpha = self.has_alpha
        copy.alpha_color = self.alpha_color
        copy.alpha_index = self.alpha_index

        copy.frames = self.frames
        copy.current_frame = self.current_frame
        copy.frame_width = self.frame_width
        copy.frame_height = self.frame_height
        copy.ratio = self.ratio
        copy.half_scale_one_dist = self.half_scale_one_dist
        copy.palette = self.palette.clone()
        copy.lane_width = self.lane_width
        copy.speed = self.speed

        if self.camera:
            copy.set_camera(self.camera)

        return copy