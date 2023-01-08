import adafruit_imageload.bmp.indexed
import displayio
import time

def show_title(display, root):
    # "Wave"
    title1_bitmap, title1_palette = adafruit_imageload.load(
    "/title_wave.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette
)
   
    
    num_colors = len(title1_palette) - 1
    # Make transparent before we show the bitmap
    for i in range(0, num_colors):
        title1_palette.make_transparent(i)
        
    title1_grid = displayio.TileGrid(title1_bitmap, pixel_shader=title1_palette, x=0, y=0)
    
    root.append(title1_grid)
    display.show(root)
    
    # Do some color transitions manipulating the palette
    for i in range(num_colors, -1, -1):  
        title1_palette.make_opaque(i)
        display.refresh()
        time.sleep(0.15)
       
    title1_palette.make_transparent(0)
    
    # Make the bitmap white
    white_palette = displayio.Palette(255)
    for i in range(1, 255):
        white_palette[i] = 0xFFFFFF
        
    title1_grid.pixel_shader = white_palette
    white_palette.make_transparent(0)
    
    # just a flash
    display.refresh()
    time.sleep(0.01)
    title1_grid.pixel_shader = title1_palette
    display.refresh()
    
    
    # "Zero"
    title2_bitmap, title2_palette = adafruit_imageload.load(
    "/title_zero.bmp", bitmap=displayio.Bitmap, palette=displayio.Palette
)
    
    title2_palette.make_transparent(0)
    title2_grid = displayio.TileGrid(title2_bitmap, pixel_shader=title2_palette, x=100, y=15)
    root.append(title2_grid)
    display.refresh()
    
    for x in range(100, 0, -1):
        title2_grid.x = x
        display.refresh()
    
    title1_grid.pixel_shader = white_palette
    title2_grid.pixel_shader = white_palette
    
    # just a flash
    display.refresh()
    time.sleep(0.15)
    title1_grid.pixel_shader = title1_palette
    title2_grid.pixel_shader = title2_palette
    display.refresh()
    
    new_palette = displayio.Palette(len(title1_palette))
    
    for i in range(0, len(title1_palette)):     
        # rotate palette list by one
        new_palette = displayio.Palette(len(title1_palette))
        new_palette[-1] = title1_palette[i]
        
        for j in range(0, len(title1_palette) - 1):
            new_palette[j] = title1_palette[j+1]
            
        title1_palette = new_palette
        display.refresh()
    
    time.sleep(4)
    
    # Clear the screen
    root.remove(title1_grid)
    root.remove(title2_grid)