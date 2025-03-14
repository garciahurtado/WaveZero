from bus_monitor_const import *
import time
import machine

class BusMonitor:
    def __init__(self, auto_start=False):
        """Initialize the bus performance monitor

        Args:
            auto_start: Whether to automatically enable counters on init (default: True)
        """
        # Array of register addresses
        self.perfctr_addrs = [PERFCTR0_ADDR, PERFCTR1_ADDR, PERFCTR2_ADDR, PERFCTR3_ADDR]
        self.perfsel_addrs = [PERFSEL0_ADDR, PERFSEL1_ADDR, PERFSEL2_ADDR, PERFSEL3_ADDR]
        self.counter_values = [0, 0, 0, 0]
        self.selected_events = [0x1F, 0x1F, 0x1F, 0x1F]  # Default events (SRAM6_ACCESS)
        self.prev_values = [0, 0, 0, 0]  # For tracking frame-to-frame differences
        self.is_running = False
        if auto_start:
            self.start_counters()
            self.is_running = True

    def configure_counters(self, events):
        """Configure performance counters with specified events.

        Args:
            events: List of up to 4 event codes to monitor
        """
        # Disable performance counters while configuring
        machine.mem32[PERFCTR_EN_ADDR] = 0

        # Reset counter values
        for addr in self.perfctr_addrs:
            machine.mem32[addr] = 1  # Write any value to clear

        # Configure each counter
        num_events = min(len(events), 4)
        for i in range(num_events):
            event_code = events[i]
            if event_code in PERF_EVENTS:
                machine.mem32[self.perfsel_addrs[i]] = event_code
                self.selected_events[i] = event_code
            else:
                print(f"Warning: Invalid event code 0x{event_code:02X}, using default")

        # Enable performance counters
        machine.mem32[PERFCTR_EN_ADDR] = 1

    def configure_preset(self, preset_name):
        """Configure counters using a predefined preset.

        Args:
            preset_name: Name of the preset from COMMON_PRESETS
        """
        if preset_name in COMMON_PRESETS:
            self.configure_counters(COMMON_PRESETS[preset_name])
            print(f"Configured preset: {preset_name}")
        else:
            print(f"Unknown preset: {preset_name}")
            print(f"Available presets: {', '.join(COMMON_PRESETS.keys())}")

    def read_counters(self):
        """Read the current values of all configured performance counters"""
        values = []
        for addr in self.perfctr_addrs:
            value = machine.mem32[addr] & 0xFFFFFF  # 24-bit counters
            values.append(value)
        return values

    def reset_counters(self):
        """Reset all performance counters to zero"""
        for addr in self.perfctr_addrs:
            machine.mem32[addr] = 1  # Write any value to clear

    def start_counters(self):
        """Enable the performance counters"""
        machine.mem32[PERFCTR_EN_ADDR] = 1

    def stop_counters(self):
        """Disable the performance counters"""
        machine.mem32[PERFCTR_EN_ADDR] = 0

    def display_counters(self):
        """Display the current counter values in a formatted table"""
        values = self.read_counters()

        # Header
        print("\n┌───┬─────────────────────────────────┬────────────┐")
        print("│ # │ Performance Event               │ Count      │")
        print("├───┼─────────────────────────────────┼────────────┤")

        # Print each configured counter
        for i in range(4):
            event_code = self.selected_events[i]
            event_name = PERF_EVENTS.get(event_code, "Unknown")

            # Format the value with thousand separators
            value_str = f"{values[i]:,}"

            print(f"│ {i} │ {event_name:<33} │ {value_str:>10} │")

        print("└───┴─────────────────────────────────┴────────────┘")

    def monitor_for_duration(self, duration_ms):
        """Monitor performance for a specified duration.

        Args:
            duration_ms: Duration to monitor in milliseconds
        """
        print(f"Monitoring bus performance for {duration_ms} ms...")

        # Reset and start counters
        self.reset_counters()
        self.start_counters()

        # Wait for the specified duration
        time.sleep_ms(duration_ms)

        # Stop counters and display results
        self.stop_counters()
        self.display_counters()

    def update_frame(self, reset_after=False, return_deltas=True):
        """Update performance counters for a single frame.

        Call this once per frame to collect performance data.

        Args:
            reset_after: Whether to reset counters after reading (default: False)
            return_deltas: Return differences since last call instead of absolute values

        Returns:
            List of counter values or deltas
        """
        # Store previous values
        self.prev_values = self.counter_values.copy()

        # Read current values
        self.counter_values = self.read_counters()

        # Calculate deltas
        if return_deltas:
            result = [current - prev for current, prev in zip(self.counter_values, self.prev_values)]
        else:
            result = self.counter_values.copy()

        # Reset if requested
        if reset_after:
            self.reset_counters()

        return result

    def get_event_names(self):
        """Get the names of currently configured events.

        Returns:
            List of event names for the four counters
        """
        return [PERF_EVENTS.get(code, f"Unknown (0x{code:02X})")
                for code in self.selected_events]

    def list_available_events(self):
        """List all available performance events by category"""
        print("\nAvailable Performance Events:")

        for category, event_codes in EVENT_CATEGORIES.items():
            print(f"\n{category} Events:")
            print("┌──────┬──────────────────────────────────┐")
            print("│ Code │ Event Name                       │")
            print("├──────┼──────────────────────────────────┤")

            for code in event_codes:
                name = PERF_EVENTS.get(code, "Unknown")
                print(f"│ 0x{code:02X} │ {name:<32} │")

            print("└──────┴──────────────────────────────────┘")

    def list_presets(self):
        """List available preset configurations"""
        print("\nAvailable Presets:")
        print("┌──────────────────┬───────────────────────────────────────────────────────┐")
        print("│ Preset Name      │ Monitored Events                                      │")
        print("├──────────────────┼───────────────────────────────────────────────────────┤")

        for name, events in COMMON_PRESETS.items():
            event_names = [PERF_EVENTS.get(e, "Unknown") for e in events]
            events_str = ", ".join(event_names)
            print(f"│ {name:<16} │ {events_str:<55} │")

        print("└──────────────────┴───────────────────────────────────────────────────────┘")


