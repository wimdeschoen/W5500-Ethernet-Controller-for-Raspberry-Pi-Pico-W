# W5500-Ethernet-Controller-for-Raspberry-Pi-Pico-W
A comprehensive MicroPython driver and Modbus TCP client for the WIZnet W5500 Ethernet controller, specifically designed for industrial automation and PLC communication.

Features

Complete W5500 Driver: Full SPI communication with register management
Robust Connection Handling: Automatic recovery from cable disconnections
Modbus TCP Client: Industrial-grade communication with Siemens S7-1500 PLCs
Connection Diagnostics: Comprehensive testing and debugging tools
ARP Table Management: Handles network state recovery after link interruptions

Hardware Requirements

Raspberry Pi Pico W
WIZnet W5500 Ethernet Module
SPI connections as specified below

Wiring
W5500 PinPico PinFunctionSCKGP10SPI ClockMOSIGP11SPI Master OutMISOGP12SPI Master InCSGP13Chip SelectRSTGP15ResetVCC3V3Power SupplyGNDGNDGround
Quick Start
Basic W5500 Setup
pythonfrom w5500_driver import W5500

# Initialize W5500
w5500 = W5500(sck_pin=10, mosi_pin=11, miso_pin=12, cs_pin=13, rst_pin=15)

# Configure network
w5500.set_mac_address("02:08:DC:15:00:28")
w5500.set_ip_address("192.168.1.100")
w5500.set_subnet_mask("255.255.255.0")
w5500.set_gateway("192.168.1.1")

# Check PHY status
phy = w5500.get_phy_status()
print(f"Link: {'UP' if phy['link'] else 'DOWN'}")
Siemens PLC Communication
pythonfrom w5500_driver import W5500
from siemens_modbus_client import SiemensModbusTCP

# Initialize hardware
w5500 = W5500(sck_pin=10, mosi_pin=11, miso_pin=12, cs_pin=13, rst_pin=15)

# Create Modbus client for machine network
plc = SiemensModbusTCP(w5500, 
                      local_ip="192.168.123.29",
                      plc_ip="192.168.123.10")

# Connect and read data
if plc.connect():
    # Read holding registers
    data = plc.read_holding_registers(0, 10)
    print(f"PLC Data: {data}")
    
    # Write to PLC
    plc.write_single_register(100, 1234)
    
    plc.disconnect()
File Structure
├── w5500_driver.py              # Core W5500 driver
├── siemens_modbus_client.py     # Modbus TCP client for Siemens PLCs
├── detailed_socket_debug.py     # Socket debugging tools
├── arp_debug_script.py          # ARP resolution diagnostics
├── improved_diagnostics.py      # Enhanced diagnostic suite
└── simple_reset_test.py         # Basic connectivity tests
Core Components
W5500 Driver (w5500_driver.py)
Key Classes:

W5500: Main driver class with SPI communication
W5500ModbusTCP: Basic Modbus TCP implementation

Features:

Variable Data Mode (VDM) SPI communication
Socket management (TCP/UDP)
Network configuration
PHY status monitoring
Hardware and software reset capabilities

Siemens Modbus Client (siemens_modbus_client.py)
Class: SiemensModbusTCP
Supported Functions:

read_holding_registers(start, count) - Function Code 3
write_single_register(address, value) - Function Code 6
write_multiple_registers(start, values) - Function Code 16
read_input_registers(start, count) - Function Code 4

Built-in Features:

Automatic ARP table management
Connection monitoring and recovery
Industrial network timeouts (500ms, 10 retries)
Force ARP mode for reliable connectivity

Diagnostic Tools
Hardware Diagnostics
python# Run comprehensive hardware tests
exec(open('improved_diagnostics.py').read())

# Test ARP resolution specifically
exec(open('arp_debug_script.py').read())

# Simple connectivity test
exec(open('simple_reset_test.py').read())
Socket Debugging
python# Detailed socket state monitoring
exec(open('detailed_socket_debug.py').read())
Network Configuration Examples
Standard Network
pythonw5500.set_ip_address("192.168.1.100")
w5500.set_subnet_mask("255.255.255.0")
w5500.set_gateway("192.168.1.1")
Machine Network (Siemens)
pythonplc = SiemensModbusTCP(w5500,
                      local_ip="192.168.123.29",
                      subnet="255.255.255.0",
                      gateway="192.168.123.1")
plc.set_plc_address("192.168.123.10")
Troubleshooting
Connection Issues After Cable Disconnect
The driver includes automatic recovery mechanisms:
python# Manual recovery if needed
plc.reconnect()

# Or use the built-in ARP fix
from arp_debug_script import clear_arp_and_reset
clear_arp_and_reset(w5500)
Common Error Codes
Status CodeDescriptionSolution0x00Socket ClosedCheck network configuration0x13Socket InitNormal state after opening0x17Socket EstablishedConnection successful0x22UDP SocketUDP mode active
PHY Link Issues
python# Check PHY status
phy = w5500.get_phy_status()
print(f"Link: {phy['link']}")
print(f"Speed: {'100M' if phy['speed_100m'] else '10M'}")
print(f"Duplex: {'Full' if phy['full_duplex'] else 'Half'}")
Advanced Usage
Custom Retry Settings
python# Set custom retry parameters
w5500._write_reg(0x0019, 0x00, [0x13, 0x88])  # RTR = 500ms
w5500._write_reg(0x001B, 0x00, 0x0F)          # RCR = 15 retries
Force ARP Mode
python# Enable Force ARP for problematic networks
mr = w5500._read_reg(0x0000, 0x00, 1)[0]
w5500._write_reg(0x0000, 0x00, mr | 0x02)  # Set FARP bit
Multiple Socket Management
python# Open multiple sockets
status0 = w5500.socket_open(0, 0x01, 8000)  # TCP socket 0
status1 = w5500.socket_open(1, 0x02, 8001)  # UDP socket 1

# Close all sockets
for sock in range(8):
    w5500.socket_close(sock)
Technical Specifications

SPI Mode: Mode 0 and Mode 3 supported
SPI Frequency: Up to 80MHz (tested at 10MHz)
Socket Count: 8 independent hardware sockets
Buffer Size: 32KB total (16KB TX + 16KB RX)
Protocols: TCP, UDP, IPv4, ICMP, ARP, IGMP, PPPoE
PHY: 10/100 Ethernet with auto-negotiation

Development Notes
MicroPython Compatibility
This driver is specifically designed for MicroPython and includes:

Memory-efficient register access
Non-blocking socket operations
Proper error handling for embedded systems
No dependencies on Python standard library modules not available in MicroPython

Performance Considerations

Use appropriate SPI frequencies (10-33MHz recommended)
Implement proper socket cleanup to prevent resource leaks
Monitor PHY status for link state changes
Use Force ARP mode only when necessary (increases network traffic)

Contributing
When contributing to this project:

Test all changes with actual hardware
Maintain compatibility with MicroPython constraints
Include diagnostic output for debugging
Document any new network configuration requirements
Test cable disconnect/reconnect scenarios

License
This project is provided as-is for educational and industrial automation purposes. Please ensure compliance with your local regulations when using in commercial applications.
References

WIZnet W5500 Datasheet
Modbus TCP Specification
Siemens S7-1500 Modbus Documentation


Author: Wim Deschoenmaeker
Hardware: Raspberry Pi Pico W + WIZnet W5500
Application: Industrial automation and PLC communication
