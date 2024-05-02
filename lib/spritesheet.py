from image_loader import ImageLoader
from sprite import Sprite


class Spritesheet(Sprite):

    ratio = 0
    half_scale_one_dist = 0
    palette = None

    # Scaled / spritesheet frames
    frames = []
    current_frame = 0
    frame_width: int = 0
    frame_height: int = 0

    def __init__(self, frame_width: int = 0, frame_height: int = 0,  *args, **kwargs):
        self.frame_width = frame_width
        self.frame_height = frame_height

        super().__init__(*args, **kwargs)
        # if 'filename' in kwargs:
        #     print(f"Spritesheet init'd with {len(self.frames)} frames")


    def load_image(self, filename):
        """Overrides parent"""
        self.frames = ImageLoader.load_image(filename, self.frame_width, self.frame_height)

        print(f"Loaded {len(self.frames)} frames")
        meta = self.frames[0]

        self.width = meta.width
        self.height = meta.height
        self.palette = meta.palette
        self.dot_color = self.palette.get_bytes(1)
        self.num_colors = meta.palette.num_colors
        self.visible = True

        self.set_frame(0)

    def update(self):
        super().update()

    def set_frame(self, frame_num):
        if frame_num >= len(self.frames):
            raise KeyError(f"Frame {frame_num} is invalid (only {len(self.frames)} frames)")

        self.current_frame = frame_num
        self.image = self.frames[frame_num]
        self.width = self.image.width
        self.height = self.image.height

    def update_frame(self):
        """Update the current frame in the spritesheet to the one that represents the correct size when taking into
        account 3D coordinates and the camera """

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
        frame_idx = int(scale * len(self.frames))
        #self.height_2d = scale * self.frame_height
        #self.width_2d = self.ratio * self.height_2d

        if frame_idx >= len(self.frames):
            frame_idx = len(self.frames) - 1

        if frame_idx < 0:
            frame_idx = 0

        return frame_idx