class BusProfiler:
    def __init__(self):
        # Create performance monitor
        self.perf = BusMonitor(auto_start=False)

        # Configure multiple counters for different aspects
        self.perf.configure_counters(
            [0x07, 0x3F, 0x43, 0x0F])  # PROC0_ACCESS, XIP_MAIN0_ACCESS, ROM_ACCESS, FASTPERI_ACCESS

        # Setup data collection
        self.samples = 0
        self.total_values = [0, 0, 0, 0]
        self.max_values = [0, 0, 0, 0]
        self.min_values = [0xFFFFFF, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF]  # 24-bit max

    def configure_counters(self, events):
        """Configure performance counters with specified events."""
        self.perf.configure_counters(events)
        # Reset statistics when changing counters
        self._reset_statistics()

    def configure_preset(self, preset_name):
        """Configure counters using a predefined preset."""
        self.perf.configure_preset(preset_name)
        # Reset statistics when changing counters
        self._reset_statistics()

    def _reset_statistics(self):
        """Reset all statistical counters."""
        self.samples = 0
        self.total_values = [0, 0, 0, 0]
        self.max_values = [0, 0, 0, 0]
        self.min_values = [0xFFFFFF, 0xFFFFFF, 0xFFFFFF, 0xFFFFFF]

    def start_profiling(self):
        """Begin profiling session"""
        self.perf.reset_counters()
        self.perf.start_counters()
        self._reset_statistics()

    def sample_frame(self):
        """Collect data for current frame"""
        frame_data = self.perf.update_frame(reset_after=False, return_deltas=True)

        # Update statistics
        self.samples += 1

        for i in range(4):
            self.total_values[i] += frame_data[i]
            self.max_values[i] = max(self.max_values[i], frame_data[i])
            if frame_data[i] > 0:  # Only consider non-zero values for min
                self.min_values[i] = min(self.min_values[i], frame_data[i])

        return frame_data

    def get_profile_stats(self):
        """Get the current profiling statistics.

        Returns:
            Dictionary with profiling results
        """
        if self.samples == 0:
            return {"error": "No samples collected"}

        # Get current event names - important to do this here, not store them!
        event_names = self.perf.get_event_names()

        # Calculate averages
        avg_values = [total / self.samples for total in self.total_values]

        # Build results dictionary
        results = {
            "samples": self.samples,
            "events": [],
        }

        for i in range(4):
            results["events"].append({
                "name": event_names[i],
                "average": avg_values[i],
                "min": self.min_values[i] if self.min_values[i] < 0xFFFFFF else None,
                "max": self.max_values[i]
            })

        return results

    def display_profile_stats(self):
        """Display the current profiling statistics."""
        if self.samples == 0:
            print("No samples collected")
            return

        # Get current event names - important to do this here, not cache them!
        event_names = self.perf.get_event_names()

        # Calculate averages
        avg_values = [total / self.samples for total in self.total_values]

        # Display results
        print("\n=== Performance Profile Results ===")
        print(f"Samples collected: {self.samples}")
        print("\n┌─────────────────────────────────┬────────────┬────────────┬────────────┐")
        print("│ Event                           │ Average    │ Min        │ Max        │")
        print("├─────────────────────────────────┼────────────┼────────────┼────────────┤")

        for i in range(4):
            name = event_names[i]
            avg = f"{avg_values[i]:.2f}"
            min_val = str(self.min_values[i]) if self.min_values[i] < 0xFFFFFF else "N/A"
            max_val = str(self.max_values[i])

            print(f"│ {name:<31} │ {avg:>10} │ {min_val:>10} │ {max_val:>10} │")

        print("└─────────────────────────────────┴────────────┴────────────┴────────────┘")

    def end_profiling(self, reset=False):
        """End profiling and display results.

        Args:
            reset: Whether to reset the profiling statistics (default: False)
        """
        # Stop the performance counters
        self.perf.stop_counters()

        # Display current statistics
        self.display_profile_stats()

        # Reset if requested
        if reset:
            self._reset_statistics()

