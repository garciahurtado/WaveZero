from uarray import array

class ScalePatterns:
    """
    Stores, creates and manages the scaling patters to use in upscale / downscaling (only horizontal)
    """
    horiz_patterns = None
    scale_precision = 8

    def __init__(self):
        self.create_horiz_patterns()
        # self.print_patterns()

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
        patterns_all = {}

        patterns1 = self.create_patterns(0, 1, step=0.125)
        patterns2 = self.create_patterns(1, 4, step=0.250)
        patterns3 = self.create_patterns(4, 8, step=0.500)
        patterns4 = self.create_patterns(8, 14, step=1)
        patterns5 = self.create_patterns(14, 18, step=1)

        patterns_all |= patterns1
        patterns_all |= patterns2
        patterns_all |= patterns3
        patterns_all |= patterns4
        patterns_all |= patterns5
        # patterns_all = self.create_patterns(1, 16, step=0.5)

        self.horiz_patterns = patterns_all
        return self.horiz_patterns

    def create_patterns(self, from_scale, to_scale, step=0.125):
        pattern_list = {}
        num_scales = int((to_scale - from_scale) / step)

        for i in range(num_scales):

            from_scale += step
            pattern = self.create_one_pattern(from_scale)
            pattern_list[from_scale] = pattern

        return pattern_list

    def create_one_pattern(self, scale):
        """
        Fractional patterns are converted into lists of integers like this:
        SCALE 0.125: [0, 0, 0, 0, 1, 0, 0, 0],  # 12.5% scaling
        SCALE 2.500: [3, 2, 3, 2, 3, 2, 3, 2],  # 2.5x scaling
        """
        size = self.scale_precision

        if scale == int(scale):
            """ integer scales are the easiest, every element equals the current scale """
            pattern = [scale] * size
        else:
            """ We have a fractional scale, we will separate the decimal part. """
            whole_scale = int(scale)
            frac_scale = scale - whole_scale

            """ To start, fill out a basic integer pattern """
            pattern = [whole_scale] * size
            portion = 1/frac_scale      # portion of 1 that 1 frac_scale represents
            step_8 = int(portion * 8) # we scale by 8 so that we can step by it

            for i in range(0, size * 8, step_8):
                """ increase some numbers in the pattern so that the total average = scale"""
                idx = int(i/size)
                idx = idx % size
                pattern[idx] = whole_scale+1

        pattern = self.pattern_to_array(pattern)  # Convert to array
        return pattern

    def print_patterns(self, first=0, last=10):
        print()
        print(f"### PRINTING SCALING PATTERNS ({first} to {last}) ###")
        patterns = self.get_horiz_patterns()
        pattern_keys = list(patterns.keys())
        pattern_keys.sort()

        str_out = ''
        for scale in pattern_keys:
            pattern = patterns[scale]
            if scale >= first and scale < last:
                actual = sum(pattern) / self.scale_precision
                str_out += "\n"
                str_out += f"{scale} ({actual:.03f}):\n"
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