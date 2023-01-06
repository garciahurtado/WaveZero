from displayio import TileGrid

class FineTileGrid(TileGrid):
    fine_y = 0
    
    def __init__(self,  *args, **kwargs):
        fine_y = 0
        super(FineTileGrid, self).__init__(*args, **kwargs)
