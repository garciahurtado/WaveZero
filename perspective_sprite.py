from displayio import Group
import time
import math

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64

class PerspectiveSprite():
    """ Simulates a sprite in a 3D space given a 2D plane and a vanishing point
    """
    def __init__(self, sprite_grid, x=0, y=0, z=0, horiz_y=0):
        self.sprite_grid = sprite_grid
        self.bitmap = sprite_grid.bitmap
        self.max_height = sprite_grid.bitmap.height
        
        print(f"max height: {self.max_height }")
        self.num_frames = round(self.bitmap.width/sprite_grid.tile_width) - 1
        print(f"Loaded {self.num_frames} frames from spritesheet")
        self.horiz_y = horiz_y
        
        # Calculate vanishing point based on the horizon
        vp_x = round(SCREEN_WIDTH / 2)
        vp_y = horiz_y
        self.vanishing = {"x": vp_x, "y": vp_y}
        self.focal_length = 100 # Distance from the camera to the projection plane in pixels
        self.horiz_z = 2000
        self.min_z = 0
        
        self.x = x
        self.y = y
        self._z = z
        
    @property
    def z(self):
        return self._z
    
    @z.setter
    def z(self, value):
        self._z = value
        self.update_sprite()


    def update_sprite(self):
        """ Update the real sprites x,y coordinates based on a projection from the fake 3D sprites x,y,z coords
        """
        if self._z == 0:
            self._z = self.horiz_z + 1
        
        self.sprite_grid.x, self.sprite_grid.y = self.to2d(self.x, self.y, self._z)
        
        # calculate 2D height, in order to pick the right frame in the spritesheet
        _, y_top = self.to2d(self.x, self.y - self.max_height, self._z)
        height_px = abs(y_top - self.sprite_grid.y)
        
        if height_px > self.num_frames:
            height_px = self.num_frames
        elif height_px < 0:
            height_px = 0
        
        # print(f"Height: {height_px}")
        self.sprite_grid[0] = height_px
        
    def to2d(self, x, y, z):
        invert_y = SCREEN_HEIGHT - y
        
        # Here's where the magic happens. We convert the 3D coordinates to x,y in 2D space
        # @link https://math.stackexchange.com/a/2338025
        new_x = round((x * ( self.focal_length / z)) + self.vanishing['x'])
        new_y = round((invert_y * ( self.focal_length / z)) + self.vanishing['y'])
        
        # invert the y, since y is at the bottom in our 3D space, but at the top of screen space
        return new_x, new_y
        
        
    
        