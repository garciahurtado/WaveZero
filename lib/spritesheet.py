from image_loader import ImageLoader
from sprite_3d import Sprite3D


class Spritesheet(Sprite3D):
    frames = []
    current_frame = 0
    frame_width = 0
    frame_height = 0
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


    def set_frame(self, frame_num):
        if frame_num == self.current_frame:
            return False

        self.current_frame = frame_num
        self.pixels = self.frames[frame_num].pixels

    def update_frame(self):
        """Update the current frame in the spritesheet to the one that represents the correct size when taking into
        account 3D coordinates and the camera"""

        if not self.camera or not self.frames or (len(self.frames) == 0):
            return False

        frame_idx = self.get_frame_idx(self.z)
        if self.current_frame == frame_idx:
            return False

        self.set_frame(frame_idx)

        return True

    def get_frame_idx(self, real_z):
        rate = ((real_z - self.camera.pos['z']) / 2)
        if rate == 0:
            rate = 0.00001 # Avoid divide by zero

        scale = self.half_scale_one_dist / rate
        frame_idx = round(scale * len(self.frames))
        self.height_2d = scale * self.frame_height
        self.width_2d = self.ratio * self.height_2d

        if frame_idx >= len(self.frames):
            frame_idx = len(self.frames) - 1

        if frame_idx < 0:
            frame_idx = 0

        return frame_idx

    def load_image(self, filename, frame_width=None, frame_height=None):
        """Overrides parent"""
        if not frame_width:
            frame_width == self.width

        if not frame_height:
            frame_height = self.height

        images = ImageLoader.load_image(filename, frame_width, frame_height)

        if isinstance(images, list):
            self.frames = images
            self.set_frame(0)
            meta = images[0]
        else:
            meta = images

        self.width = meta.width
        self.height = meta.height
        self.palette = meta.palette
        self.num_colors = meta.num_colors
        self.pixels = meta.pixels

        self.reset()

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