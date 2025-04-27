import utime
from machine import Pin
from rotary_irq import RotaryIRQ

pin_num_clk = 27
pin_num_dt = 26

def irq_handler():
    print("/// THE HANDLER WAS CALLED ///")
    pass

print("Binding RotaryIRQ controller...")
utime.sleep(1)

input_handler = RotaryIRQ(
    pin_num_clk=pin_num_clk,
    pin_num_dt=pin_num_dt,
    range_mode=RotaryIRQ.RANGE_UNBOUNDED,
    half_step=False,
)

print("\nSo far so good...\n")

# my_pin = Pin(pin_num_dt, mode=Pin.IN, pull=None)
#
# my_pin.irq(handler=irq_handler, hard=True)

print("\n... And we got to the end\n")

