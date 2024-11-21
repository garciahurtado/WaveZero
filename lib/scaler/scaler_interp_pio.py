from rp2 import PIO, asm_pio


@asm_pio(
    out_shiftdir=PIO.SHIFT_RIGHT,
    in_shiftdir=PIO.SHIFT_LEFT,
    autopull=True,
    pull_thresh=32,
    sideset_init=(PIO.OUT_LOW,)
)
def indexed_sprite_handler():
    # Setup phase
    pull().side(0)  # Get palette base address
    mov(y, osr).side(1)  # Store in Y
    pull().side(0)  # Get sprite data address
    mov(x, osr).side(1)  # Store in X

    label("wrap_target")
    wrap_target()
    # Get pixel pair - use interpolator for address calc
    in_(pins, 32).side(0)  # Output address to interpolator
    out(pins, 8).side(1)  # Read byte containing two 4-bit indices

    # Process high nibble
    out(null, 4)  # Align to high nibble
    # Use interpolator for palette lookup instead of addition
    mov(isr, y)  # Load palette base
    in_(pins, 32)  # Send to interpolator for offset calc
    out(pins, 16)  # Get color from interpolator
    in_(pins, 16).side(0)  # Output to display

    # Process low nibble
    out(null, 4)  # Align to low nibble
    mov(isr, y)  # Load palette base again
    in_(pins, 32)  # Send to interpolator
    out(pins, 16)  # Get color

    in_(pins, 16).side(1)  # Output to display
    push()

    # Advance to next byte
    jmp(x_dec, "wrap_target")
    wrap()

@asm_pio(
    in_shiftdir=PIO.SHIFT_RIGHT,    # Input data shifts right
    out_shiftdir=PIO.SHIFT_LEFT,    # Push data shifts left
    autopull=True,                  # Auto pull from FIFO
    pull_thresh=32,                 # Pull full words
    autopush=True,                  # Auto push to FIFO when ISR full
    push_thresh=4,                  # Push every 4 bits (one index)
)
def palette_lookup():
    wrap_target()
    out(isr, 4)               # Extract 4 bits into ISR
    wrap()                    # Loop for next 4 bits