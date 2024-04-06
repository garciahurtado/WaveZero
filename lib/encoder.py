from machine import Pin

class RotaryEncoder:
    def __init__(self, clk_pin, dt_pin):
        self.clk_pin = clk_pin
        self.dt_pin = dt_pin
        
        # Initialize the pins
        self.clk = Pin(self.clk_pin, Pin.IN, Pin.PULL_UP)
        self.dt = Pin(self.dt_pin, Pin.IN, Pin.PULL_UP)
        
        # Variables to store the encoder state
        self.position = 0
        self.clk_last_state = self.clk.value()
        
        # Attach interrupt handler to the CLK pin
        self.clk.irq(trigger=Pin.IRQ_FALLING | Pin.IRQ_RISING, handler=self.handle_rotation)
    
    def handle_rotation(self, pin):
        clk_state = self.clk.value()
        dt_state = self.dt.value()
        
        if clk_state != self.clk_last_state:
            if dt_state != clk_state:
                self.position += 1
            else:
                self.position -= 1
            
            print("Position:", self.position)
        
        self.clk_last_state = clk_state
    
    def get_position(self):
        return self.position

