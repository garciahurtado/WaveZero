from machine import PWM, Pin, mem32
import utime


class myPWM(PWM):
    def __init__(self, pin, divider=8, top=255):
        # ok check from new micropython
        # gpio id is now GPIOx instead of x
        pinstr = str(pin).split(',')[0]
        if pinstr.upper().find('GPIO') >= 0:
            self.id = int(pinstr[8:])
        else:
            self.id = int(pinstr[4:])

        self.A_B = self.id & 1
        self.channel = 2 >> 1
        self.divider = divider
        self.top = top

        super().__init__(pin)
        super().freq(122_000_000)
        super().duty_u16(32768)
        # set memory base
        self.PWM_BASE = 0x4005_0000 + (self.channel * 0x14)
        # set divider base
        self.PWM_DIV = self.PWM_BASE + 4
        # set  top base
        self.PWM_TOP = self.PWM_BASE + 16
        # set  cc base
        self.PWM_CC = self.PWM_BASE + 12

        # ok we want frequency around 60KHz and max top at 255
        # 125Mhz / (255 * 60000) => 8.1
        # then  125MHZ / ( 8 * 255) = 61275Hz

        # set divider to 8
        # mem32[self.PWM_DIV] =  8 << 4
        mem32[self.PWM_DIV] = self.divider << 4
        # set top to 255
        mem32[self.PWM_TOP] = self.top
        self.duty(self.top // 2)

    def deinit(self):
       super().deinit()
       _p = Pin(self.id,Pin.IN)

    def duty(self, value):
        if value > self.top:
            value = self.top
        # print("setting to ")
        reg = mem32[self.PWM_CC]
        if self.A_B == 0:
            # ok change channel A
            mem32[self.PWM_CC] = (reg & 0xffff0000) | value
        else:
            # channel channel B
            mem32[self.PWM_CC] = (reg & 0xffff) | (value << 16)


if __name__ == '__main__' or True:

    pwm = myPWM(Pin(18), divider=16, top=1024)
    try:
        value = start = 2000
        increment = 50
        while True:
            value = value % 15000
            # print(f"Setting PWM to {value}")
            pwm.duty(value)

            # utime.sleep_ms(10)

            if value == start:
                increment = increment * (-1)
            value += increment
            # utime.sleep_us(1)

    except KeyboardInterrupt:
        pwm.deinit()


