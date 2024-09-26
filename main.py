import gc
import sys
from utime import sleep

# import frozen_img # Created with freezefs: https://github.com/bixb922/freezeFS
from screens.screen_app import ScreenApp
from screens.game_screen import GameScreen

# from test_screen import TestScreen
import micropython
import time
import machine
# import test_midi as midi
# import pio_led_test
# import simple_audio_test
# import pwm_audio_test
# import square_wave_test
# import wav.myPWM
# import midi.midi_player_2 as midi
# from midi.simple_pwm_player import SimplePwmPlayer
# import lib.pwm_with_trigger_pin as pwm_player

from machine import Pin

from screens.test_screen import TestScreen


def main():
    # micropython.opt_level(0)

    # machine.freq(250_000_000)
    machine.freq(40_000_000)

    current_freq = machine.freq()
    print(f"CPU: {current_freq / 1_000_000} MHz")

    check_mem()
    print("Compiler opt level: " + str(micropython.opt_level()))

    time.sleep(1)

    # midi_test()
    # return False

    app = ScreenApp(96, 64)
    # app.load_screen(GameScreen(app.display))
    # app.load_screen(TitleScreen(app.display))
    app.load_screen(TestScreen(app.display))

    print("After loading screen class")
    app.run()

def check_mem():
    gc.collect()
    print(micropython.mem_info())

def midi_test():
    player = pwm_player.audio_pwmSimplePwmPlayer(Pin(18))

    print("Play 440")
    player.play(440, 2)

    print("Play 220")
    player.play(220, 2)

    print("Play 880")
    player.play(880, 2)

    print("Play 440")
    player.play(440, 0.5)
    sleep(5)
    player.stop()

    sys.exit(1)

if __name__ == "__main__":
    print("======== APP START ========")
    print(micropython.mem_info())
    main()
