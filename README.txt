WaveZero Development
====================

- In a CMD window, run:
python ./watch_files.py

- This will automatically sync any workspace code changes to the rpi pico
- Sometimes, the copy process will not work if the pico is locked up
- In that case, you may need to save the file and trigger the copy right as the pico is booting up:
    - Press RESET on the pico (or perform a soft reset via the console)
    - Quickly save the file in the IDE
    - The file watcher should be able to catch the change and copy the file to the pico. This will also stop the program from starting all the way.

How to remove all profiler statements from the project source:

[^\n]*prof\.\w*_profile\(.*$