import io

import math
from uarray import array

from utils import aligned_buffer, pprint

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
        patterns1 = self.create_print_patterns(0, 1, step=0.125)
        patterns2 = self.create_print_patterns(1, 5, step=0.125)
        patterns1.update(patterns2)

        self.horiz_patterns = patterns1
        reprs = self.print_patterns(self.horiz_patterns)
        print(reprs)

        return self.horiz_patterns

    def _create_static_patterns(self):

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
            1.500: [2, 1, 2, 1, 2, 1, 2, 1],  # 1.5x scaling
            2.0: [2, 2, 2, 2, 2, 2, 2, 2],  # 2x scaling
            2.500: [3, 2, 3, 2, 3, 2, 3, 2],  # 2x scaling
            3.0: [3, 3, 3, 3, 3, 3, 3, 3],  # 3x scaling
            3.500: [4, 3, 4, 3, 4, 3, 4, 3],  # 3.5x scaling
            4.0: [4, 4, 4, 4, 4, 4, 4, 4],  # 4x scaling
            4.500: [5, 4, 5, 4, 5, 4, 5, 4],  # 4.5x scaling
            5.0: [5, 5, 5, 5, 5, 5, 5, 5],  # 5x scaling
            8.0: [8, 8, 8, 8, 8, 8, 8, 8],  # 8x scaling
            16.0: [16, 16, 16, 16, 16, 16, 16, 16],  # 8x scaling
        }

        patterns = {}
        for i, (key, val) in enumerate(raw_patterns.items()):
            array_pattern = self.create_aligned_pattern(val)
            patterns[key] = array_pattern

        return patterns

    def create_print_patterns(self, from_scale, to_scale, step=0.125):
        pattern_list = {}
        scales_num = int((to_scale - from_scale) / step)

        for i in range(scales_num):
            from_scale += step # First one doesn't count

            pattern = self.create_pattern(from_scale)
            pattern_list[from_scale] = pattern

        return pattern_list

    def create_pattern(self, scale, num=8):
        """
        Fractional patterns are converted into lists of integers like this:
        SCALE 0.125: [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5% scaling
        SCALE 2.500: [3, 2, 3, 2, 3, 2, 3, 2],  # 2.5x scaling
        """

        if scale == int(scale):
            """ whole scales are the easiest """
            pattern = [scale] * num
        else:
            """ We have a fractional scale """
            whole_scale = int(scale)
            frac_scale = scale - whole_scale

            pattern = [whole_scale] * num # Start with basic 'whole' pattern
            portion = 1/frac_scale
            step_8 = int(portion * 8) # we scale by 8 so that we can step by it

            for i in range(0, num*8, step_8):
                """ increase some numbers in the pattern so that the total average = scale"""
                idx = math.ceil(i/8)
                pattern[idx-1] = whole_scale+1

        pattern = self.create_aligned_pattern(pattern)  # Convert to array
        return pattern

    def print_patterns(self, patterns):
        print()
        print("### PRINTING PATTERNS ###")
        str_out = ''
        for key, patt_list in patterns.items():
            print(patt_list)
            str_out += "\n"
            str_out += f"{key}:\n"
            list_str = ", ".join([str(num) for num in patt_list])

            # list_str = ' ,'.join(list(patt_list))
            str_out += f"   [{list_str}]\n"

        return str_out

    def create_aligned_pattern(self, list):
        """
        Create word-ALIGNED buffer to store scaling patterns
        """
        arr_buff = aligned_buffer(8, alignment=4)
        final_array = array('L', arr_buff)

        for i in range(8):
            final_array[i] = int(list[i])

        return final_array