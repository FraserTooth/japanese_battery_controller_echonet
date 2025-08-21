# pychonet v2.x Migration Guide

This guide explains the key differences between pychonet v0.x and v2.x and how to properly use the newer API.

## Key Changes from v0.x to v2.x

### 1. Constructor Signatures

**v0.x (Old):**
```python
# Old way - typically took fewer parameters
device = StorageBattery(host, instance)
device = HomeSolarPower(host, instance) 
device = EchonetInstance(host, eojgc, eojcc, instance)
```

**v2.x (New):**
```python
# New way - requires api_connector parameter
device = StorageBattery(host, api_connector, instance=0x1)
device = HomeSolarPower(host, api_connector, instance=0x1)  # Note: NOT optional!
device = EchonetInstance(host, eojgc, eojcc, instance, api_connector)
```

**Key Changes:**
- `api_connector` parameter is **required** for `HomeSolarPower` 
- `api_connector` parameter is **optional** for `StorageBattery` (defaults to `None`)
- `instance` parameter has default value `0x1` for device-specific classes
- Parameter order changed: `api_connector` comes before `instance`

### 2. Server and Client Setup

**v2.x Standard Setup:**
```python
from pychonet.lib.udpserver import UDPServer
from pychonet import ECHONETAPIClient as api

# Initialize UDP server
udp = UDPServer()
loop = asyncio.get_event_loop()
udp.run("0.0.0.0", 3610, loop=loop)

# Create API client 
server = api(server=udp)
```

### 3. Device Discovery

**v2.x Discovery Process:**
```python
# Send discovery request
await server.discover(host)

# Wait and check server state
for i in range(timeout * 10):
    await asyncio.sleep(0.1)
    if host in server._state:
        # Device discovered
        break
```

**Key Points:**
- Discovery is asynchronous and may not return immediately
- Check `server._state[host]` to verify discovery success
- Device instances are stored in `server._state[host]["instances"]`

### 4. Available Methods

**StorageBattery Methods (v2.x):**
```python
# Inherited from EchonetInstance
await device.getOperationalStatus()     # Get ON/OFF status
await device.getInstantaneousPower()    # Get instantaneous power (EPC 0x84)
await device.getCumulativePower()       # Get cumulative power (EPC 0x85)
await device.getMessage(epc)            # Direct EPC access
await device.update()                   # Get all available properties
await device.getAllPropertyMaps()       # Get property maps

# Device control
await device.on()                       # Turn device on
await device.off()                      # Turn device off
```

**HomeSolarPower Methods (v2.x):**
```python
# Solar-specific methods
await device.getMeasuredInstantPower()  # EPC 0xE0 - Instantaneous generation
await device.getMeasuredCumulPower()    # EPC 0xE1 - Cumulative generation

# Inherited methods (same as StorageBattery)
await device.getInstantaneousPower()    # EPC 0x84
await device.getCumulativePower()       # EPC 0x85
await device.getMessage(epc)            # Direct EPC access
# ... etc
```

### 5. Power Property Access

**StorageBattery Power Properties:**
```python
# Method approach
power = await device.getInstantaneousPower()  # Generic power

# Direct EPC approach for battery-specific properties
charge_discharge = await device.getMessage(0xD3)  # Charging/discharging power
current = await device.getMessage(0xD4)           # Charging/discharging current  
voltage = await device.getMessage(0xD5)           # Charging/discharging voltage
battery_level = await device.getMessage(0xE2)     # Remaining stored electricity
```

**HomeSolarPower Power Properties:**
```python
# Solar-specific methods
instant_gen = await device.getMeasuredInstantPower()  # EPC 0xE0
cumul_gen = await device.getMeasuredCumulPower()      # EPC 0xE1

# Direct EPC approach
power_gen = await device.getMessage(0xE0)             # Instantaneous generation
cumulative = await device.getMessage(0xE1)            # Cumulative generation
system_type = await device.getMessage(0xD0)           # System interconnection type
```

### 6. Error Handling

**v2.x Error Patterns:**
```python
try:
    result = await device.getMessage(epc)
    if result is not False:  # Check for False (failed request)
        print(f"Success: {result}")
    else:
        print("Request failed")
except Exception as e:
    print(f"Error: {e}")
```

**Key Points:**
- Methods return `False` on failure, not `None`
- Always check for `result is not False` 
- Wrap in try/except for additional error handling

### 7. State Management

**v2.x State Access:**
```python
# Check if device exists
if host in server._state:
    # Access device instances
    instances = server._state[host]["instances"]
    
    # Iterate through discovered devices
    for eojgc in instances:
        for eojcc in instances[eojgc]:
            for instance in instances[eojgc][eojcc]:
                # Create device object
                device = StorageBattery(host, server, instance)
```

## Common EPC Codes for Power Devices

### StorageBattery (0x02-0x7D)
- `0xD3`: Measured instantaneous charging/discharging power
- `0xD4`: Measured instantaneous charging/discharging current
- `0xD5`: Measured instantaneous charging/discharging voltage
- `0xE2`: Remaining stored electricity 1
- `0xE4`: Remaining stored electricity 3
- `0xCF`: Working operation status

### HomeSolarPower (0x02-0x79)  
- `0xE0`: Measured instantaneous power generation
- `0xE1`: Measured cumulative power generation
- `0xD0`: System-interconnected type
- `0xD1`: Output power restraint status

### Common (All Devices)
- `0x80`: Operation status (ON/OFF)
- `0x84`: Instantaneous power consumption
- `0x85`: Cumulative power consumption
- `0x8A`: Manufacturer code

## Migration Checklist

- [ ] Update constructor calls to include `api_connector` parameter
- [ ] Ensure `HomeSolarPower` constructor has required `api_connector`
- [ ] Update server setup to use `UDPServer()` and `ECHONETAPIClient`
- [ ] Implement proper discovery waiting logic
- [ ] Check method return values for `False` instead of `None`
- [ ] Use `server._state` to access discovered devices
- [ ] Test EPC direct access with `getMessage()`
- [ ] Verify property maps are retrieved with `getAllPropertyMaps()`

## Complete Working Example

See `src/pychonet_v2_example.py` for a comprehensive working example that demonstrates all the concepts above.