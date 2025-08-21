#!/usr/bin/env python3
import asyncio
import argparse
import sys
from pychonet.lib.udpserver import UDPServer
from pychonet import ECHONETAPIClient as api
from pychonet.EchonetInstance import EchonetInstance


async def discover_and_test(host):
    """Test direct EPC commands to discover power information."""
    print(f"Connecting to Echonet device at {host}...")
    
    # Initialize UDP server and API client
    udp = UDPServer()
    loop = asyncio.get_event_loop()
    udp.run("0.0.0.0", 3610, loop=loop)
    server = api(server=udp)
    
    # Set debug mode if available
    if hasattr(server, 'set_debug'):
        server.set_debug(True)
    
    # Try to discover the device
    print("Discovering device...")
    result = await server.discover(host)
    print(f"Discovery result: {result}")
    
    # Wait a bit for discovery to complete
    await asyncio.sleep(2)
    
    # Try additional discovery methods
    print("\n=== Trying Additional Discovery Methods ===")
    
    # Try to get device information
    try:
        print("Trying to get device info...")
        if hasattr(server, 'getDeviceInfo'):
            info = await server.getDeviceInfo(host)
            print(f"Device info: {info}")
        else:
            print("getDeviceInfo method not available")
    except Exception as e:
        print(f"Error getting device info: {e}")
    
    # Try to get instances
    try:
        print("\nTrying to get instances...")
        if hasattr(server, 'getInstances'):
            instances = await server.getInstances(host)
            print(f"Instances: {instances}")
        else:
            print("getInstances method not available")
    except Exception as e:
        print(f"Error getting instances: {e}")
        
    # Try to broadcast for discovery
    try:
        print("\nTrying broadcast discovery...")
        if hasattr(server, 'broadcastDiscovery'):
            result = await server.broadcastDiscovery()
            print(f"Broadcast discovery result: {result}")
        else:
            print("broadcastDiscovery method not available")
    except Exception as e:
        print(f"Error with broadcast discovery: {e}")
    
    # Examine the server state
    print("\n=== Server State Information ===")
    
    # Check if server has _state attribute
    if hasattr(server, '_state'):
        print("server._state exists")
        if host in server._state:
            print(f"Host {host} found in server._state")
            print(f"Contents for {host}: {server._state[host]}")
            
            # If device is available but has no instances, try to populate them
            if server._state[host].get('available', False) and not server._state[host].get('instances'):
                print("\n=== Trying to populate instances manually ===")
                
                # Common instance types for power-related devices
                instances_to_try = [
                    (0x02, 0x7D, 0x01),  # Storage Battery
                    (0x02, 0x79, 0x01),  # Home Solar Power
                    (0x02, 0x88, 0x01),  # Smart Electric Energy Meter
                ]
                
                # Manually add instances to state
                if 'instances' not in server._state[host]:
                    server._state[host]['instances'] = {}
                
                for eojgc, eojcc, instance in instances_to_try:
                    if eojgc not in server._state[host]['instances']:
                        server._state[host]['instances'][eojgc] = {}
                    
                    if eojcc not in server._state[host]['instances'][eojgc]:
                        server._state[host]['instances'][eojgc][eojcc] = {}
                    
                    if instance not in server._state[host]['instances'][eojgc][eojcc]:
                        server._state[host]['instances'][eojgc][eojcc][instance] = {}
                        print(f"Added instance: {eojgc:02X}:{eojcc:02X}:{instance:02X}")
                
                print(f"Updated instances: {server._state[host]['instances']}")
                
                # Try to get property maps
                for eojgc, eojcc, instance in instances_to_try:
                    try:
                        print(f"Getting property maps for {eojgc:02X}:{eojcc:02X}:{instance:02X}...")
                        await server.getAllPropertyMaps(host, eojgc, eojcc, instance)
                    except Exception as e:
                        print(f"Error getting property maps: {e}")
        else:
            print(f"Host {host} not found in server._state")
            print(f"Available hosts in _state: {list(server._state.keys())}")
    else:
        print("server._state doesn't exist")
        
    # Check other possible state attributes
    for attr in ['state', 'devices', 'discovered_devices']:
        if hasattr(server, attr):
            attr_val = getattr(server, attr)
            print(f"server.{attr} exists: {attr_val}")
            
    # Try to dump all interesting attributes
    print("\nAll server attributes:")
    for attr in dir(server):
        if not attr.startswith('_') and attr not in ['discover', 'server']:
            try:
                val = getattr(server, attr)
                if not callable(val):
                    print(f"server.{attr}: {val}")
            except:
                pass
    
    # Common Echonet Lite EOJ classes to try
    device_types = [
        (0x02, 0x7D, 0x01, "Storage Battery"),
        (0x02, 0x79, 0x01, "Home Solar Power"),
        (0x02, 0x88, 0x01, "Low Voltage Smart Meter"),
        (0x05, 0xFF, 0x01, "Controller"),
        (0x00, 0x11, 0x01, "Temperature Sensor")
    ]
    
    successful_readings = []
    
    # Try different device types with direct EchonetInstance
    for eojgc, eojcc, instance, name in device_types:
        try:
            print(f"\n=== Testing {name} (Group: 0x{eojgc:02X}, Class: 0x{eojcc:02X}, Instance: 0x{instance:02X}) ===")
            
            # Create generic instance
            device = EchonetInstance(host, eojgc, eojcc, instance, server)
            
            # Try to get operational status (should work for most devices)
            try:
                status = await device.getOperationalStatus()
                print(f"Operational status: {status}")
                if status is not False and status is not None:
                    print(f"✅ Found valid device: {name}")
                    successful_readings.append((name, "Operational Status", status))
            except Exception as e:
                print(f"Error getting operational status: {e}")
            
            # Common power-related EPCs to try
            power_epcs = [
                (0x80, "Operation status"),
                (0x84, "Instantaneous power consumption"),
                (0x85, "Cumulative power consumption"),
                (0xD3, "Instantaneous charging/discharging power"),
                (0xD4, "Instantaneous charging/discharging current"),
                (0xE0, "Instantaneous power generation"),
                (0xE1, "Cumulative power generation"),
                (0xE7, "Instantaneous electric energy"),
                (0xE8, "Cumulative electric energy"),
                (0xEA, "Measured electric power"),
                (0xEB, "Cumulative electric energy measurement value")
            ]
            
            print(f"Trying direct EPC commands on {name}...")
            for epc, desc in power_epcs:
                try:
                    result = await device.getMessage(epc)
                    print(f"EPC 0x{epc:02X} ({desc}): {result}")
                    if result is not False and result is not None:
                        successful_readings.append((name, desc, result))
                except Exception as e:
                    print(f"Error getting EPC 0x{epc:02X} ({desc}): {e}")
        
        except Exception as e:
            print(f"Error with {name}: {e}")
    
    # Summary of successful readings
    if successful_readings:
        print("\n===== SUCCESSFUL POWER READINGS =====")
        for device_type, desc, value in successful_readings:
            print(f"{device_type} - {desc}: {value}")
        return True
    else:
        print("\nNo power readings could be retrieved from the device.")
        return False


async def main():
    parser = argparse.ArgumentParser(description='Get active power from an Echonet device')
    parser.add_argument('host', help='IP address of the Echonet device')
    args = parser.parse_args()
    
    result = await discover_and_test(args.host)
    return 0 if result else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)