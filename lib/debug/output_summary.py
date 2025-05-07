import re
import matplotlib.pyplot as plt
import pandas as pd
import io
from collections import defaultdict

def parse_summary_data(summary_content):
    """
    Parses the frame summary text data into a structure suitable for plotting.

    Args:
        summary_content: A string containing the summary data
                         (output from the previous script).

    Returns:
        A pandas DataFrame where index is frame number and columns are
        the memory block codes, containing their counts. Returns None if
        no data is found.
    """
    print("DEBUG: Parsing summary data...")
    frame_data = defaultdict(dict) # Using defaultdict to store {frame_num: {code: count}}
    current_frame = None
    # Regex to find the frame number
    frame_regex = re.compile(r"--- Frame (\d+) ---")
    # Regex to find the code counts
    code_regex = re.compile(r"Code '(.+)': (\d+) occurrences")

    log_stream = io.StringIO(summary_content)

    for line in log_stream:
        frame_match = frame_regex.search(line)
        code_match = code_regex.search(line)

        if frame_match:
            current_frame = int(frame_match.group(1))
            print(f"DEBUG: Found Frame {current_frame}")
        elif code_match and current_frame is not None:
            code = code_match.group(1)
            count = int(code_match.group(2))
            frame_data[current_frame][code] = count
            # print(f"DEBUG: Frame {current_frame}: Code '{code}' = {count}") # Optional detailed debug

    if not frame_data:
        print("DEBUG: No frame data parsed.")
        return None

    # Convert the dictionary to a pandas DataFrame
    # Using frame numbers as index directly
    df = pd.DataFrame.from_dict(frame_data, orient='index')
    # Fill missing values (if a code doesn't appear in a frame) with 0
    df = df.fillna(0).astype(int)
    # Sort columns alphabetically for consistent legend order, but prioritize '.'
    cols = sorted(df.columns)
    if '.' in cols:
      cols.insert(0, cols.pop(cols.index('.'))) # Move '.' to the front
    df = df[cols]

    print(f"DEBUG: Parsed data into DataFrame with shape {df.shape}")
    print("DEBUG: DataFrame columns:", df.columns.tolist())
    # print("DEBUG: DataFrame head:\n", df.head()) # Optional: print first few rows
    return df

def plot_frame_data(df, output_filename="memory_code_trends.png"):
    """
    Generates a line plot showing the trends of memory block codes over frames.

    Args:
        df: A pandas DataFrame with frame numbers as index and code counts as columns.
        output_filename: The name of the file to save the plot to.
    """
    if df is None or df.empty:
        print("ERROR: No data available to plot.")
        return

    print(f"DEBUG: Plotting data for {len(df.index)} frames and {len(df.columns)} codes.")

    plt.style.use('seaborn-v0_8-darkgrid') # Use a nice style
    fig, ax = plt.subplots(figsize=(14, 8)) # Create figure and axes

    # Plot each code type as a line
    for code in df.columns:
        # Don't plot codes if their max count is very low relative to others (optional)
        # if df[code].max() > df.values.max() * 0.01: # Example threshold
        ax.plot(df.index, df[code], marker='o', linestyle='-', label=f"Code '{code}'")

    # --- Customize the plot ---
    ax.set_title('Memory Block Code Counts per Frame', fontsize=16)
    ax.set_xlabel('Frame Number', fontsize=12)
    ax.set_ylabel('Number of Occurrences', fontsize=12)

    # Set x-axis ticks to be integers representing frame numbers
    ax.set_xticks(df.index)
    ax.tick_params(axis='x', rotation=45) # Rotate x-axis labels if many frames

    # Add a legend
    # Place legend outside the plot area to avoid overlap
    ax.legend(title="Block Codes", bbox_to_anchor=(1.04, 1), loc="upper left")

    # Add grid lines
    ax.grid(True, which='both', linestyle='--', linewidth=0.5)

    # Adjust layout to prevent labels overlapping
    plt.tight_layout(rect=[0, 0, 0.85, 1]) # Adjust rect to make space for legend

    # Save the plot to a file
    try:
        plt.savefig(output_filename)
        print(f"SUCCESS: Plot saved successfully as {output_filename}")
    except Exception as e:
        print(f"ERROR: Failed to save plot: {e}")

    # plt.show() # Optionally display the plot interactively if run locally

# --- Main execution part ---

# In a real script, you would read the summary file like this:

summary_file_path = 'frames-summary.txt'
try:
    with open(summary_file_path, 'r', encoding='utf-8') as f:
        summary_text = f.read()
except FileNotFoundError:
    print(f"Error: Summary file not found at {summary_file_path}")
    summary_text = None
except Exception as e:
     print(f"An error occurred reading the summary file: {e}")
     summary_text = None

# --- Simulation using fetched content ---
# This function will be called by the tool with the actual file content
def run_charting_on_fetched_content(fetched_summary_data):
    """Runs the parsing and charting using fetched summary data."""
    print("Running analysis on fetched summary content...")
    if fetched_summary_data:
        dataframe = parse_summary_data(fetched_summary_data)
        if dataframe is not None:
            plot_frame_data(dataframe) # Saves the plot as PNG
        else:
            print("Could not generate DataFrame from summary data.")
    else:
        print("No summary data was fetched or provided.")

# Example of how to call this if summary_text is loaded
# run_charting_on_fetched_content(summary_text_variable)

