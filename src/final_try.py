#!/usr/bin/env python3
import asyncio
import argparse
import sys
from pychonet.lib.udpserver import UDPServer
from pychonet import ECHONETAPIClient as api
from pychonet.EchonetInstance import EchonetInstance
from pychonet.StorageBattery import StorageBattery
from pychonet.HomeSolarPower import HomeSolarPower


async def simple_try(host):
    """Simple test with minimal code"""
    print(f"Testing connection to {host}...")
    
    # Initialize UDP server and API client
    udp = UDPServer()
    loop = asyncio.get_event_loop()
    udp.run("0.0.0.0", 3610, loop=loop)
    server = api(server=udp)
    
    # Just try to discover the device
    print("Sending discovery packet...")
    await server.discover(host)
    
    # Wait a bit
    print("Waiting for response...")
    await asyncio.sleep(3)
    
    # Check if the device was discovered
    if hasattr(server, '_state') and host in server._state:
        print(f"Host found in server state: {server._state[host]}")
        
        # Directly create instance objects and try to get some data
        print("\nTrying direct instance access...")
        
        # Try different device types
        device_types = [
            (StorageBattery, "Storage Battery"),
            (HomeSolarPower, "Home Solar Power"),
            (EchonetInstance, "Generic Instance", 0x02, 0x88)  # Smart Meter
        ]
        
        for device_class in device_types:
            if len(device_class) == 2:
                cls, name = device_class
                try:
                    print(f"\nTrying {name}...")
                    device = cls(host, server)
                    
                    # Try to get basic information
                    try:
                        status = await device.getOperationalStatus()
                        print(f"Operational status: {status}")
                    except Exception as e:
                        print(f"Error getting operational status: {e}")
                        
                    # Try simple power methods
                    try:
                        if hasattr(device, 'getInstantaneousPower'):
                            power = await device.getInstantaneousPower()
                            print(f"Instantaneous power: {power}")
                    except Exception as e:
                        print(f"Error getting instantaneous power: {e}")
                        
                except Exception as e:
                    print(f"Error creating {name} instance: {e}")
            else:
                cls, name, eojgc, eojcc = device_class
                try:
                    print(f"\nTrying {name}...")
                    device = cls(host, eojgc, eojcc, 0x01, server)
                    
                    # Try to get basic information
                    try:
                        status = await device.getOperationalStatus()
                        print(f"Operational status: {status}")
                    except Exception as e:
                        print(f"Error getting operational status: {e}")
                except Exception as e:
                    print(f"Error creating {name} instance: {e}")
    else:
        print(f"Host {host} not found in server state")
        if hasattr(server, '_state'):
            print(f"Available hosts: {list(server._state.keys())}")
    
    return True


async def main():
    parser = argparse.ArgumentParser(description='Simple test for Echonet device')
    parser.add_argument('host', help='IP address of the Echonet device')
    args = parser.parse_args()
    
    result = await simple_try(args.host)
    return 0 if result else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)