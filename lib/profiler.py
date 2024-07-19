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
        elapsed = utime.ticks_diff(end_time, start_time)

        """ Increase count by one, reset the start time to zero, and add the time to the total runtime"""
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
        print(f"{'func': <32} {'runs': <8} {'avg ms': <14} {'total ms': >20}")
        print("-------------------------------------------------------------------------------")
        for label, data in Profiler.profile_labels.items():
            num_runs = data[0]
            total_time = data[2]
            avg_time = total_time / num_runs if num_runs else 0

            avg_time_ms = avg_time / 1000
            total_time_ms = total_time / 1000

            print(f"{label: <32} {num_runs: <8} {avg_time_ms: <14.2} {total_time_ms: >20.6}")

def timed(func, *args, **kwargs):
    parts = str(func).split(' ')
    if len(parts) > 1:
        myname = parts[1]
    else:
        myname = parts[0]

    def new_func(*args, **kwargs):
        Profiler.start_profile(myname)
        result = func(*args, **kwargs)
        Profiler.end_profile(myname)

        return result
    return new_func
