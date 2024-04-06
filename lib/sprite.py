from microbmp import MicroBMP as bmp

def load_bmp(filename):
    """Loads an image from a BMP file and converts it to a binary RGB565 stream for later display"""
    image = bmp().load(filename)
    
    return {
        'data':image.rgb565(),
        'width': image.DIB_w,
        'height':image.DIB_h
    }