import re
from collections import Counter
import io

def parse_mem_info_frames(log_content):
    """
    Analyzes the textual output from multiple MicroPython `micropython.mem_info(1)` calls,
    typically concatenated together in a single log file or string.

    This function processes the log content frame by frame. It identifies the
    start of a new frame by looking for the characteristic "stack:" line.
    It collects memory map lines (those starting with a hex address like '00000000:')
    that appear *after* a "stack:" line and *before* the next "stack:" line.

    Args:
        log_content: A string containing the potentially multi-frame log data
                     from `micropython.mem_info(1)`.

    Returns:
        A list of `collections.Counter` objects. Each `Counter` in the list
        represents one detected frame's map data, mapping the character codes
        found to their respective counts. The list is ordered according to the
        sequence of frames found in the input `log_content`.
    """
    print("DEBUG: Starting parse_mem_info_frames (using revised stack: delimiter)...") # DEBUG
    frame_results = []
    # Will hold the counter for the frame currently being processed
    current_frame_codes = None
    line_number = 0 # DEBUG

    # Regex to find lines containing the memory layout data
    map_line_regex = re.compile(r"^[0-9a-fA-F]{8}:\s*([.=hTMA=BFSALD\s]+)\s*$")
    # Regex to detect the start of the mem_info block, used as frame delimiter. Case-insensitive.
    frame_start_regex = re.compile(r"^\s*stack:", re.IGNORECASE)

    log_stream = io.StringIO(log_content)

    for line in log_stream:
        line_number += 1
        stripped_line = line.strip()

        # Check if this line marks the beginning of a new frame
        if frame_start_regex.match(line):
            print(f"DEBUG: Line {line_number}: Found frame start marker: '{stripped_line}'") # DEBUG
            # If we were processing a previous frame, store its results *if* it had codes
            if current_frame_codes is not None and current_frame_codes:
                 print(f"DEBUG: Storing previous frame data (found {len(current_frame_codes)} code types).") # DEBUG
                 frame_results.append(current_frame_codes)
            elif current_frame_codes is not None:
                 print(f"DEBUG: Previous frame started but no map codes collected.") # DEBUG

            # Start a new counter for the new frame
            current_frame_codes = Counter()

        # If we have started a frame (current_frame_codes is initialized)...
        elif current_frame_codes is not None:
            # Check if the current line is a map line
            map_match = map_line_regex.match(line)
            if map_match:
                 # DEBUG: Print first map line found for this frame
                 # if not current_frame_codes:
                 #    print(f"DEBUG: Line {line_number}: Found first map line for current frame: '{stripped_line}'") # DEBUG

                 # Extract codes from the matched map line
                 codes_part = map_match.group(1)
                 for char in codes_part:
                     if not char.isspace():
                         current_frame_codes[char] += 1
            # else: This line is within a frame but not a 'stack:' line and not a map line.
            # Examples: GC:, No. of blocks:, GC memory layout:, None, *** POOL...
            # We simply ignore these lines for the purpose of code counting.
            # Optional debug print:
            # elif stripped_line:
            #      print(f"DEBUG: Line {line_number}: Ignoring non-map/non-start line within frame: '{stripped_line[:60]}...'")


    # After processing all lines, store the last frame's data if it exists and has codes
    print(f"DEBUG: Finished processing lines. Checking for last frame data...") # DEBUG
    if current_frame_codes is not None and current_frame_codes:
        print(f"DEBUG: Storing last frame data (found {len(current_frame_codes)} code types).") # DEBUG
        frame_results.append(current_frame_codes)
    elif current_frame_codes is not None:
         print(f"DEBUG: Last frame started but no map codes collected.") # DEBUG
    else:
        print(f"DEBUG: No 'stack:' line found in the entire log.") # DEBUG


    print(f"DEBUG: parse_mem_info_frames finished. Found {len(frame_results)} frames based on 'stack:' delimiter.") # DEBUG
    return frame_results

def print_frame_summaries(frame_data):
    """
    Prints the summary counts for each frame and a legend.

    Args:
        frame_data: A list of collections.Counter objects, as returned by
                    `parse_mem_info_frames`.
    """
    print("\n--- Per-Frame Summary of GC Block Codes ---") # Add newline for spacing after debug prints
    if not frame_data:
        print("No GC block data frames found in the log.")
        print("Check if the log file contains 'stack:' lines followed by hex address lines (e.g., '00000000: ...').")
        return

    # Define a sort key for consistent ordering of codes within each frame's output
    def sort_key(item):
        char = item[0]
        if char == '=': return 0 # Prioritize '='
        if char == '.': return 1 # Then '.'
        return 2 # All other codes after

    # Iterate through each frame's Counter object
    for i, code_counts in enumerate(frame_data):
        print(f"\n--- Frame {i+1} ---")
        if not code_counts:
            print("  (No map codes found in this frame)") # Should be less likely now
            continue

        # Sort the counts for this frame before printing
        sorted_counts = sorted(code_counts.items(), key=sort_key)
        for code, count in sorted_counts:
            print(f"  Code '{code}': {count} occurrences")

    # Print the legend once at the end
    print("\n--- Legend (Common Interpretations) ---")
    print("  = : Marked tail block (part of marked multi-block allocation)")
    print("  . : Free block")
    print("  h : Head block (start of an allocation)")
    print("  T : Tail block (part of a multi-block allocation)")
    print("  M : Marked head block (live object, marked during GC)")
    print("  A : Available head block (free, previously allocated)")
    print("  B : Busy head block (allocated object)")
    print("  S : STACK block (memory reserved for stack)")
    print("  F : Finalized head block (object needs __del__ call)")
    print("  L : Locked head block (cannot be moved by GC)")
    print("  D : Data block (contains object data)")
    print("  (Note: Exact meanings can vary slightly between MicroPython ports/versions)")

# --- Main execution part (Example Usage) ---
# !!! IMPORTANT: Replace 'gc-log-one-frame.txt' with the actual path to your log file !!!
# Use 'gc-log-sample-frame.txt' if you want to test with the sample provided
file_path = 'gc-log-full-log.txt'
print(f"Attempting to read log file: {file_path}") # DEBUG
try:
    # Read the entire log file content
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: # Added encoding/error handling
        log_data = f.read()
    print(f"Successfully read {len(log_data)} bytes from {file_path}") # DEBUG
    # Parse the log data into frames
    frames = parse_mem_info_frames(log_data)
    # Print the summaries for the parsed frames
    print_frame_summaries(frames)
except FileNotFoundError:
    print(f"Error: File not found at {file_path}")
    print("Please ensure the file exists and the path is correct.")
except Exception as e:
    print(f"An error occurred: {e}")

# --- Simulation using fetched content ---
# This part can be used if the log data is passed as a string variable
def run_analysis_on_fetched_content(fetched_log_data):
    """Runs the per-frame parsing and printing using fetched data."""
    print("Parsing fetched log content frame by frame...")
    frames = parse_mem_info_frames(fetched_log_data)
    print_frame_summaries(frames)
    print("\nAnalysis complete.")

