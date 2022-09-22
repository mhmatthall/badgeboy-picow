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
        print('  Initialising interfaces...')
        self.reset_pin = Pin(RST_PIN, Pin.OUT)
        self.busy_pin = Pin(BUSY_PIN, Pin.IN, Pin.PULL_UP)
        self.cs_pin = Pin(CS_PIN, Pin.OUT)
        
        self.width = EPD_WIDTH
        self.height = EPD_HEIGHT

        self.spi = SPI(1, baudrate=4000000)
        self.dc_pin = Pin(DC_PIN, Pin.OUT)

        # Create a buffer to store the display data
        self.buf = bytearray(self.height * self.width // 8)

        self.image_buffer = framebuf.FrameBuffer(
            self.buf, self.width, self.height, framebuf.MONO_HLSB
        )

        print('  Initialising display...')

        # Hardware reset
        self.hw_reset()
        self.wait_for_display()

        # Send power on cmd
        self.send_command(0x04)
        self.wait_for_display()

        # PANEL SETTING REGISTER (PSR) ---
        # Send panel setting cmd
        self.send_command(0x00)

        # 1 - set resolution pt1
        # 0 - set resolution pt2
        # 0 - get lut from otp (DON'T SPECIFY)
        # 1 - black/white only mode ENABLE
        # 1 - gate scan direction UP
        # 1 - source shift direction RIGHT
        # 1 - booster ON
        # 1 - soft reset DOES NOTHING
        self.send_data(0x9f)

        # VCOM AND DATA INTERVAL REGISTER ---
        # Send CDI command
        self.send_command(0x50)

        # 0 - VBD pt1
        # 0 - VBD pt2
        # 1 - DDX pt1
        # 0 - DDX pt2
        # 0 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        # 1 - default data interval of 10 frames (base-10)
        self.send_data(0x27)

        # TRY to get board revision info to ID type of display module (no workie)
        # self.send_command(0x70)
        # rev_rx = self.receive_data(2)
        # print(f'  Revision: {rev_rx}')


    def digital_write(self, pin, value):
        pin.value(value)


    def digital_read(self, pin):
        return pin.value()


    def delay_ms(self, delaytime):
        utime.sleep(delaytime / 1000.0)


    def spi_writebyte(self, data):
        self.spi.write(bytearray(data))


    def spi_read(self, num_bytes):
        return bytearray(self.spi.read(num_bytes))


    def module_exit(self):
        self.digital_write(self.reset_pin, 0)


    # Hardware reset
    def hw_reset(self):
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


    def receive_data(self, num_bytes):
        self.digital_write(self.dc_pin, 1)
        self.digital_write(self.cs_pin, 0)
        rx = self.spi_read(num_bytes)
        self.digital_write(self.cs_pin, 1)
        return rx


    def wait_for_display(self):
        print('  Display is busy...')
        
        # Poll status until complete
        while(self.digital_read(self.busy_pin) == 0):
            self.delay_ms(100)

        print('    ...done!')


    def refresh_display(self):
        # Send DRF cmd
        self.send_command(0x12)
        self.wait_for_display()


    def display(self):
        # Start tx 2 to SRAM (DTM2)
        self.send_command(0x13)

        for j in range(self.height):
            for i in range(int(self.width / 8)):
                print(f'    setting {self.buf[i + j * int(self.width / 8)]} at ({i}, {j})')
                self.send_data(self.buf[i + j * int(self.width / 8)])

        self.refresh_display()
    

    def debug_display_lines(self):
        # Start tx 2 to SRAM (DTM2)
        self.send_command(0x13)

        # For each line in the long side
        for j in range(self.height):
            # Send in (128 / 8 =) 16B chunks
            for i in range(int(self.width / 8)):
                if (j % 4) == 0:
                    print(f'    setting {0x00} at ({i}, {j})')
                    self.send_data(0x00)
                else:
                    print(f'    setting {0xff} at ({i}, {j})')
                    self.send_data(0xff)

        self.refresh_display()


    def clear_display(self, val_to_write=0xff):
        # Start tx 2 to SRAM (DTM2)
        self.send_command(0x13)

        for j in range(self.height):
            for i in range(int(self.width / 8)):
                print(f'    clearing ({i}, {j})')
                self.send_data(val_to_write)

        self.refresh_display()


    def power_off(self):
        # Send power off cmd
        self.send_command(0x02)
        self.wait_for_display()

        # Send deep sleep cmd; requires full reset to reenable
        self.send_command(0x07)
        self.send_data(0xA5)


# DEBUG CODE
# DEBUG CODE
# DEBUG CODE
# if __name__ == '__main__':
#     # Instantiate display
#     print("DEBUG: instantiate")
#     d = WS_29_B()

#     d.delay_ms(2000)

#     print("DEBUG: clear display")
#     d.clear_display()

#     d.delay_ms(2000)

#     # print("DEBUG: fill buffer with all white")
#     # d.image_buffer.fill(0xff)

#     # d.delay_ms(2000)

#     print("DEBUG: display debug pattern")
#     d.debug_display_lines()
    
#     d.delay_ms(2000)

#     # print("DEBUG: push line 1 to buffer")
#     # d.image_buffer.text("Festival of Ideas", 0, 10, 0x00)
#     # print("DEBUG: push line 2 to buffer")
#     # d.image_buffer.text("badgeboy", 0, 40, 0x00)
#     # print("DEBUG: display buffer contents")
#     # d.display()

#     print("Display is powering off...")
#     d.power_off()
