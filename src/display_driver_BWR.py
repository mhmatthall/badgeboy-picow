""" Pico-ePaper-2.9-B display driver
    by Matt Hall

    Adapted from 'Pico_ePaper_Code' (https://github.com/waveshare/Pico_ePaper_Code)
        by: Waveshare team
        version: 1.0 (2021-03-16)
        license: MIT
"""
from machine import Pin, SPI
import framebuf
import utime

# Display resolution (must be portrait)
DISPLAY_WIDTH = 128
DISPLAY_HEIGHT = 296

# Pinout
DC_PIN = 8      # Data/Command pin
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
        print('* Initialising display module interface...')
        self.__reset_pin = Pin(RESET_PIN, Pin.OUT)
        self.__busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.__cs_pin = Pin(CS_PIN, Pin.OUT)

        self.width = DISPLAY_WIDTH
        self.height = DISPLAY_HEIGHT

        self.__spi = SPI(1, baudrate=4000000)
        self.__dc_pin = Pin(DC_PIN, Pin.OUT)

        # Create a buffer to store the display data
        self.__buf = bytearray(self.height * self.width // 8)

        self.__image_buffer = framebuf.FrameBuffer(
            self.__buf, self.width, self.height, framebuf.MONO_HLSB
        )

        print('* Initialising display...')

        # Hardware reset
        self.__hw_reset()
        self.__wait_for_display()

        # Send power on cmd
        self.__send_command(0x04)
        self.__wait_for_display()

        # PANEL SETTING REGISTER (PSR) ---
        # Send panel setting cmd
        self.__send_command(0x00)

        # 1 - set resolution pt1
        # 0 - set resolution pt2
        # 0 - get lut from otp (DON'T SPECIFY)
        # 1 - black/white only mode ENABLE
        # 1 - gate scan direction UP
        # 1 - source shift direction RIGHT
        # 1 - booster ON
        # 1 - soft reset DOES NOTHING
        self.__send_data(0x9f)

        # VCOM AND DATA INTERVAL REGISTER ---
        # Send CDI command
        self.__send_command(0x50)

        # 0 - VBD pt1
        # 0 - VBD pt2
        # 1 - DDX pt1
        # 0 - DDX pt2
        # 0 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        self.__send_data(0x27)

    def __digital_write(self, pin, value):
        pin.value(value)

    def __digital_read(self, pin):
        return pin.value()

    def __delay_ms(self, delaytime):
        utime.sleep(delaytime / 1000.0)

    def __spi_writebyte(self, data):
        self.__spi.write(bytearray(data))

    def __spi_read(self, num_bytes):
        return bytearray(self.__spi.read(num_bytes))

    def __module_exit(self):
        self.__digital_write(self.__reset_pin, 0)

    def __hw_reset(self):
        self.__digital_write(self.__reset_pin, 1)
        self.__delay_ms(50)
        self.__digital_write(self.__reset_pin, 0)
        self.__delay_ms(2)
        self.__digital_write(self.__reset_pin, 1)
        self.__delay_ms(50)

    def __send_command(self, command):
        self.__digital_write(self.__dc_pin, 0)
        self.__digital_write(self.__cs_pin, 0)
        self.__spi_writebyte([command])
        self.__digital_write(self.__cs_pin, 1)

    def __send_data(self, data):
        self.__digital_write(self.__dc_pin, 1)
        self.__digital_write(self.__cs_pin, 0)
        self.__spi_writebyte([data])
        self.__digital_write(self.__cs_pin, 1)

    def __receive_data(self, num_bytes):
        self.__digital_write(self.__dc_pin, 1)
        self.__digital_write(self.__cs_pin, 0)
        rx = self.__spi_read(num_bytes)
        self.__digital_write(self.__cs_pin, 1)
        return rx

    def __wait_for_display(self):
        print('    Rendering...')

        # Poll status until complete
        while(self.__digital_read(self.__busy_pin) == 0):
            self.__delay_ms(100)

        print('    Rendering complete.')

    def __refresh_display(self):
        # Send DRF cmd
        self.__send_command(0x12)
        self.__wait_for_display()

    def __display_buffer_img(self):
        # Start tx 2 to SRAM (DTM2)
        self.__send_command(0x13)

        # For each row (0-295)
        for j in range(self.height):
            # For each col / 8 (0-15)
            for i in range(int(self.width / 8)):
                # Send byte to display, where each bit represents a pixel
                self.__send_data(self.__buf[i + j * int(self.width / 8)])

        self.__refresh_display()

    def __debug_display_lines(self):
        # Start tx 2 to SRAM (DTM2)
        self.__send_command(0x13)

        # For each line in the long side
        for j in range(self.height):
            # Send in (128 / 8 =) 16B chunks
            for i in range(int(self.width / 8)):
                if (j % 4) == 0:
                    print(f'    setting {0x00} at ({i}, {j})')
                    self.__send_data(0x00)
                else:
                    print(f'    setting {0xff} at ({i}, {j})')
                    self.__send_data(0xff)

        self.__refresh_display()

    def __clear_display(self, val_to_write=0xff):
        # Start tx 2 to SRAM (DTM2)
        self.__send_command(0x13)

        for j in range(self.height):
            for i in range(int(self.width / 8)):
                print(f'    clearing ({i}, {j})')
                self.__send_data(val_to_write)

        self.__refresh_display()

    def __power_off(self):
        # Send power off cmd
        self.__send_command(0x02)
        self.__wait_for_display()

        # Send deep sleep cmd; requires full reset to reenable
        self.__send_command(0x07)
        self.__send_data(0xA5)

    def display(self, image):
        """ Push an image to the display module and display it. Images are expected to be contiguous
        hex strings, where each pair of hex values represents 8 pixels to display.

        e.g., '0e' corresponds to the 8 pixel segment: '00001110'
        """
        # Start tx 2 to SRAM (DTM2)
        self.__send_command(0x13)

        print('* Starting render...')

        # Fetch every two chars in the image and interpret as hex number
        for i in range(0, len(image), 2):
            self.__send_data(
                int(image[i:i+2], 16)
            )

        # Refresh screen with new image in SRAM
        self.__refresh_display()
