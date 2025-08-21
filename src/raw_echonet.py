#!/usr/bin/env python3
import asyncio
import socket
import argparse
import sys
import time
import binascii

# ECHONET Lite constants
ENL_PORT = 3610
ENL_MULTICAST = "224.0.23.0"

# Common EPC codes
EPC_OPERATIONAL_STATUS = 0x80
EPC_INSTALLATION_LOCATION = 0x81
EPC_MANUFACTURER_CODE = 0x8A
EPC_POWER_CONSUMPTION = 0x84
EPC_CUMULATIVE_POWER = 0x85
EPC_INSTANTANEOUS_POWER = 0xE0
EPC_BATTERY_CHARGE_DISCHARGE = 0xD3

def create_echonet_packet(tid, eojgc, eojcc, eojci, esv, props):
    """Create an ECHONET Lite packet"""
    # ECHONET Lite header (EHD)
    ehd1 = 0x10  # ECHONET Lite message
    ehd2 = 0x81  # Format 1
    
    # Transaction ID (TID)
    tid_high = (tid >> 8) & 0xFF
    tid_low = tid & 0xFF
    
    # ECHONET Lite object (EOJ) - source (controller)
    seoj1 = 0x05  # Controller class group
    seoj2 = 0xFF  # Controller class
    seoj3 = 0x01  # Instance number
    
    # ECHONET Lite object (EOJ) - destination
    deoj1 = eojgc  # Class group
    deoj2 = eojcc  # Class code
    deoj3 = eojci  # Instance number
    
    # Service (ESV)
    esv_code = esv
    
    # Properties
    opc = len(props)  # Number of properties
    
    # Build the packet
    packet = bytearray([
        ehd1, ehd2,
        tid_high, tid_low,
        seoj1, seoj2, seoj3,
        deoj1, deoj2, deoj3,
        esv_code,
        opc
    ])
    
    # Add properties
    for prop in props:
        epc = prop[0]
        pdc = prop[1]
        edt = prop[2:]
        
        packet.extend([epc, pdc])
        if pdc > 0:
            packet.extend(edt)
    
    return packet


def parse_echonet_response(data):
    """Parse ECHONET Lite response packet"""
    try:
        # Basic header validation
        if len(data) < 12:
            return None
        
        # Extract header components
        ehd = (data[0] << 8) | data[1]
        tid = (data[2] << 8) | data[3]
        seoj = (data[4], data[5], data[6])
        deoj = (data[7], data[8], data[9])
        esv = data[10]
        opc = data[11]
        
        # Parse properties
        props = []
        idx = 12
        for i in range(opc):
            if idx + 2 > len(data):
                break
                
            epc = data[idx]
            pdc = data[idx + 1]
            
            if idx + 2 + pdc > len(data):
                break
                
            edt = data[idx + 2:idx + 2 + pdc]
            props.append((epc, pdc, edt))
            
            idx += 2 + pdc
            
        return {
            'ehd': ehd,
            'tid': tid,
            'seoj': seoj,
            'deoj': deoj,
            'esv': esv,
            'opc': opc,
            'props': props
        }
    except Exception as e:
        print(f"Error parsing packet: {e}")
        return None


def format_property_value(epc, edt):
    """Format property value based on EPC code"""
    try:
        # Common EPC codes
        if epc == EPC_OPERATIONAL_STATUS:
            return "ON" if edt[0] == 0x30 else "OFF"
        elif epc == EPC_MANUFACTURER_CODE:
            return f"Manufacturer: {binascii.hexlify(edt).decode()}"
        elif epc == EPC_POWER_CONSUMPTION:
            if len(edt) >= 2:
                return f"{int.from_bytes(edt, byteorder='big')} W"
        elif epc == EPC_CUMULATIVE_POWER:
            if len(edt) >= 4:
                return f"{int.from_bytes(edt, byteorder='big')} kWh"
        elif epc == EPC_INSTANTANEOUS_POWER:
            if len(edt) >= 2:
                return f"{int.from_bytes(edt, byteorder='big')} W"
        elif epc == EPC_BATTERY_CHARGE_DISCHARGE:
            if len(edt) >= 2:
                val = int.from_bytes(edt, byteorder='big', signed=True)
                if val >= 0:
                    return f"Charging: {val} W"
                else:
                    return f"Discharging: {-val} W"
        
        # Default: return hex representation
        return f"Raw: {binascii.hexlify(edt).decode()}"
    except Exception as e:
        return f"Error formatting: {e}"


