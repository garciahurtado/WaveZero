def rgb_to_hex(r, g, b):
    return f"#{r:02x}{g:02x}{b:02x}"

def process_file(input_file):
    with open(input_file, 'r') as infile:
        for line in infile:
            r, g, b = map(int, line.strip().split(','))
            hex_value = rgb_to_hex(r, g, b)
            print(hex_value)

if __name__ == "__main__":
    input_file = "temp_gradient.txt"
    process_file(input_file)