def dump_object(obj):
    # Get all attributes of the object
    attributes = dir(obj)

    print(f"Properties of {type(obj).__name__} object:")
    for attr in attributes:
        # Skip double underscore attributes
        if attr.startswith("__"):
            continue

        try:
            value = getattr(obj, attr)
            # Check if it's a method
            if callable(value):
                print(f"{attr}: <method>")
            else:
                print(f"{attr}: {value}")
        except Exception as e:
            print(f"{attr}: <unable to access: {str(e)}>")

def dump_sprite(sprite):
    
    print(f"sprite.x={sprite.x}")
    print(f"sprite.y={sprite.y}")
    print(f"sprite.z={sprite.z}")
    print(f"sprite.draw_x = {sprite.draw_x}")
    print(f"sprite.draw_y = {sprite.draw_y}")
    print(f"sprite.speed={sprite.speed}")
    print(f"sprite.visible={sprite.visible}")
    print(f"sprite.active={sprite.active}")