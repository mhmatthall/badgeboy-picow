""" Pico-ePaper-2.9-B display driver
        by: Matt Hall
        version: 0.3

    Adapted from 'Pico_ePaper_Code' (https://github.com/waveshare/Pico_ePaper_Code)
        by: Waveshare team
        version: 1.0 (2021-03-16)
        license: MIT
"""
from machine import Pin, SPI
from utime import sleep

# Toggle print debugging
DEBUG = True

# Display resolution (must be portrait)
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 296

# Pinout
DC_PIN = 8      # Data/Command pin (0=cmd, 1=data)
CS_PIN = 9      # Chip Select pin
# pin 10 is the CLK
# pin 11 is the MOSI
RESET_PIN = 12  # Reset active when LOW
BUSY_PIN = 13   # Busy when LOW

"""
Driver class for the Waveshare 2.9" ePaper display for Pico (pico-e-paper-2.9-b)
"""
class DisplayDriver:
    def __init__(self):
        if DEBUG: print('* Initialising display module interface...')
        # Init pin layout
        self.__cs_pin = Pin(CS_PIN, Pin.OUT)
        self.__reset_pin = Pin(RESET_PIN, Pin.OUT)
        self.__busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)

        # Init SPI connection
        self.__spi = SPI(1, baudrate=4000000)
        self.__dc_pin = Pin(DC_PIN, Pin.OUT)

        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT

        if DEBUG: print('* Initialising display...')

        # Reset and send power on cmd
        self.__hw_reset()
        self.__send_command(0x04)
        self.__wait_for_display()

        # ------------------------------------------------------------
        # PANEL SETTING REGISTER (PSR)
        # Send panel setting cmd
        self.__send_command(0x00)

        # 0 - set resolution pt1
        # 0 - set resolution pt2
        # 0 - get lut from otp (DON'T SPECIFY)
        # 0 - black/white only mode DISABLE
        # 1 - gate scan direction UP
        # 1 - source shift direction RIGHT
        # 1 - booster ON
        # 1 - soft reset DOES NOTHING
        self.__send_data(0x0f)
        
        # mystery command
        self.__send_data(0x89)
        
        # ------------------------------------------------------------
        # RESOLUTION SETTING (TRES)
        # (OVERRIDES PSR RESOLUTION OPTIONS)
        self.__send_command(0x61)
        self.__send_data(0x80)
        self.__send_data(0x01)
        self.__send_data(0x28)

        # ------------------------------------------------------------
        # VCOM AND DATA INTERVAL REGISTER (CDI)
        # Send config
        self.__send_command(0x50)

        # 0 - VBD pt1
        # 1 - VBD pt2
        # 1 - DDX pt1
        # 1 - DDX pt2
        # 0 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        self.__send_data(0x77)

    def __delay_ms(self, delaytime):
        sleep(delaytime / 1000.0)

    def __hw_reset(self):
        self.__reset_pin.value(1)
        self.__delay_ms(50)

        self.__reset_pin.value(0)
        self.__delay_ms(2)

        self.__reset_pin.value(1)
        self.__delay_ms(50)

    def __send_command(self, command):
        # Command mode
        self.__dc_pin.value(0)

        # Slave chip select and send command, then return to master
        self.__cs_pin.value(0)
        self.__spi.write(bytearray([command]))
        self.__cs_pin.value(1)

    def __send_data(self, data):
        # Data mode
        self.__dc_pin.value(1)

        # Slave chip select and send command, then return to master
        self.__cs_pin.value(0)
        self.__spi.write(bytearray([data]))
        self.__cs_pin.value(1)

    def __wait_for_display(self):
        if DEBUG: print('    Rendering...')
        # Set upper bounds of 30 seconds for display to update; check every 1 second
        for i in range(30):
            # Rendering takes time so we monitor the BUSY pin that signals when
            # the microcontroller has finished the render (0=busy, 1=free)
            if self.__busy_pin.value() == 1: break
            self.__delay_ms(1000)

        if DEBUG: print('    Rendering complete.')

    def __refresh_display(self):
        # Send display refresh cmd (DRF)
        self.__send_command(0x12)
        self.__wait_for_display()

    def __fill_display(self, channel=0x10, val_to_write=0xff):
        # Start pixel data tx to SRAM (DTM1)
        self.__send_command(channel)

        for j in range(self.height):
            for i in range(int(self.width / 8)):
                if DEBUG: print(f'    clearing ({i}, {j})')
                self.__send_data(val_to_write)

        self.__refresh_display()

    def __power_off(self):
        # Send power off cmd
        self.__send_command(0x02)
        self.__wait_for_display()

        # Send deep sleep cmd; requires full reset to reenable
        self.__send_command(0x07)
        self.__send_data(0xA5)

    def debug_display_stripes(self, channel=0x10):
        if DEBUG: print("* DEBUG CMD: STRIPES")
        
        # Start pixel data tx to SRAM (DTM1)
        self.__send_command(channel)

        # For each line in the long side
        for j in range(self.height):
            # Send in (128 / 8 =) 16B chunks
            for i in range(int(self.width / 8)):
                if (j % 4) == 0:
                    if DEBUG: print(f'    setting {0x00} at ({i}, {j})')
                    self.__send_data(0x00)
                else:
                    if DEBUG: print(f'    setting {0xff} at ({i}, {j})')
                    self.__send_data(0xff)

        self.__refresh_display()

    def display(self, image, channel=0x10):
        """ Push an image to the display module and display it. Images are expected to be contiguous
        hex strings, where each pair of hex values represents 8 pixels to display.

        e.g., '0e' corresponds to the 8 pixel segment: '00001110'
        
        The image can be displayed in black (0x10) or red (0x13); black is default.
        """
        # Wipe SRAM for given colour channel
        self.__fill_display(channel)
        
        # Start pixel data tx to SRAM (DTM1)
        self.__send_command(channel)

        if DEBUG: print('* Starting render...')

        # Fetch every two chars in the image and interpret as hex number
        for i in range(0, len(image), 2):
            self.__send_data(
                int(image[i:i+2], 16)
            )

        # Refresh screen with new image in SRAM
        self.__refresh_display()
