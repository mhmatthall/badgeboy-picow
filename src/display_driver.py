"""Pico-ePaper-2.9-B display driver

    Adapted from 'Pico_ePaper_Code' (https://github.com/waveshare/Pico_ePaper_Code)
        by: Waveshare team 
        version: 1.0 (2021-03-16)
        license: MIT
"""
from machine import Pin, SPI
import framebuf
import utime

# Display resolution
EPD_WIDTH = 128
EPD_HEIGHT = 296 # flash ur dad

DC_PIN = 8
CS_PIN = 9
# pin 10 is the CLK
# pin 11 is the MOSI
RST_PIN = 12
BUSY_PIN = 13

"""Driver class for the Waveshare 2.9" ePaper display for Pico (pico-e-paper-2.9-b)
"""
class WS_29_B:
    def __init__(self):
        print('Initialising interfaces...')
        self.reset_pin = Pin(RST_PIN, Pin.OUT)

        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

        self.spi = SPI(1)
        self.spi.init(baudrate=4000_000)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)

        self.buffer_black = bytearray(self.height * self.width // 8)
        self.buffer_red = bytearray(self.height * self.width // 8)
        self.image_buffer_black = framebuf.FrameBuffer(
            self.buffer_black, self.width, self.height, framebuf.MONO_HLSB
        )
        self.image_buffer_red = framebuf.FrameBuffer(
            self.buffer_red, self.width, self.height, framebuf.MONO_HLSB
        )

        print('Initialising display...')
        self.reset()

        # Send power on cmd
        self.send_command(0x04)
        self.wait_for_display_update()

        # PANEL SETTING REGISTER ---
        # Send panel setting cmd
        self.send_command(0x00)

        # Get LUT from OTP, 128x296
        self.send_data(0x0f)

        # Temperature sensor, boost and other related timing settings
        self.send_data(0x89)

        # RESOLUTION SETTING ---
        self.send_command(0x61)
        self.send_data(0x80)
        self.send_data(0x01)
        self.send_data(0x28)

        # VCOM AND DATA INTERVAL SETTING
        self.send_command(0x50)
        # WBmode:VBDF 17|D7 VBDW 97 VBDB 57
        # WBRmode:VBDF F7 VBDW 77 VBDB 37  VBDR B7
        self.send_data(0x77)

    def digital_write(self, pin, value):
        pin.value(value)

    def digital_read(self, pin):
        return pin.value()

    def delay_ms(self, delaytime):
        utime.sleep(delaytime / 1000.0)

    def spi_writebyte(self, data):
        self.spi.write(bytearray(data))

    def module_exit(self):
        self.digital_write(self.reset_pin, 0)

    # Hardware reset
    def reset(self):
        self.digital_write(self.reset_pin, 1)
        self.delay_ms(50)
        self.digital_write(self.reset_pin, 0)
        self.delay_ms(2)
        self.digital_write(self.reset_pin, 1)
        self.delay_ms(50)

    def send_command(self, command):
        self.digital_write(self.dc_pin, 0)
        self.digital_write(self.cs_pin, 0)
        self.spi_writebyte([command])
        self.digital_write(self.cs_pin, 1)

    def send_data(self, data):
        self.digital_write(self.dc_pin, 1)
        self.digital_write(self.cs_pin, 0)
        self.spi_writebyte([data])
        self.digital_write(self.cs_pin, 1)

    def wait_for_display_update(self):
        print('Updating display...')

        # Send get status cmd
        self.send_command(0x71)

        while(self.digital_read(self.busy_pin) == 0):
            # Poll status
            self.send_command(0x71)
            self.delay_ms(10)

        print('  ...done!')

    def refresh_display(self):
        self.send_command(0x12)
        self.wait_for_display_update()

    def display(self):
        # Start tx 1 to SRAM
        self.send_command(0x10)

        for j in range(0, self.height):
            for i in range(0, int(self.width / 8)):
                self.send_data(self.buffer_black[i + j * int(self.width / 8)])

        # Start tx 2 to SRAM
        self.send_command(0x13)

        for j in range(0, self.height):
            for i in range(0, int(self.width / 8)):
                self.send_data(self.buffer_red[i + j * int(self.width / 8)])

        self.refresh_display()

    def clear_sram(self, black_col_value, red_col_value):
        # Start tx 1 to SRAM
        self.send_command(0x10)

        for j in range(0, self.height):
            for i in range(0, int(self.width / 8)):
                self.send_data(black_col_value)

        # Start tx 2 to SRAM
        self.send_command(0x13)

        for j in range(0, self.height):
            for i in range(0, int(self.width / 8)):
                self.send_data(red_col_value)

        self.refresh_display()

    def power_off(self):
        # Send power off cmd
        self.send_command(0x02)
        self.wait_for_display_update()

        # Send deep sleep cmd; requires full reset to reenable
        self.send_command(0x07)
        self.send_data(0xA5)

        self.delay_ms(2000)
        self.module_exit()


# DEBUG CODE
# DEBUG CODE
# DEBUG CODE
if __name__ == '__main__':
    # Instantiate display
    d = WS_29_B()

    # Init LCD layers
    d.clear_sram(0xff, 0xff)
    d.image_buffer_black.fill(0xff)
    d.image_buffer_red.fill(0xff)

    d.image_buffer_black.text("Festival of Ideas", 0, 10, 0x00)
    # d.image_buffer_red.text("ePaper-2.9-B", 0, 25, 0x00)
    d.image_buffer_black.text("badgeboy", 0, 40, 0x00)
    # d.image_buffer_red.text("Hello World", 0, 55, 0x00)
    d.display()

    # d.delay_ms(2000)
    # d.image_buffer_red.vline(10, 90, 40, 0x00)
    # d.image_buffer_red.vline(90, 90, 40, 0x00)
    # d.image_buffer_black.hline(10, 90, 80, 0x00)
    # d.image_buffer_black.hline(10, 130, 80, 0x00)
    # d.image_buffer_red.line(10, 90, 90, 130, 0x00)
    # d.image_buffer_black.line(90, 90, 10, 130, 0x00)
    # d.display()
    # d.delay_ms(2000)
    # d.image_buffer_black.rect(10, 150, 40, 40, 0x00)
    # d.image_buffer_red.fill_rect(60, 150, 40, 40, 0x00)
    # d.display()
    # d.delay_ms(2000)
    # d.clear_sram(0xff, 0xff)
    # d.delay_ms(2000)

    print("Display is powering off...")
    d.power_off()

    # Init LCD layers
    d.clear_sram(0xff, 0xff)
    d.image_buffer_black.fill(0xff)
    d.image_buffer_red.fill(0xff)

    d.image_buffer_black.text("Updated screen", 0, 10, 0x00)
    # d.image_buffer_red.text("ePaper-2.9-B", 0, 25, 0x00)
    d.image_buffer_black.text("badgeboy", 0, 40, 0x00)
    # d.image_buffer_red.text("Hello World", 0, 55, 0x00)
    d.display()
