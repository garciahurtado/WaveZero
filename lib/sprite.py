from microbmp import MicroBMP as bmp
import framebuf
import array
import color_old as colors
import math

class Sprite:
    """ Represents a sprite which is loaded from disk in BMP format, and stored in memory as an RGB565 framebuffer"""
    pixels = None
    width = 0
    height = 0
    x = 0
    y = 0
    z = 0 # used in pseudo 3D rendering
    
    horiz_z = 2000
    
    has_alpha = False
    alpha_color = None
    camera = None # to simulate 3D
    height2d = 0

    def __init__(self, filename=None, x=0, y=0, z=0, camera=None) -> None:
        if filename:
            self.load_bmp(filename)
        self._z = z
        self.camera = camera
        

    def load_bmp(self, filename):
        """Loads an image from a BMP file and converts it to a binary RGB565 stream for later display"""
        print(f"Loading BMP: {filename}")
        image = bmp().load(filename)
        print(image)

        self.width = image.DIB_w
        self.height = image.DIB_h
        self.palette = image.palette
        pixels = image.rgb565()
        self.pixels = framebuf.FrameBuffer(
            pixels,
            self.width,
            self.height,
            framebuf.RGB565)
        
    def set_alpha(self, alpha_index=0):
        """Sets the index of the color to be used as an alpha channel (transparent), when drawing the sprite
        into the display framebuffer """

        self.has_alpha = True
        self.alpha_color = self.palette[alpha_index]
        self.alpha_color = colors.rgb_to_565(self.alpha_color)
        #alpha_color = alpha_color[2],alpha_color[1],alpha_color[0] # RGB to BGR
        #self.alpha_color = colors.rgb_to_565(alpha_color)
        print(f"Alpha color: {colors.rgb565_to_rgb(self.alpha_color)}")

    def show(self, display:framebuf.FrameBuffer):
        x, y = self.pos(display)
        if x > (display.width * 2):
            x = display.width * 2

        if self.has_alpha:
            display.blit(self.pixels, x, y, self.alpha_color)
        else:
            display.blit(self.pixels, x, y)
            
    def clone(self):
        copy = self.__class__()
        copy.camera = self.camera
        copy.x = self.x
        copy.y = self.y
        
        copy.pixels = self.pixels
        copy.width = self.width
        copy.height = self.height        
        copy.horiz_z = self.horiz_z
        copy.z = self.z
        
        copy.has_alpha = self.has_alpha
        copy.alpha_color = self.alpha_color
        
        return copy

            
    """3D sprites only"""
    @property
    def z(self):
        return self._z
    
    @z.setter
    def z(self, value):
        self._z = value
        #self.update_sprite()
        
    def get_lane(self, offset):
        """
        Returns the lane number which this sprite occupies in 3D space
        """
        total_width = self.num_lanes * self.lane_width

        if (self.x + offset) == 0:
            return 0
        else:
            return math.floor( (self.x + offset) / self.lane_width )

        
    def pos(self, display):
        """Returns the 2D coordinates of the object, calculated from the internal x,y (if 2D) or x,y,z
        (if 3D with perspective camera)
        """
        if self.camera: 
            # Send it back to the start
            if self._z < self.camera.min_z:
                self._z = self.horiz_z + 1
            
            x, y = self.camera.to2d(self.x, self.y, self._z)
            y = y - self.height_2d # set the object on the "floor", since it starts being drawn from the top
            return x, y
        else:
            return self.x, self.y

        

class Spritesheet(Sprite):
    frames = []
    current_frame = 0
    frame_width = 0
    frame_height = 0
    
    def __init__(self, filename=None, frame_width=None, frame_height=None, *args, **kwargs):
        super().__init__(filename, *args, **kwargs)
      
        if frame_width and frame_height:
            self.frame_width = frame_width
            self.frame_height = frame_height
        
            num_frames = self.width // frame_width
            print(f"Spritesheet with {num_frames} frames")
            
            self.frames = [None] * num_frames

            for idx in range(num_frames):
                x = idx * frame_width
                y = 0
                
                buffer = bytearray(frame_width * frame_height * 2)
                my_buffer = framebuf.FrameBuffer(buffer, frame_width, frame_height, framebuf.RGB565)
                
                for i in range(frame_width):
                    for j in range(frame_height):
                        color = self.pixels.pixel(x + i, y + j)
                        my_buffer.pixel(i, j, color)
                
                self.frames[idx] = my_buffer

            self.set_frame(0)

    def set_frame(self, frame_num):
        self.current_frame = frame_num
        self.pixels = self.frames[frame_num]
        
            
    def update_frame(self):
        if not self.frames or len(self.frames) == 0:
            return False
        
        # calculate 2D height, in order to pick the right frame in the spritesheet
        _, y_top = self.camera.to2d(self.x, self.y, self._z)
        _, y_bottom = self.camera.to2d(self.x, self.y + self.height, self._z)
        height_2d = math.ceil(y_bottom - y_top)
        self.height_2d = height_2d if height_2d > 1  else 1

        frame_idx = len(self.frames) / (self.height_2d / self.height) - 1
        # frame_idx = int((ratio * len(self.frames)) - 1)
        if frame_idx < 0:
            frame_idx = 0
        if frame_idx >= len(self.frames):
            frame_idx = len(self.frames) - 1
        self.set_frame(int(frame_idx))
    
    def clone(self):
        copy = super().clone()
        copy.frames = self.frames
        copy.current_frame = self.current_frame
        copy.frame_width = self.frame_width
        copy.frame_height = self.frame_height
        
        return copy
        
        
        