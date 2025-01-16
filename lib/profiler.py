import utime
from ucollections import OrderedDict
import asyncio

class Profiler():
    profile_labels = OrderedDict()
    _task_local = {}
    enabled = True

    @staticmethod
    def _get_current_task():
        try:
            return asyncio.current_task()
        except RuntimeError:
            return None  # We're not in an asyncio event loop

    @staticmethod
    def start_profile(label):
        if not Profiler.enabled:
            return False

        # task = Profiler._get_current_task()
        # if task:
        #     if task not in Profiler._task_local:
        #         Profiler._task_local[task] = []
        #     Profiler._task_local[task].append(label)

        if label not in Profiler.profile_labels:
            Profiler.profile_labels[label] = [0, 0, 0, label]  # num calls / start usecs / total time / label

        Profiler.profile_labels[label][1] = utime.ticks_us()  # record the start time

    @staticmethod
    def end_profile(label=None):
        if not Profiler.enabled:
            return False
        task = Profiler._get_current_task()
        if task:
            if not label:
                if task not in Profiler._task_local or not Profiler._task_local[task]:
                    return
                label = Profiler._task_local[task].pop()
            elif task in Profiler._task_local and Profiler._task_local[task] and Profiler._task_local[task][
                -1] == label:
                Profiler._task_local[task].pop()
        elif not label:
            return

        if label not in Profiler.profile_labels:
            return

        record = Profiler.profile_labels[label]
        if not record[1]:
            return

        end_time = utime.ticks_us()
        elapsed = utime.ticks_diff(end_time, record[1])

        record[0] += 1  # Increment call count
        record[1] = 0  # Reset start time
        record[2] += elapsed  # Add to total time

    @staticmethod
    async def profile_clean():
        Profiler.profile_labels.clear()
        Profiler._task_local.clear()

    @staticmethod
    def dump_profile(filter=None):
        """
        Filter: only the profile tags matching the string will be shown
        """
        if not Profiler.enabled:
            return False

        print("\n")
        print(f"{'func': <32} {'runs': <8} {'avg ms': <14} {'total ms': >9} ")
        print("--------------------------------------------------------------------")

        if not Profiler.profile_labels:
            print("No profiling data available.")
        else:
            sorted_labels = sorted(Profiler.profile_labels.items(), key=lambda x: x[1][2], reverse=True)

            for record in sorted_labels:
                record = record[1]
                num_runs, _, total_time, label = record

                if filter and filter not in label:
                    continue

                if num_runs == 0:
                    print(f"{label: <32} {'N/A': <8} {'N/A': <14} {'N/A': >9}")
                else:
                    avg_time = total_time / num_runs
                    avg_time_ms = avg_time / 1000
                    total_time_ms = total_time / 1000
                    print(f"{label: <32} {num_runs: <8} {avg_time_ms: <14.4f} {total_time_ms: >9.2f}")

        print("\n")

def timed(func):
    """ Doesnt currently work. """
    func_name = func.__name__
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()
        loop.create_task(Profiler.start_profile(func_name))
        try:
            result = func(*args, **kwargs)
            return result
        finally:
            loop.create_task(Profiler.end_profile(func_name))
    return wrapper
