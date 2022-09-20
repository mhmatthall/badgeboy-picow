"""badgeboy digital name badge logic for the Raspberry Pi Pico W

Software for the Pico W used in the digital name badge project for the Festival of Ideas
2022. This should run when the Pico receives power but only after executing any './boot.py' file
first.

This requires the MicroPython binaries to be loaded onto the Pico already.

by Matt Hall

"""
import network
import time
import rp2
import ubinascii
import urequests as req

WLAN_SSID = 'Badge City'
WLAN_PW = 'ilovecomputers'
WLAN_SUBNET = '192.168.0'
WLAN_SERVER_IP = '2'
WLAN_SERVER_URL = WLAN_SUBNET + WLAN_SERVER_IP

REQUEST_HEADER = '{ "Content-Type": "application/json" }'

BADGE_DATA_CACHE = ''

# Display a boot screen to indicate device powered on
display_boot_screen()

# Set device country to GB so that the wireless radio
# uses UK-approved network channels
rp2.country('GB')

# Connect to WLAN as a client rather than a host
wlan = network.WLAN(network.STA_IF)
wlan.active(True)

# Disable wireless radio power saving, if needed
# wlan.config(pm=0xa11140)

# Get our MAC address
MAC = upper(ubinascii.hexlify(
        network.WLAN().config('mac')).decode()
        )

# Log MAC
print(f"This device's MAC: {MAC}")

# Connect to network (WARNING: will infinite loop until connected)
connect_to_wifi()

# Main event loop
while True:
    try:
        print('Polling API...')

        # Poll DB for changes every X seconds
        poll_request = req.get(
            f'{WLAN_SERVER_URL}/api/badges/{MAC}',
            headers=REQUEST_HEADER
        )

        # If found in DB
        if poll_request.status_code == 200:
            print('Found badge!')
            badge_data = poll_request.json()

            # Only change things when the server data has changed
            if badge_data != BADGE_DATA_CACHE:
                print('Badge data cache out of date. Refreshing...')

                # Update data cache
                BADGE_DATA_CACHE = badge_data

                # Display badge info
                # TODO

        # If not found in DB
        elif poll_request.status_code == 404:
            print('Badge not found!\nInserting blank DB record...')

            # Insert blank DB record
            create_badge_request = req.post(
                f'{WLAN_SERVER_URL}/api/badges/{MAC}',
                headers=REQUEST_HEADER,
                data='{ "macAddress":"' + MAC + '", "name":"", "pronouns":"", "affiliation":"", "message":"", "image":"" }'
            )

            # If successful
            if create_badge_request.status_code == 201:
                print(f'Successfully created new DB record for badge {MAC}')

                # Display instructions
                # TODO

            else:
                print(f'ERROR: Could not create new badge record in DB. API returned status {create_badge_request.status_code}')
            
            # Finally, close socket
            create_badge_request.close()

        else:
            print(f'ERROR: DB poll failed. API returned status {poll_request.status_code}')
    
    except err:
        print(f'ERROR: Could not complete network request:\n{err}')

        #  Check if network was to blame
        if wlan.status() < 0 or wlan.status() > 3:
            print('REASON: Network connection was lost. Attempting reconnect...')
            wlan.disconnect()
            connect_to_wifi()   # WARNING: will continue forever until reconnected
    
    finally:
        poll_request.close()

    print('Event loop complete. Sleeping...')
    time.sleep(20)


def connect_to_wifi():
    print('Connecting to WLAN...')

    # Try to establish connection
    wlan.connect(WLAN_SSID, WLAN_PW)

    # We don't want to ever stop trying to connect for resiliency
    while not wlan.connected() and wlan.status() == 0:
        print('  ...')
        time.sleep(1)

    # Log local IP address
    print(f'  Connected with IP {wlan.ifconfig()[0]}')


def display_boot_screen():
    print('Hello world!\nClearing the display...')

    # Clear the display and show a loading thing
    # TODO
