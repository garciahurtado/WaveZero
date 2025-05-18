import gc
import time # Needed for timestamp
import micropython # Needed for mem_info (though we comment out the call below)

from scaler.const import DEBUG_LOG_MEM

_log_seq = 0 # Global sequence counter for log messages within a frame
_current_frame_num = 0 # Internal frame counter, managed by log_new_frame()

def log_new_frame():
    """
    Signals the start of a new logical frame for logging.
    Increments the internal frame counter and resets the sequence counter.
    Call this ONCE at the beginning of each frame/iteration you want to track.
    Prints a FRAME_START marker in INI-like format.
    """
    if not DEBUG_LOG_MEM:
        return False # Fail silently, the user doesn't want memory logging

    global _current_frame_num, _log_seq

    _current_frame_num += 1
    # Reset log sequence counter for each new frame
    _log_seq = 0
    # print(f"\n--- Starting Frame {_current_frame_num} ---") # Human-readable marker (optional)

    # Log a specific marker for frame start using the log_mem function
    # This ensures consistent formatting for frame boundaries
#    log_mem("FRAME_START")

def log_mem(tag_description):
    """
    Logs the current free memory with the current frame number, sequence number,
    timestamp, and descriptive tag directly to the console in an INI-like format.
    Uses the internal frame counter. Adds extra newlines for visibility.
    """
    if not DEBUG_LOG_MEM:
        return False # Fail silently, the user doesn't want memory logging

    global _log_seq, _current_frame_num
    _log_seq += 1

    # Ensure a frame has been started before logging (optional check)
    if _current_frame_num == 0 and tag_description != "FRAME_START":
        print("WARNING: log_mem called before log_new_frame() was ever called for Frame 1.")
        # Decide how to handle this - log as frame 0? Skip?
        # For now, allow logging but frame number might be 0 if called too early.
        pass

    # Optional: Uncomment the next line to force garbage collection before
    # checking memory. This gives a 'post-GC' view but adds overhead.
    # gc.collect()

    free_mem = gc.mem_free()
    # Use ticks_us for potentially higher resolution timestamp if available and needed
    timestamp_us = time.ticks_us()

    # --- MODIFIED: Format output as INI-like block ---
    print()
    print(f"[LOG_{_current_frame_num}_{_log_seq}]") # Header for the log entry
    print(f"frame = {_current_frame_num}")
    print(f"seq = {_log_seq}")
    print(f"time_us = {timestamp_us}")
    # Ensure tag doesn't contain characters that break INI parsing if needed later
    # (e.g., replacing '=' or newlines, though less critical for simple parsing)
    cleaned_tag = str(tag_description).replace('\n', ' ').replace('\r', '')
    print(f"tag = {cleaned_tag}")
    print(f"free = {free_mem}")
    # --- End of modification ---


# --- End of Memory Logging Setup ---

# --- Example Usage in Your Code ---
# Note: Functions no longer need frame_num passed to them for logging purposes

# Example 1: Logging function entry and exit
def process_data(data_chunk): # No frame_num needed
#    log_mem("process_data_START") # Log at the beginning

    # ... your function logic here ...
    processed_result = data_chunk.decode('utf-8') # Example operation
    # ... more logic ...
#
    log_mem("process_data_END") # Log at the end
    return processed_result

# Example 2: Logging before and after a loop known to allocate
def handle_incoming_requests(requests): # No frame_num needed
    log_mem("handle_requests_START")
    results = []
    log_mem("handle_requests_LOOP_BEFORE")
    for i, req in enumerate(requests):
        log_mem(f"handle_requests_LOOP_ITER_{i}_START") # Optional
        temp_data = {"id": i, "payload": list(req)}
        results.append(temp_data)
        log_mem(f"handle_requests_LOOP_ITER_{i}_END") # Optional

    log_mem("handle_requests_LOOP_AFTER")
    # ... potentially process results ...
    log_mem("handle_requests_END")
    return results

# Example 3: Logging around potentially large allocations or resource use
# def read_config_file(filepath): # No frame_num needed
# #    log_mem(f"read_config_START: {filepath}")
#     config_content = None # Define outside try
#     f = None # Define outside try
#     try:
#         f = open(filepath, 'r')
# #        log_mem("read_config_FILE_OPENED")
#         config_content = f.read() # Reading the whole file might allocate significant memory
# #        log_mem("read_config_READ_COMPLETE")
#     except Exception as e:
# #        log_mem(f"read_config_ERROR: {e}")
#         config_content = None
#     finally:
#         # Ensure file is closed if it was successfully opened
#         if f:
#             try:
#                 f.close()
# #                log_mem("read_config_FILE_CLOSED")
#             except Exception as e_close:
#                 pass
# #                 log_mem(f"read_config_CLOSE_ERROR: {e_close}")
# #
#     log_mem("read_config_END")
#     return config_content

# Example 4: Triggering the full mem_info dump periodically along with logs
# Assume this runs in your main loop or a periodic task

# while True:
#     # --- Signal Start of New Frame ---
#     log_new_frame() # Call this once per frame/iteration
#
#     # --- Your main application logic ---
#     log_mem("MAIN_LOOP_TOP")
#
#     # Simulate some work
#     config = read_config_file("settings.cfg") # Example call
#     if config:
#          log_mem("MAIN_LOOP_CONFIG_PROCESSED")
#
#     requests_to_handle = [b'req1', b'req2', b'req3'] # Dummy data
#     handle_incoming_requests(requests_to_handle) # Example call
#     log_mem("MAIN_LOOP_REQUESTS_HANDLED")
#     # --- End of main logic ---
#
#
#     # --- Trigger the detailed memory dump ---
#     # --- MODIFIED: Commented out the mem_info(1) call ---
#     # print("\n--- MEM_INFO_DUMP_START ---")
#     # micropython.mem_info(1) # This is often too verbose
#     # print("--- MEM_INFO_DUMP_END ---\n")
#     # --- End of dump ---
#
#     # --- Optional: Log basic free memory once per loop ---
#     # If you still want *some* regular memory check without the full dump:
#     # log_mem("MAIN_LOOP_MEM_CHECK") # Uses the standard INI format
#
#     log_mem("MAIN_LOOP_BOTTOM")
#
#     # Add a delay or other loop control
#     time.sleep(5) # Example delay

