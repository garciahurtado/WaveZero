from machine import Pin
from utime import sleep

class Screen:
  def __init__(self):
    self.setup()
    
  def setup(self):
    self.led1 = Pin(6, Pin.OUT)
    self.led2 = Pin(7, Pin.OUT)
    self.led3 = Pin(8, Pin.OUT)
    self.led4 = Pin(9, Pin.OUT)

  def run(self):
    leds = [self.led1, self.led2, self.led3, self.led4]

    while True:
      for myled in leds:
        myled.toggle()
        sleep(0.1)
        myled.toggle()
      sleep(0.5)

print("Starting....")
scr = Screen()
scr.run()
