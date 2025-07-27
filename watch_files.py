import os
import time
import subprocess
import sys

# Add /lib to the system path to import the print_utils module
sys.path.append(os.path.join(os.getcwd(), 'lib'))

from windows_toasts import Toast, ToastDuration, WindowsToaster
from scaler.const import INK_GREEN
from print_utils import printc

# Set the directory to monitor
project_root = os.getcwd()
directory_to_monitor = os.path.join(project_root)

# Set the path to the MicroPython tools
micropython_tools_path = '\\Users\\ghurtado\\Development\\MicroPython\\micropython\\tools'

# Dictionary to store the last modification time of each file
file_timestamps = {}

# ANSI escape codes for color formatting
RED = "\033[91m"
RESET = "\033[0m"
COM = "COM4"        # this might change over time

def upload_file(file_path):
    try:
        # Change directory to the project root
        os.chdir(project_root)

        # Determine the relative path of the file from the project root
        relative_path = os.path.relpath(file_path, project_root)

        # Use MicroPython tools to upload the file
        pyboard_bin = os.path.join(micropython_tools_path, 'pyboard.py')
        subprocess.run(
            [
                "python",
                pyboard_bin,
                "--device", COM, "-f", "cp",
                file_path,
                ":/" + relative_path
            ],
            check=True,
            capture_output=True
        )

        # Print success message
        msg = f"/{relative_path} uploaded to :/{relative_path}"
        msg = msg.replace('\\', '/')
        printc(msg, INK_GREEN)

        # Success! - show Windows toast
        toaster = WindowsToaster('File Watcher')
        newToast = Toast(duration=ToastDuration.Short)
        newToast.text_fields = [f"File uploaded:\n {relative_path}"]
        toaster.show_toast(newToast)

    except subprocess.CalledProcessError as e:
        printc(f"Error uploading file: {file_path}\nError message: {str(e)}")
    except Exception as e:
        printc(f"Unexpected error uploading file: {file_path}\nError message: {str(e)}")

def monitor_directory():
    print(f"Monitoring directory {directory_to_monitor}")

    while True:
        try:
            # Iterate over all files in the directory
            for root, dirs, files in os.walk(directory_to_monitor):
                for file in files:
                    # Check if the file has a .py extension
                    if file.endswith(".py") or file.endswith(".bmp"):
                        file_path = os.path.join(root, file)

                        # Get the current modification time of the file
                        current_timestamp = os.path.getmtime(file_path)

                        # Check if the file has been modified
                        if file_path in file_timestamps and current_timestamp != file_timestamps[file_path]:
                            print(f"File modified: {file_path}")
                            upload_file(file_path)

                        # Update the timestamp in the dictionary
                        file_timestamps[file_path] = current_timestamp

            # Wait for a short interval before checking again
            time.sleep(1)
        except KeyboardInterrupt:
            print("Monitoring stopped by user.")
            break
        except Exception as e:
            print(f"{RED}Unexpected error monitoring directory: {str(e)}{RESET}")


# Start monitoring the directory
if __name__ == '__main__':
    monitor_directory()