def main():
    monitor = BusMonitor()

    # Print welcome message and instructions
    print("\nRP2040 Bus Performance Monitor")
    print("==============================")
    print("This tool monitors the RP2040 bus fabric performance counters.")
    print("Available commands:")
    print("  p - List available presets")
    print("  e - List all event codes")
    print("  r - Read and display current counter values")
    print("  c - Reset counters")
    print("  m <duration_ms> - Monitor for specified duration (ms)")
    print("  s <preset> - Set counters using preset")
    print("  1-4 <event_code> - Configure counter 1-4")
    print("  q - Quit")

    # Start with a default preset
    monitor.configure_preset("core_activity")
    print("\nInitialized with 'core_activity' preset:")
    monitor.display_counters()

    while True:
        cmd = input("\nCommand: ").strip().split()

        if not cmd:
            continue

        if cmd[0] == 'q':
            break

        elif cmd[0] == 'p':
            monitor.list_presets()

        elif cmd[0] == 'e':
            monitor.list_available_events()

        elif cmd[0] == 'r':
            monitor.display_counters()

        elif cmd[0] == 'c':
            monitor.reset_counters()
            print("Counters reset")

        elif cmd[0] == 'm':
            if len(cmd) > 1 and cmd[1].isdigit():
                duration = int(cmd[1])
                monitor.monitor_for_duration(duration)
            else:
                print("Usage: m <duration_ms>")

        elif cmd[0] == 's':
            if len(cmd) > 1:
                monitor.configure_preset(cmd[1])
                monitor.display_counters()
            else:
                print("Usage: s <preset>")

        elif cmd[0] in '1234' and len(cmd) > 1:
            try:
                counter_idx = int(cmd[0]) - 1
                event_code = int(cmd[1], 0)  # Support decimal or hex (with 0x prefix)

                # Update just one counter
                current_events = monitor.selected_events.copy()
                current_events[counter_idx] = event_code
                monitor.configure_counters(current_events)

                print(f"Counter {cmd[0]} configured to monitor: {PERF_EVENTS.get(event_code, 'Unknown')}")
                monitor.display_counters()
            except ValueError:
                print(f"Invalid event code: {cmd[1]}")

        else:
            print("Unknown command. Type 'p' for presets, 'e' for events, or 'q' to quit.")


if __name__ == "__main__":
    main()
