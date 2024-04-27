from tkinter import Tk, Canvas


def main():
    root = Tk()
    root.geometry("600x400")

    square_size = 30
    canvas = Canvas(root, width=30 * 5 + 50, height=500)
    canvas.pack()
    labels = []
    sprites = []



    for i, my_color in enumerate(sprites):
        labels.append(canvas.create_rectangle(square_size * i, 0, square_size * (i + 1), square_size, fill=my_color))

    root.mainloop()


if __name__ == '__main__':
    main()
