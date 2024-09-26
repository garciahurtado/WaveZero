from images.image_loader import ImageLoader
from sprites.sprite import Sprite


class Spritesheet(Sprite):

    ratio = 0
    half_scale_one_dist = 10
    palette = None

    # Scaled / spritesheet frames
    frames = []
    num_frames = 0
    current_frame = 0
    frame_width: int = 0
    frame_height: int = 0

    def __init__(self, frame_width, frame_height, color_depth=8, *args, **kwargs):
        self.frame_width = frame_width
        self.frame_height = frame_height
        self.color_depth = color_depth

        if 'width' not in kwargs:
            kwargs['width'] = frame_width
            kwargs['height'] = frame_height

        self.frames = []

        super().__init__(**kwargs)
        # if 'filename' in kwargs:
        #     print(f"Spritesheet init'd with {len(self.frames)} frames")


    def load_image(self, filename, frame_width, frame_height):
        """Overrides parent"""
        color_depth = self.color_depth
        image = ImageLoader.load_image(filename, frame_width, frame_height, color_depth)
        if image.frames:
            self.num_frames = len(image.frames)
            self.frames = image.frames
        else:
            self.num_frames = 0


        print(f"Loaded {len(self.frames)} frames")

        # self.width = meta.width
        # self.height = meta.height
        self.palette = image.palette
        self.dot_color = self.palette.get_bytes(1)
        self.num_colors = image.palette.num_colors
        self.visible = True

        self.set_frame(0)

    def update(self):
        super().update()


    def update_frame(self):
        """Update the current frame in the spritesheet to the one that represents the correct size when taking into
        account 3D coordinates and the camera """

#        prof.start_profile("sprite.update_frame")

        frame_idx = self.get_frame_idx(self.z)
        # print(f"IDX: {frame_idx} / z: {self.z}")
        if self.current_frame == frame_idx:
            return False 

        self.set_frame(frame_idx)

        # prof.end_profile("sprite.update_frame")

        return True

    def set_frame(self, frame_num):
        if self.num_frames < 1:
            return False

        if frame_num >= len(self.frames):
            raise KeyError(f"Frame {frame_num} is invalid (only {len(self.frames)} frames)")

        print(f"SET FRAME {frame_num}")
        self.current_frame = frame_num
        self.image = self.frames[frame_num]

    def get_frame_idx(self, real_z):
        """ Given the Z coordinate (depth), find the frame ID which best represents the
        size of the object at that distance """

        num_frames = self.num_frames

        rate = (real_z - self.camera.cam_z / 2)
        if rate == 0:
            rate = 0.0001 # Avoid divide by zero

        scale = abs(self.half_scale_one_dist / rate)
        frame_idx = int(scale * num_frames)

        if frame_idx > num_frames - 1:
            frame_idx = num_frames - 1

        if frame_idx < 0:
            frame_idx = 0

        return frame_idx

    def __len__(self):
        return self.num_frames

    def clone(self):
        new = super().clone()
        new.frames = self.frames
        new.num_frames = self.num_frames
        new.frame_width = self.frame_width
        new.frame_height = self.frame_height
        new.width = self.width
        new.height = self.height
        new.ratio = self.ratio
        new.half_scale_one_dist = self.half_scale_one_dist
        new.palette = self.palette
        new.z = self.z

        return new