async def probe_echonet_device(host, port=ENL_PORT):
    """Probe an ECHONET Lite device for power-related properties"""
    print(f"Probing ECHONET Lite device at {host}:{port}...")
    
    # Device types to probe (group, class, instance)
    device_types = [
        (0x02, 0x7D, 0x01, "Storage Battery"),
        (0x02, 0x79, 0x01, "Home Solar Power"),
        (0x02, 0x88, 0x01, "Smart Electric Energy Meter"),
        (0x05, 0xFF, 0x01, "Controller"),
        (0x00, 0x11, 0x01, "Temperature Sensor")
    ]
    
    # Properties to request for each device type
    property_sets = [
        # Basic properties
        [
            (EPC_OPERATIONAL_STATUS, 0),
            (EPC_INSTALLATION_LOCATION, 0),
            (EPC_MANUFACTURER_CODE, 0)
        ],
        # Power-related properties
        [
            (EPC_POWER_CONSUMPTION, 0),
            (EPC_CUMULATIVE_POWER, 0)
        ],
        # Solar/Battery specific
        [
            (EPC_INSTANTANEOUS_POWER, 0),
            (EPC_BATTERY_CHARGE_DISCHARGE, 0)
        ]
    ]
    
    # Create UDP socket for communication
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(2.0)
    
    successful_readings = []
    
    # Try each device type
    for eojgc, eojcc, eojci, device_name in device_types:
        print(f"\n=== Testing {device_name} (Group: 0x{eojgc:02X}, Class: 0x{eojcc:02X}, Instance: 0x{eojci:02X}) ===")
        
        # Try each property set
        for prop_set in property_sets:
            tid = int(time.time() * 1000) & 0xFFFF
            packet = create_echonet_packet(tid, eojgc, eojcc, eojci, 0x62, prop_set)  # 0x62 = Get
            
            try:
                # Send the packet
                sock.sendto(packet, (host, port))
                
                # Wait for response with timeout
                try:
                    response, addr = sock.recvfrom(1024)
                    
                    # Parse the response
                    parsed = parse_echonet_response(response)
                    if parsed:
                        print(f"Received response from {addr[0]}:{addr[1]}")
                        print(f"TID: 0x{parsed['tid']:04X}")
                        print(f"ESV: 0x{parsed['esv']:02X}")
                        print(f"Properties: {parsed['opc']}")
                        
                        # Process properties
                        for prop in parsed['props']:
                            epc, pdc, edt = prop
                            formatted_value = format_property_value(epc, edt)
                            print(f"  Property EPC: 0x{epc:02X}, PDC: {pdc}, Value: {formatted_value}")
                            
                            if pdc > 0:  # Valid response with data
                                successful_readings.append((device_name, f"EPC 0x{epc:02X}", formatted_value))
                except socket.timeout:
                    print(f"No response received (timeout)")
            except Exception as e:
                print(f"Error sending/receiving data: {e}")
            
            # Wait a bit before next request
            await asyncio.sleep(0.5)
    
    # Close the socket
    sock.close()
    
    # Summary of successful readings
    if successful_readings:
        print("\n===== SUCCESSFUL READINGS =====")
        for device_type, epc, value in successful_readings:
            print(f"{device_type} - {epc}: {value}")
        return True
    else:
        print("\nNo readings could be retrieved from the device.")
        return False


async def main():
    parser = argparse.ArgumentParser(description='Probe ECHONET Lite device for power information')
    parser.add_argument('host', help='IP address of the ECHONET Lite device')
    parser.add_argument('--port', type=int, default=ENL_PORT, help='UDP port (default: 3610)')
    args = parser.parse_args()
    
    result = await probe_echonet_device(args.host, args.port)
    return 0 if result else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)