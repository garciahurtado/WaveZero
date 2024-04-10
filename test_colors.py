from tkinter import *
from tkinter import ttk
import lib.color_old as colors

def main():
    root = Tk()
    root.geometry("600x400")

    # Create a color palette
    color1 = (0,255,255)
    color2 = (0,0,255)

    red = [200,0,0]
    mag = [255,0,100]
    cyan = [66, 242, 245]
    blue = [20,80,255]
    horiz_far = [92, 0, 24]
    horiz_near = [0, 238, 255]

    all_colors = colors.make_palette(horiz_far, horiz_near, 10)
    print(all_colors)
    canvas = Canvas(root, width = 500, height = 500)
    canvas.pack()
    
    labels = []

    square_size = 30
    for i, my_color in enumerate(all_colors):
        
        #my_color = colors.rgb565_to_rgb(color_565)
        
        my_color = colors.rgb_to_hex(my_color)
        print(i, my_color)
        labels.append(canvas.create_rectangle(square_size*i, 0, square_size*(i+1), square_size, fill=my_color))

    root.mainloop()


def horiz_test():
    root = Tk()
    root.geometry("600x400")


    horiz_far = [92, 0, 24]
    horiz_near = [0, 238, 255]

    num_horiz_colors = 24
    horiz_palette = colors.make_palette(horiz_near, horiz_far, num_horiz_colors)
    horiz_palette.insert(0, [0, 0, 0])
    draw_palette(horiz_palette, root)

def draw_palette(palette, root):
    square_size = 30
    canvas = Canvas(root, width=30*len(palette)+50, height=500)
    canvas.pack()
    labels = []
    for i, my_color in enumerate(palette):
        # my_color = colors.rgb565_to_rgb(color_565)

        my_color = colors.rgb_to_hex(my_color)
        print(i, my_color)
        labels.append(canvas.create_rectangle(square_size * i, 0, square_size * (i + 1), square_size, fill=my_color))

    root.mainloop()


if __name__ == '__main__':
    # main()
    horiz_test()