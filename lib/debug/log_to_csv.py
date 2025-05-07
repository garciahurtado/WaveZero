import re
import pandas as pd
import io
from collections import defaultdict

def parse_ini_log(log_content):
    """
    Parses multi-block INI-style log entries into a list of dictionaries.

    Args:
        log_content: A string containing the captured log output.

    Returns:
        A list of dictionaries, where each dictionary represents one log entry.
        Returns an empty list if parsing fails or no entries are found.
    """
    parsed_data = []
    current_entry = {}
    # Regex to find the start of a log block, e.g., [LOG_1_1]
    entry_start_regex = re.compile(r"^\[LOG_(\d+)_(\d+)\]$")
    # Regex to find key = value pairs, stripping whitespace
    key_value_regex = re.compile(r"^\s*(\w+)\s*=\s*(.*)\s*$")

    log_stream = io.StringIO(log_content)

    for line in log_stream:
        stripped_line = line.strip()

        start_match = entry_start_regex.match(stripped_line)
        kv_match = key_value_regex.match(stripped_line)

        if start_match:
            # If we find a new entry start and have data in the current_entry,
            # save the completed previous entry.
            if current_entry:
                parsed_data.append(current_entry)
            # Start a new entry (frame and seq from header are redundant but ok)
            current_entry = {}
            # Optionally store frame/seq from header if needed:
            # current_entry['header_frame'] = int(start_match.group(1))
            # current_entry['header_seq'] = int(start_match.group(2))

        elif kv_match and current_entry is not None:
            # If we are inside an entry block, add the key-value pair
            key = kv_match.group(1)
            value = kv_match.group(2)
            # Attempt to convert numeric values, keep others as string
            try:
                if '.' in value: # Basic float check
                     current_entry[key] = float(value)
                else:
                     current_entry[key] = int(value)
            except ValueError:
                current_entry[key] = value # Keep as string if conversion fails

    # Append the very last entry after the loop finishes
    if current_entry:
        parsed_data.append(current_entry)

    return parsed_data

def create_pivoted_csv(parsed_data):
    """
    Converts the parsed log data into a pivoted CSV string.

    Args:
        parsed_data: A list of dictionaries (output from parse_ini_log).

    Returns:
        A string containing the data in CSV format (frames as rows, tags as columns),
        or None if input data is empty.
    """
    if not parsed_data:
        print("No parsed data to process.")
        return None

    try:
        # Create DataFrame from the list of dictionaries
        df = pd.DataFrame(parsed_data)

        # Ensure essential columns exist
        if 'frame' not in df.columns or 'tag' not in df.columns or 'free' not in df.columns:
             print("ERROR: Parsed data missing required columns ('frame', 'tag', 'free').")
             # print("DEBUG: Available columns:", df.columns.tolist())
             return None

        # Pivot the table: index=frame, columns=tag, values=free memory
        # Use max() as aggregator if multiple entries exist for same frame/tag (takes last seq usually)
        # Alternatively, use first(), last(), mean() etc. if needed.
        pivot_df = df.pivot_table(index='frame', columns='tag', values='free', aggfunc='last')

        # Get columns in a somewhat logical order (FRAME_START first, then alphabetical)
        cols = sorted([col for col in pivot_df.columns if col != 'FRAME_START'])
        if 'FRAME_START' in pivot_df.columns:
             cols.insert(0, 'FRAME_START')
        pivot_df = pivot_df[cols]


        # Convert to CSV string
        # Keep NaN as empty strings in CSV for clarity
        csv_output = pivot_df.to_csv(index=True, na_rep='')

        return csv_output

    except Exception as e:
        print(f"ERROR creating pivoted CSV: {e}")
        # print("DEBUG: DataFrame head before pivot:\n", df.head()) # Optional debug
        return None

# --- Main execution part (Example Usage) ---

# 1. Capture the console output from your MicroPython script
#    (containing the INI-like logs) and save it to a file (e.g., "captured_log.txt").

# 2. Run this script, providing the captured log file path.

log_file_path = 'frames-memory-labels.txt' # <--- CHANGE THIS to your captured log file

try:
    print(f"Reading log file: {log_file_path}")
    with open(log_file_path, 'r') as f:
        log_content = f.read()

    print("Parsing log content...")
    parsed_entries = parse_ini_log(log_content)

    if parsed_entries:
        print(f"Parsed {len(parsed_entries)} log entries.")
        print("Creating pivoted CSV...")
        csv_data = create_pivoted_csv(parsed_entries)

        if csv_data:
            # Save the CSV data to a new file
            csv_filename = "memory_log_pivoted.csv"
            print(f"Saving pivoted data to {csv_filename}...")
            with open(csv_filename, 'w') as f_csv:
                f_csv.write(csv_data)
            print("CSV file saved successfully.")
            # print("\n--- CSV Output ---")
            # print(csv_data) # Optionally print CSV to console
        else:
            print("Failed to generate CSV data.")
    else:
        print("No valid log entries found in the file.")

except FileNotFoundError:
    print(f"Error: Log file not found at {log_file_path}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")

