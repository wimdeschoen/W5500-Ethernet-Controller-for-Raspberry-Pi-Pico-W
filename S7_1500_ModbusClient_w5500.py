"""
Siemens S7-1500 Modbus TCP Client for W5500
Designed for reliable communication with Siemens PLCs in machine networks
"""

import time
import struct
from w5500_driver import W5500

class SiemensModbusTCP:
    """
    Modbus TCP client optimized for Siemens S7-1500 PLCs
    Includes connection recovery and robust error handling
    """
    
    def __init__(self, w5500, local_ip="192.168.123.29", subnet="255.255.255.0", 
                 gateway="192.168.123.1", mac_addr="02:08:DC:AB:CD:29"):
        """
        Initialize Siemens Modbus TCP client
        
        Args:
            w5500: W5500 driver instance
            local_ip: Local IP address for the W5500
            subnet: Subnet mask
            gateway: Gateway IP address  
            mac_addr: MAC address for the W5500
        """
        self.w5500 = w5500
        self.local_ip = local_ip
        self.subnet = subnet
        self.gateway = gateway
        self.mac_addr = mac_addr
        
        # Connection settings
        self.plc_ip = "192.168.123.10"  # Default S7-1500 address
        self.plc_port = 502  # Standard Modbus TCP port
        self.socket = 0  # Use socket 0 for Modbus
        self.connected = False
        self.transaction_id = 1
        
        # Configure network
        self._setup_network()
        
    def _setup_network(self):
        """Configure W5500 network settings with ARP optimization"""
        print("Configuring W5500 for Siemens network...")
        
        # Apply the ARP fix from our previous debugging
        self._apply_arp_fix()
        
        # Configure network parameters
        self.w5500.set_mac_address(self.mac_addr)
        self.w5500.set_ip_address(self.local_ip)
        self.w5500.set_subnet_mask(self.subnet)
        self.w5500.set_gateway(self.gateway)
        
        # Set optimized retry parameters for industrial networks
        # RTR = 500ms (industrial networks can be slower)
        self.w5500._write_reg(0x0019, 0x00, [0x13, 0x88])  # RTR = 5000 (500ms)
        
        # RCR = 10 retries (more persistent for industrial use)
        self.w5500._write_reg(0x001B, 0x00, 0x0A)  # RCR = 10
        
        print(f"Network configured: {self.local_ip} -> PLC {self.plc_ip}")
        
    def _apply_arp_fix(self):
        """Apply the ARP fix we discovered earlier"""
        # Force close all sockets
        for sock in range(8):
            try:
                socket_bsb = 0x01 + (sock * 4)
                self.w5500._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE
            except:
                pass
        
        # Software reset
        self.w5500._write_reg(0x0000, 0x00, 0x80)  # Set RST bit
        time.sleep_ms(50)
        
        # Enable Force ARP mode for reliable connectivity
        mr = self.w5500._read_reg(0x0000, 0x00, 1)[0]
        self.w5500._write_reg(0x0000, 0x00, mr | 0x02)  # Set FARP bit
        
    def set_plc_address(self, ip_address):
        """Change the PLC IP address"""
        self.plc_ip = ip_address
        print(f"PLC address changed to: {self.plc_ip}")
        
    def connect(self, timeout_ms=10000):
        """
        Connect to the Siemens PLC
        
        Args:
            timeout_ms: Connection timeout in milliseconds
            
        Returns:
            bool: True if connected successfully
        """
        if self.connected:
            print("Already connected to PLC")
            return True
            
        print(f"Connecting to Siemens PLC at {self.plc_ip}:{self.plc_port}...")
        
        try:
            # Ensure socket is closed
            self._close_socket()
            
            # Wait for PHY link
            if not self._wait_for_link():
                raise Exception("PHY link not available")
            
            # Test ARP resolution first
            if not self._test_arp_resolution():
                raise Exception("ARP resolution failed")
            
            # Open TCP socket
            socket_bsb = 0x01  # Socket 0
            
            # Set TCP mode and local port
            self.w5500._write_reg(0x0000, socket_bsb, 0x01)  # TCP mode
            self.w5500._write_reg(0x0004, socket_bsb, [0xC3, 0x50])  # Port 50000
            self.w5500._write_reg(0x0001, socket_bsb, 0x01)  # OPEN command
            
            # Wait for socket to open
            for i in range(50):
                if self.w5500._read_reg(0x0001, socket_bsb, 1)[0] == 0x00:
                    break
                time.sleep_ms(10)
            
            status = self.w5500._read_reg(0x0003, socket_bsb, 1)[0]
            if status != 0x13:  # SOCK_INIT
                raise Exception(f"Socket open failed: 0x{status:02x}")
            
            # Set destination (PLC)
            dest_bytes = [int(x) for x in self.plc_ip.split('.')]
            self.w5500._write_reg(0x000C, socket_bsb, dest_bytes)  # Destination IP
            self.w5500._write_reg(0x0010, socket_bsb, [self.plc_port >> 8, self.plc_port & 0xFF])  # Dest port
            
            # Clear interrupts
            self.w5500._write_reg(0x0002, socket_bsb, 0xFF)
            
            # Connect
            self.w5500._write_reg(0x0001, socket_bsb, 0x04)  # CONNECT command
            
            # Wait for connection with timeout
            start_time = time.ticks_ms()
            while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
                status = self.w5500._read_reg(0x0003, socket_bsb, 1)[0]
                sir = self.w5500._read_reg(0x0002, socket_bsb, 1)[0]
                
                if status == 0x17:  # SOCK_ESTABLISHED
                    self.connected = True
                    print("Connected to Siemens PLC successfully")
                    return True
                elif sir & 0x08:  # TIMEOUT
                    self.w5500._write_reg(0x0002, socket_bsb, 0x08)  # Clear timeout
                    raise Exception("Connection timeout")
                elif status == 0x00:  # SOCK_CLOSED
                    raise Exception("Connection refused by PLC")
                    
                time.sleep_ms(100)
            
            raise Exception("Connection timeout")
            
        except Exception as e:
            print(f"Connection failed: {e}")
            self._close_socket()
            return False
    
    def disconnect(self):
        """Disconnect from the PLC"""
        if self.connected:
            print("Disconnecting from PLC...")
            self._close_socket()
            self.connected = False
            print("Disconnected")
    
    def _close_socket(self):
        """Close the Modbus socket"""
        try:
            socket_bsb = 0x01  # Socket 0
            self.w5500._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE command
            time.sleep_ms(20)
        except:
            pass
    
    def _wait_for_link(self, timeout_ms=5000):
        """Wait for PHY link to be established"""
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            phy = self.w5500.get_phy_status()
            if phy['link']:
                return True
            time.sleep_ms(100)
        return False
    
    def _test_arp_resolution(self):
        """Test ARP resolution using UDP"""
        try:
            # Use socket 1 for ARP test
            socket_bsb = 0x05  # Socket 1
            
            # Close and open UDP socket
            self.w5500._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE
            time.sleep_ms(10)
            
            self.w5500._write_reg(0x0000, socket_bsb, 0x02)  # UDP mode
            self.w5500._write_reg(0x0004, socket_bsb, [0xC3, 0x51])  # Port 50001
            self.w5500._write_reg(0x0001, socket_bsb, 0x01)  # OPEN
            
            # Wait for open
            for i in range(50):
                if self.w5500._read_reg(0x0001, socket_bsb, 1)[0] == 0x00:
                    break
                time.sleep_ms(10)
            
            # Set destination
            dest_bytes = [int(x) for x in self.plc_ip.split('.')]
            self.w5500._write_reg(0x000C, socket_bsb, dest_bytes)
            self.w5500._write_reg(0x0010, socket_bsb, [0x01, 0xF6])  # Port 502
            
            # Send dummy data
            tx_buf_bsb = 0x06  # Socket 1 TX buffer
            self.w5500._write_reg(0x0000, tx_buf_bsb, [0x00, 0x01])  # 2 bytes
            self.w5500._write_reg(0x0024, socket_bsb, [0x00, 0x02])  # TX_WR = 2
            self.w5500._write_reg(0x0001, socket_bsb, 0x20)  # SEND
            
            # Wait for send completion
            for i in range(50):
                cmd = self.w5500._read_reg(0x0001, socket_bsb, 1)[0]
                sir = self.w5500._read_reg(0x0002, socket_bsb, 1)[0]
                
                if cmd == 0x00:  # Command done
                    if sir & 0x10:  # SEND_OK
                        self.w5500._write_reg(0x0001, socket_bsb, 0x10)  # Close UDP socket
                        return True
                    elif sir & 0x08:  # TIMEOUT
                        break
                        
                time.sleep_ms(50)
            
            self.w5500._write_reg(0x0001, socket_bsb, 0x10)  # Close UDP socket
            return False
            
        except:
            return False
    
    def _send_modbus_frame(self, pdu):
        """Send Modbus TCP frame"""
        if not self.connected:
            raise Exception("Not connected to PLC")
        
        # Build MBAP header
        mbap = struct.pack('>HHHB', 
                          self.transaction_id,  # Transaction ID
                          0,                    # Protocol ID (always 0 for Modbus TCP)
                          len(pdu) + 1,        # Length (PDU + Unit ID)
                          1)                    # Unit ID (typically 1 for PLCs)
        
        frame = mbap + pdu
        
        # Send via W5500
        socket_bsb = 0x01  # Socket 0
        tx_buf_bsb = 0x02  # Socket 0 TX buffer
        
        # Get current TX write pointer
        tx_wr_bytes = self.w5500._read_reg(0x0024, socket_bsb, 2)
        tx_wr = struct.unpack('>H', tx_wr_bytes)[0]
        
        # Write frame to TX buffer
        for i, byte in enumerate(frame):
            addr = (tx_wr + i) & 0xFFFF
            self.w5500._write_reg(addr, tx_buf_bsb, byte)
        
        # Update TX write pointer
        new_tx_wr = (tx_wr + len(frame)) & 0xFFFF
        self.w5500._write_reg(0x0024, socket_bsb, struct.pack('>H', new_tx_wr))
        
        # Send command
        self.w5500._write_reg(0x0001, socket_bsb, 0x20)  # SEND
        
        # Wait for send completion
        for i in range(50):
            cmd = self.w5500._read_reg(0x0001, socket_bsb, 1)[0]
            if cmd == 0x00:  # Command completed
                break
            time.sleep_ms(10)
        
        self.transaction_id = (self.transaction_id + 1) & 0xFFFF
    
    def _receive_modbus_response(self, timeout_ms=5000):
        """Receive Modbus TCP response"""
        socket_bsb = 0x01  # Socket 0
        rx_buf_bsb = 0x03  # Socket 0 RX buffer
        
        start_time = time.ticks_ms()
        response_data = bytearray()
        
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            # Check received data size
            rx_rsr_bytes = self.w5500._read_reg(0x0026, socket_bsb, 2)
            rx_rsr = struct.unpack('>H', rx_rsr_bytes)[0]
            
            if rx_rsr > 0:
                # Get RX read pointer
                rx_rd_bytes = self.w5500._read_reg(0x0028, socket_bsb, 2)
                rx_rd = struct.unpack('>H', rx_rd_bytes)[0]
                
                # Read available data
                for i in range(rx_rsr):
                    addr = (rx_rd + i) & 0xFFFF
                    byte = self.w5500._read_reg(addr, rx_buf_bsb, 1)[0]
                    response_data.append(byte)
                
                # Update RX read pointer
                new_rx_rd = (rx_rd + rx_rsr) & 0xFFFF
                self.w5500._write_reg(0x0028, socket_bsb, struct.pack('>H', new_rx_rd))
                
                # RECV command
                self.w5500._write_reg(0x0001, socket_bsb, 0x40)
                
                # Wait for RECV completion
                for j in range(50):
                    cmd = self.w5500._read_reg(0x0001, socket_bsb, 1)[0]
                    if cmd == 0x00:
                        break
                    time.sleep_ms(10)
                
                # Check if we have complete response (at least MBAP header)
                if len(response_data) >= 8:  # MBAP (7) + Function code (1) minimum
                    return bytes(response_data)
            
            time.sleep_ms(50)
        
        raise Exception("Response timeout")
    
    def read_holding_registers(self, start_address, count):
        """
        Read holding registers from Siemens PLC
        
        Args:
            start_address: Starting register address (0-based)
            count: Number of registers to read
            
        Returns:
            list: Register values as 16-bit integers
        """
        if count > 125:  # Modbus TCP limit
            raise ValueError("Maximum 125 registers per request")
        
        # Build PDU (Function 3 - Read Holding Registers)
        pdu = struct.pack('>BHH', 3, start_address, count)
        
        try:
            self._send_modbus_frame(pdu)
            response = self._receive_modbus_response()
            
            # Parse response
            if len(response) < 9:
                raise Exception("Response too short")
            
            # Check MBAP header
            trans_id, proto_id, length, unit_id, func_code = struct.unpack('>HHHBB', response[:8])
            
            if func_code == 3:  # Success
                byte_count = response[8]
                if len(response) < 9 + byte_count:
                    raise Exception("Incomplete response")
                
                data = response[9:9+byte_count]
                registers = []
                
                for i in range(0, len(data), 2):
                    reg_value = struct.unpack('>H', data[i:i+2])[0]
                    registers.append(reg_value)
                
                return registers
                
            elif func_code == 0x83:  # Error response
                error_code = response[8]
                raise Exception(f"Modbus error: {error_code}")
            else:
                raise Exception(f"Unexpected function code: {func_code}")
                
        except Exception as e:
            print(f"Read holding registers failed: {e}")
            return None
    
    def write_single_register(self, address, value):
        """
        Write single holding register to Siemens PLC
        
        Args:
            address: Register address (0-based)
            value: 16-bit value to write
            
        Returns:
            bool: True if successful
        """
        # Build PDU (Function 6 - Write Single Register)
        pdu = struct.pack('>BHH', 6, address, value & 0xFFFF)
        
        try:
            self._send_modbus_frame(pdu)
            response = self._receive_modbus_response()
            
            if len(response) < 8:
                raise Exception("Response too short")
            
            trans_id, proto_id, length, unit_id, func_code = struct.unpack('>HHHBB', response[:8])
            
            if func_code == 6:  # Success - echo of request
                return True
            elif func_code == 0x86:  # Error response
                error_code = response[8]
                raise Exception(f"Modbus error: {error_code}")
            else:
                raise Exception(f"Unexpected function code: {func_code}")
                
        except Exception as e:
            print(f"Write single register failed: {e}")
            return False
    
    def write_multiple_registers(self, start_address, values):
        """
        Write multiple holding registers to Siemens PLC
        
        Args:
            start_address: Starting register address (0-based)
            values: List of 16-bit values to write
            
        Returns:
            bool: True if successful
        """
        if len(values) > 123:  # Modbus TCP limit
            raise ValueError("Maximum 123 registers per request")
        
        # Build data bytes
        data_bytes = bytearray()
        for value in values:
            data_bytes.extend(struct.pack('>H', value & 0xFFFF))
        
        # Build PDU (Function 16 - Write Multiple Registers)
        pdu = struct.pack('>BHHB', 16, start_address, len(values), len(data_bytes))
        pdu += data_bytes
        
        try:
            self._send_modbus_frame(pdu)
            response = self._receive_modbus_response()
            
            if len(response) < 8:
                raise Exception("Response too short")
            
            trans_id, proto_id, length, unit_id, func_code = struct.unpack('>HHHBB', response[:8])
            
            if func_code == 16:  # Success
                return True
            elif func_code == 0x90:  # Error response
                error_code = response[8]
                raise Exception(f"Modbus error: {error_code}")
            else:
                raise Exception(f"Unexpected function code: {func_code}")
                
        except Exception as e:
            print(f"Write multiple registers failed: {e}")
            return False
    
    def read_input_registers(self, start_address, count):
        """
        Read input registers from Siemens PLC
        
        Args:
            start_address: Starting register address (0-based)
            count: Number of registers to read
            
        Returns:
            list: Register values as 16-bit integers
        """
        if count > 125:  # Modbus TCP limit
            raise ValueError("Maximum 125 registers per request")
        
        # Build PDU (Function 4 - Read Input Registers)
        pdu = struct.pack('>BHH', 4, start_address, count)
        
        try:
            self._send_modbus_frame(pdu)
            response = self._receive_modbus_response()
            
            if len(response) < 9:
                raise Exception("Response too short")
            
            trans_id, proto_id, length, unit_id, func_code = struct.unpack('>HHHBB', response[:8])
            
            if func_code == 4:  # Success
                byte_count = response[8]
                if len(response) < 9 + byte_count:
                    raise Exception("Incomplete response")
                
                data = response[9:9+byte_count]
                registers = []
                
                for i in range(0, len(data), 2):
                    reg_value = struct.unpack('>H', data[i:i+2])[0]
                    registers.append(reg_value)
                
                return registers
                
            elif func_code == 0x84:  # Error response
                error_code = response[8]
                raise Exception(f"Modbus error: {error_code}")
            else:
                raise Exception(f"Unexpected function code: {func_code}")
                
        except Exception as e:
            print(f"Read input registers failed: {e}")
            return None
    
    def is_connected(self):
        """Check if connected to PLC"""
        if not self.connected:
            return False
        
        # Check socket status
        try:
            socket_bsb = 0x01
            status = self.w5500._read_reg(0x0003, socket_bsb, 1)[0]
            return status == 0x17  # SOCK_ESTABLISHED
        except:
            return False
    
    def reconnect(self):
        """Reconnect to PLC after connection loss"""
        print("Attempting to reconnect to PLC...")
        self.connected = False
        self._apply_arp_fix()  # Apply ARP fix before reconnecting
        time.sleep_ms(100)
        return self.connect()


