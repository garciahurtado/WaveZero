import time
import math

SCREEN_WIDTH = 96
SCREEN_HEIGHT = 64

class PerspectiveSprite():
    """ Simulates a sprite in a 3D space given a 2D plane and a vanishing point
    """
    def __init__(self, sprite_grid, x=0, y=0, z=0, camera=None):
        self.sprite_grid = sprite_grid
        self.bitmap = sprite_grid.bitmap
        # self.max_height = sprite_grid.bitmap.height
        
        self.num_frames = round(self.bitmap.screen_width / sprite_grid.tile_width) - 1
        self.camera = camera

        self.horiz_z = 2000
        self.min_z = 0
        
        self.x = x
        self.y = y
        self._z = z
        
        self.num_lanes = 5
        self.lane_width = 30
        
    @property
    def z(self):
        return self._z
    
    @z.setter
    def z(self, value):
        self._z = value
        self.update_sprite()
        
    def get_lane(self):
        """
        Returns the lane number which this sprite occupies in 3D space
        """
        if (self.x) == 0:
            return 0
        else:
            return math.floor( (self.x) / self.lane_width )
        


    def update_sprite(self):
        """ Update the 2D sprite's x,y coordinates based on a projection from the fake 3D sprite's x,y,z coords
        """
        
        # Send it back to the start
        if self._z < self.camera.min_z:
            self._z = self.horiz_z + 1
        
        self.sprite_grid.x, self.sprite_grid.y = self.camera.to2d(self.x, self.y + self.bitmap.screen_height, self._z)
        
        # calculate 2D height, in order to pick the right frame in the spritesheet
        _, y_top = self.camera.to2d(self.x, self.y, self._z)
        height_px = y_top - self.sprite_grid.y
        
        
        if height_px > self.num_frames:
            height_px = self.num_frames
        elif height_px < 0:
            height_px = 0
        
        # print(f"Height: {height_px}")
        self.sprite_grid[0] = height_px