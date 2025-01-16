from uarray import array

class ScalingPatterns:
    """
    Stores, creates and manages the scaling patters to use in upscale / downscaling (only horizontal)
    """
    horiz_patterns = None

    def __init__(self):
        self.create_horiz_patterns()

    def get_pattern(self, scale):
        patterns = self.get_horiz_patterns()
        return patterns[scale]

    def get_horiz_patterns(self):
        """ Return exisiting, or create if it doesn't exist """
        if not self.horiz_patterns:
            self.horiz_patterns = self.create_horiz_patterns()

        return self.horiz_patterns

    def create_horiz_patterns(self):
        """
        steps tested = 0.016, 0.032, 0.064, 0.125, 0.250, 0.500
        """
        patterns1 = {}
        patterns1 = self.create_patterns(0, 1, step=0.064)
        patterns2 = self.create_patterns(1, 4, step=0.250)
        patterns3 = self.create_patterns(4, 6, step=0.500)
        patterns4 = self.create_patterns(6, 10, step=1)

        patterns1.update(patterns2)
        patterns1.update(patterns3)
        patterns1.update(patterns4)

        self.horiz_patterns = patterns1

        return self.horiz_patterns

    def create_patterns(self, from_scale, to_scale, step=0.125):
        pattern_list = {}
        scales_num = int((to_scale - from_scale) / step)

        for i in range(scales_num):
            pattern = self.create_one_pattern(from_scale)
            pattern_list[from_scale] = pattern
            from_scale += step # First one doesn't count

        return pattern_list

    def create_one_pattern(self, scale, num=8):
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
            step_8 = round(portion * 8) # we scale by 8 so that we can step by it

            for i in range(0, num*8, step_8):
                """ increase some numbers in the pattern so that the total average = scale"""
                idx = int(i/8)
                pattern[idx] = whole_scale+1

        pattern = self.pattern_to_array(pattern)  # Convert to array
        return pattern

    def print_patterns(self, first=0, last=1):
        print()
        print(f"### PRINTING SCALING PATTERNS ({first} to {last}) ###")
        patterns = self.get_horiz_patterns()

        str_out = ''
        for key, pattern in patterns.items():
            if key >= first and key < last:
                str_out += "\n"
                str_out += f"{key}:\n"
                list_str = ", ".join([str(num) for num in pattern])
                str_out += f"   [{list_str}]\n"

        print(str_out)

    def pattern_to_array(self, list):
        """
        Create bytebuffer to store 1 scaling pattern of 8 elements
        """
        arr_buff = bytearray(8 * 4)
        final_array = array('L', arr_buff)

        for i in range(8):
            final_array[i] = int(list[i])

        return final_array