# Example usage and test functions
def test_siemens_connection():
    """Test connection to Siemens PLC"""
    print("Siemens S7-1500 Modbus TCP Test")
    print("=" * 40)
    
    # Initialize W5500
    try:
        w5500 = W5500(sck_pin=10, mosi_pin=11, miso_pin=12, cs_pin=13, rst_pin=15)
        print("W5500 initialized")
    except Exception as e:
        print(f"W5500 init failed: {e}")
        return
    
    # Create Siemens Modbus client
    plc = SiemensModbusTCP(w5500)
    
    try:
        # Connect to PLC
        if plc.connect():
            print("Connected to Siemens PLC")
            
            # Test read holding registers
            print("\nTesting read holding registers...")
            registers = plc.read_holding_registers(0, 10)  # Read first 10 registers
            if registers:
                print(f"Registers 0-9: {registers}")
            
            # Test write single register
            print("\nTesting write single register...")
            if plc.write_single_register(100, 1234):
                print("Write successful")
                
                # Read back to verify
                verify = plc.read_holding_registers(100, 1)
                if verify:
                    print(f"Verified value: {verify[0]}")
            
            # Test connection status
            print(f"\nConnection status: {'Connected' if plc.is_connected() else 'Disconnected'}")
            
        else:
            print("Failed to connect to PLC")
            
    except Exception as e:
        print(f"Test error: {e}")
    finally:
        plc.disconnect()

if __name__ == "__main__":
    test_siemens_connection()