This folder contains the "original" font files in Python source code, generated with font_to_py.py

To save memory, these files are compiled into frozen .mpy modules by the mpy cross-compiler, placed into /fonts,
and imported at runtime with:

1. move the .py source file to ~/micropython/ports/rp2/modules/fonts
2. compile it as an .mpy with: 

cd ~/micropython
./mpy-cross/build/mpy-cross ./ports/rp2/modules/fonts/m42_9px.py