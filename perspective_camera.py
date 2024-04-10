class PerspectiveCamera():
    def __init__(self, width, height, vp_x=0, vp_y=0, focal_length=100):
        self.width = width
        self.height = height
        self.focal_length = focal_length
        self.vp = {"x":vp_x,"y":vp_y}
        self.focal_length = focal_length # Distance from the camera to the projection plane in pixels
        self.horiz_z = 5000 # past this point all sprites are considered to be in the horizon line
        self.min_z = 0
        
            
    def to2d(self, x, y, z):
        """
        Convert 3D coordinates to 2D space according to the screen dimensions and optical
        settings of this 3D camera
        """
        # invert_y = self.height - y - (self.max_height)
        invert_y = self.height - y
        invert_x = self.width - x
        
        # Here's where the magic happens. We convert the 3D coordinates to x,y in 2D space
        # @link https://math.stackexchange.com/a/2338025
        if z == 0:
            z = 0.00001
            
        new_x = round( ((x - self.vp['x']) * ( self.focal_length / z)) + self.vp['x'] )
        new_y = round( ((invert_y - self.vp['y']) * ( self.focal_length / z)) + self.vp['y'] )
        
        if new_x < 0:
            new_x = 0
        if new_y < 0:
            new_y = 0
        
        return new_x, new_y