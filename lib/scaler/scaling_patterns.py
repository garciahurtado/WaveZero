from uarray import array

from utils import aligned_buffer

class ScalingPatterns:
    """
    Stores, creates and manages the scaling patters to use in upscale / downscaling (only horizontal)
    """
    horiz_patterns = None

    def get_pattern(self, scale):
        patterns = self.get_horiz_patterns()
        return patterns[scale]

    def get_horiz_patterns(self):
        """ Return exisiting, or create if it doesn't exist """
        if not self.horiz_patterns:
            self.horiz_patterns = self.create_horiz_patterns()

        return self.horiz_patterns

    def create_horiz_patterns(self):
        """Initialize horizontal scaling patterns"""
        # Base patterns for different scaling factors
        raw_patterns = {
            0.125: [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5%
            0.250: [0, 0, 1, 0, 0, 0, 1, 0],  # 25%
            0.375: [0, 0, 1, 0, 0, 1, 0, 1],  # 37.5%
            0.500: [0, 1, 0, 1, 0, 1, 0, 1],  # 50% scaling
            0.625: [0, 1, 1, 0, 1, 0, 1, 1],  # 62.5%
            0.750: [0, 1, 1, 1, 0, 1, 1, 1],  # 75% - works
            0.875: [1, 1, 1, 1, 0, 1, 1, 1],  # 87.5%
            1.0: [1, 1, 1, 1, 1, 1, 1, 1],  # No scaling
            1.250: [1, 2, 1, 1, 1, 2, 1, 1],  # 1.25x
            1.500: [1, 2, 1, 2, 1, 2, 1, 2],  # 1.5x scaling
            2.0: [2, 2, 2, 2, 2, 2, 2, 2],  # 2x scaling
            2.500: [2, 3, 2, 3, 2, 3, 2, 3],  # 2x scaling
            3.0: [3, 3, 3, 3, 3, 3, 3, 3],  # 3x scaling
            3.500: [3, 4, 3, 4, 3, 4, 3, 4],  # 3.5x scaling
            4.0: [4, 4, 4, 4, 4, 4, 4, 4],  # 4x scaling
            5.0: [5, 5, 5, 5, 5, 5, 5, 5],  # 5x scaling
            8.0: [8, 8, 8, 8, 8, 8, 8, 8],  # 8x scaling
            16.0: [16, 16, 16, 16, 16, 16, 16, 16],  # 8x scaling
        }

        patterns = {}
        for i, (key, val) in enumerate(raw_patterns.items()):
            array_pattern = self.create_aligned_pattern(val)
            patterns[key] = array_pattern

        return patterns


    def create_aligned_pattern(self, list):
        """
        Create word-ALIGNED buffer to store scaling patterns
        """
        arr_buff = aligned_buffer(8 * 4, alignment=4)
        final_array = array('L', arr_buff)

        for i in range(8):
            final_array[i] = list[i]

        return final_array