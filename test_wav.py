'''
    (c) 2021  Daniel Perron
    MIT License

    example of audio output using PWM and DMA
    right now it  works only with wave file at
    8000 sample rate , stereo or mono, and 16 bits audio

    GPIO  2 & 3  pin 4 and 5 are the output
    You need to use headphones with a 1K resistor in series on
    left and right speaker

    The myPWM subclass set the maximum count to 255 at a frequency around  122.5KHz.

    The myDMA class allow to use direct memory access to transfer each frame at the current sample rate


    You need to install the wave.py and chunk.py  from
         https://github.com/joeky888/awesome-micropython-lib/tree/master/Audio
         
    SDCard.py  is available in  https://github.com/micropython/micropython/tree/master/drivers/sdcard
      please be sure to rename it SDCard.py into the pico lib folder


    ***  be sure to increase the SPI clock speed > 5MHz
    *** once SDCard is initialize set the spi to an higher clock


    How it works,

       1 - We set the PWM  to a range of 255, 1023 for 10 bits, at 122Khz
       2 - We read the wave file using the class wave which will set the sample rate and read the audio data by chunk
       3 - Mono files are converted to stereo by duplicating the original audio samples
       4 - Each chunk are converted to  16 bit signed to  unsigned char with the middle at 128
       5 - Wait for the DMA to be completed.  On first it will be anyway.
       6 - The converted chunk is then pass to the DMA to be transfer at the sample rate using one of build-in timer
       7 - Go on step 2 until is done.

    P.S. use rshell to transfer wave files to the Pico file system

    For Headphones

    
             2K
    PIO2   -/\/\/-----+-----    headphone left
                      |
                     === 0.1uF
                      |
    PIO4   -----------+-----    headphone ground
                      |
                     === 0.1uF
              2k      |
    PIO3   -/\/\/-----+-----    headphone right



    For amplifier don't use PIO4 and the capacitor should be 2200pF and connected to GND. 
    
       


'''
#
#---USES 
import os as uos
import time
from wav.wavePlayer import wavePlayer
import wav.wave as wave
from machine import Pin, PWM

def test_pulse():
    # Set up the GPIO pin for the speaker
    speaker_pin = Pin(16, Pin.OUT)

    # Set up PWM on the speaker pin
    speaker_pwm = PWM(speaker_pin)

    # Set the PWM frequency and duty cycle
    frequency = 420  # Frequency in Hz
    duty_cycle = 0.4  # Duty cycle between 0 and 1

    # Play the tone for a specified duration
    duration = 2  # Duration in seconds
    going_up = True

    try:
        for i in range(duration*100):
            
            step = int(frequency / 3)
            
            if going_up:
                frequency = frequency + step
            else:
                frequency = frequency - step
                
            if frequency > 3000:
                frequency = 3000
                going_up = False
            elif frequency < 100:
                frequency = 100
                going_up = True
                
            # Set the PWM frequency and duty cycle
            speaker_pwm.freq(frequency)
            speaker_pwm.duty_u16(int(duty_cycle * 65535))
            
                
            # Play the tone for the specified duration
            time.sleep(0.003)

    except KeyboardInterrupt:
        speaker_pwm.deinit()
        pass

    # Clean up
    speaker_pwm.deinit()

def test_wav():
    player = wavePlayer(leftPin=Pin(18, Pin.OUT))
    waveFolder = "/sound"
    wavelist = []

    for i in uos.listdir(waveFolder):
        if i.find(".wav") >= 0:
            wavelist.append(waveFolder + "/" + i)
        elif i.find(".WAV") >= 0:
            wavelist.append(waveFolder + "/" + i)

    print("{0:<45}".format('File Path'), ' Framerate| Width|  Ch.|Frames')
    for filename in wavelist:
        f = wave.open(filename, 'rb')
        # the format string "{0:<50}" says print left justified from chars 0 to 50 in a fixed with string
        print("{0:<50}".format(filename),
              "{0:>5}".format(f.getframerate()),
              "{0:>5}".format(f.getsampwidth()),
              "{0:>6}".format(f.getnchannels()),
              "{0:>6}".format(f.getnframes())
              )

    if not wavelist:
        print("Warning NO '.wav' files")
    else:
        print("Will play these '.wav' files", "/n", wavelist)
        try:
            for song in wavelist:
                print(f"Playing {song}")
                player.play(song)
        except KeyboardInterrupt:
            player.stop()
    print("wavePlayer terminated")


