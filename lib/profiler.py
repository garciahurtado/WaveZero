import utime


class Profiler():
    profile_labels = {}

    @staticmethod
    def start_profile(label):
        if label not in Profiler.profile_labels.keys():
            Profiler.profile_labels[label] = [0, 0, 0]  # num calls / start usecs / total time

        Profiler.profile_labels[label][1] = utime.ticks_us()  # record the start time

    @staticmethod
    def end_profile(label):
        if label not in Profiler.profile_labels.keys():
            raise f"Profiling Label '{label}' not found"

        record = Profiler.profile_labels[label]

        if not record[1]:
            raise AttributeError(f"Profiling label {label} is missing a start_profile")

        end_time = utime.ticks_us()
        start_time = record[1]
        elapsed = end_time - start_time

        """ Increase count by one, and add the time to the total"""
        record[0] = record[0] + 1
        record[1] = 0
        record[2] = record[2] + elapsed

    @staticmethod
    def profile_clean():
        for key in Profiler.profile_labels:
            data = Profiler.profile_labels[key]
            data[0], data[1], data[2] = 0, 0, 0

    @staticmethod
    def dump_profile():
        print()
        print(f"{'func': <22} {'runs': <8} {'avg ms': <14} {'total ms': <20}")
        print("--------------------------------------------------------")
        for label, data in Profiler.profile_labels.items():
            num_runs = data[0]
            total_time = data[2]
            avg_time = total_time / num_runs if num_runs else 0

            avg_time_ms = avg_time / 1000
            total_time_ms = total_time / 1000

            print(f"{label: <22} {num_runs: <8} {avg_time_ms: <14.2} {total_time_ms: <20.2}")
