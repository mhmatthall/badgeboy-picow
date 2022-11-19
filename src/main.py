""" badgeboy digital name badge logic for the Raspberry Pi Pico W

    Software for the Pico W used in the badgeman digital name badge system. This should run when the
    Pico receives power but only after executing any './boot.py' file first.

    This requires that the MicroPython binaries are loaded onto the Pico already.

        by: Matt Hall
        version: 0.1

"""
from machine import Pin, Timer
import network
import time
import rp2
import ujson
import ubinascii
import urequests as req

# Import whatever driver file is present
try:
    from display_driver_BWR import DisplayDriver
except:
    from display_driver_BW import DisplayDriver

# Toggle print debugging
DEBUG = False

# Network info
WLAN_SSID = 'Badge City'
WLAN_PW = 'ihatecomputers'
WLAN_SUBNET = '192.168.69'
WLAN_SERVER_IP = '1'
WLAN_SERVER_PORT = '3001'
WLAN_SERVER_URL = WLAN_SUBNET + '.' + WLAN_SERVER_IP + ':' + WLAN_SERVER_PORT

REQUEST_HEADER = { "Content-Type": "application/json" }

DISPLAY_DATA_CACHE = {}

EVENT_LOOP_SLEEP_TIME = 20

# Control onboard LED as a status indicator
led = Pin('LED', Pin.OUT)
led_timer = Timer()

def blink_led(_timer):
    global led
    led.toggle()

def connect_to_wifi():
    if DEBUG: print('* Connecting to WLAN...')

    # Try to establish connection
    wlan.connect(WLAN_SSID, WLAN_PW)

    # We don't want to ever stop trying to connect for resiliency
    while wlan.status() != 3:
        if DEBUG: print('  ...' + str(wlan.status()))
        time.sleep(1)

    # Log local IP address
    if DEBUG: print(f'    Connected to \'{WLAN_SSID}\' with address {wlan.ifconfig()[0]}')


# Begin initialisation
if DEBUG: print('*** badgeboy for the Raspberry Pi Pico W ***')

# Blink LED at medium rate in init stage
led_timer.init(freq=0.5, mode=Timer.PERIODIC, callback=blink_led)

# Set device country to GB so that the wireless radio
# uses UK-approved network channels
rp2.country('GB')

# Connect to WLAN as a client rather than a host
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Disable wireless radio power saving, if needed
# wlan.config(pm=0xa11140)

# Get our MAC address
MAC = ubinascii.hexlify(
    network.WLAN().config('mac')
).decode().upper()

# Log MAC
if DEBUG: print(f"* This device's MAC address is {MAC}")

# Connect to network (WARNING: will infinite loop until connected)
connect_to_wifi()

# Create and init display unit
badge = DisplayDriver()

# Main event loop
while True:
    try:
        if DEBUG: print('* Polling API...')

        # Poll DB for changes
        poll_request = req.get(
            f'http://{WLAN_SERVER_URL}/api/badges/by-mac/{MAC}',
            headers=REQUEST_HEADER
        )

        # If found in DB
        if poll_request.status_code == 200:
            if DEBUG: print('    Badge exists in DB')
            badge_data = poll_request.json()

            # Only change things when the server data has changed
            if badge_data != DISPLAY_DATA_CACHE:
                if DEBUG: print('    Display data cache out of date. Refreshing...')
                
                # Blink LED at medium rate when refreshing
                led_timer.init(freq=5, mode=Timer.PERIODIC, callback=blink_led)

                # Update data cache
                BADGE_DATA_CACHE = badge_data

                # Display badge info
                badge.display(badge_data['userData']['image'])

        # If not found in DB
        elif poll_request.status_code == 404:
            if DEBUG: print('    Badge not found!\n      Inserting blank DB record...')
            
            # Blink LED at medium rate when not found
            led_timer.init(freq=5, mode=Timer.PERIODIC, callback=blink_led)

            # Insert blank DB record
            create_badge_request = req.post(
                f'http://{WLAN_SERVER_URL}/api/badges',
                headers=REQUEST_HEADER,
                data=ujson.dumps(
                    { "macAddress":MAC }
                )
            )

            # If successful
            if create_badge_request.status_code == 201:
                if DEBUG: print(f'      Successfully created new DB record.')
                if DEBUG: print(f'      Retrieving image from server...')

                # Get image from server
                img_request = req.get(
                    f'http://{WLAN_SERVER_URL}/api/badges/by-mac/{MAC}',
                    headers=REQUEST_HEADER
                )

                if img_request.status_code == 200:
                    if DEBUG: print('      Pushing image to display module...')

                    # Update data cache
                    BADGE_DATA_CACHE = img_request.json()

                    # Display instructions
                    badge.display(img_request.json()['userData']['image'])
                else:
                    if DEBUG: print(f'      ERROR: Could not get badge image from server. API returned status {img_request.status_code}')

                img_request.close()
            else:
                if DEBUG: print(f'      ERROR: Could not create new badge record in DB. API returned status {create_badge_request.status_code}')
            
            # Finally, close socket
            create_badge_request.close()

        else:
            if DEBUG: print(f'    ERROR: DB poll failed. API returned status {poll_request.status_code}')
            
        # Clean up connection
        poll_request.close()
    
    except Exception as err:
        if DEBUG: print(f'    ERROR: Could not complete network request:\n    {err}')
        
        # Blink LED quickly when errored
        led_timer.init(freq=10, mode=Timer.PERIODIC, callback=blink_led)

        #  Check if network was to blame
        if wlan.status() < 0 or wlan.status() > 3:
            if DEBUG: print('      REASON: Network connection was lost. Attempting reconnect...')
            wlan.disconnect()
            connect_to_wifi()   # WARNING: will continue forever until reconnected

    if DEBUG: print(f'* Event loop complete. Sleeping for {EVENT_LOOP_SLEEP_TIME} seconds...')
    
    # Blink LED slowly in main event loop
    led_timer.init(freq=0.3, mode=Timer.PERIODIC, callback=blink_led)
    
    time.sleep(EVENT_LOOP_SLEEP_TIME)
