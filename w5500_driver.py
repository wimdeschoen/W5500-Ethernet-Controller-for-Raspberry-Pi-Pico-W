#Version = v6

import machine
import time
import struct
from micropython import const

# W5500 Block Select Bits (BSB)
_BSB_COMMON_REG = const(0x00)
_BSB_S0_REG = const(0x01)
_BSB_S0_TX_BUF = const(0x02)
_BSB_S0_RX_BUF = const(0x03)

# Common Register Addresses
_MR = const(0x0000)          # Mode Register
_GAR = const(0x0001)         # Gateway Address Register (4 bytes)
_SUBR = const(0x0005)        # Subnet Mask Register (4 bytes)
_SHAR = const(0x0009)        # Source Hardware Address Register (6 bytes)
_SIPR = const(0x000F)        # Source IP Address Register (4 bytes)
_INTLEVEL = const(0x0013)    # Interrupt Low Level Timer Register
_IR = const(0x0015)          # Interrupt Register
_IMR = const(0x0016)         # Interrupt Mask Register
_SIR = const(0x0017)         # Socket Interrupt Register
_SIMR = const(0x0018)        # Socket Interrupt Mask Register
_RTR = const(0x0019)         # Retry Time Register (2 bytes)
_RCR = const(0x001B)         # Retry Count Register
_PHYCFGR = const(0x002E)     # PHY Configuration Register
_VERSIONR = const(0x0039)    # Chip Version Register

# Socket Register Addresses (offset from socket base)
_Sn_MR = const(0x0000)       # Socket Mode Register
_Sn_CR = const(0x0001)       # Socket Command Register
_Sn_IR = const(0x0002)       # Socket Interrupt Register
_Sn_SR = const(0x0003)       # Socket Status Register
_Sn_PORT = const(0x0004)     # Socket Source Port Register (2 bytes)
_Sn_DHAR = const(0x0006)     # Socket Destination Hardware Address (6 bytes)
_Sn_DIPR = const(0x000C)     # Socket Destination IP Address (4 bytes)
_Sn_DPORT = const(0x0010)    # Socket Destination Port Register (2 bytes)
_Sn_MSSR = const(0x0012)     # Socket Maximum Segment Size Register (2 bytes)
_Sn_RXBUF_SIZE = const(0x001E) # Socket RX Buffer Size Register
_Sn_TXBUF_SIZE = const(0x001F) # Socket TX Buffer Size Register
_Sn_TX_FSR = const(0x0020)   # Socket TX Free Size Register (2 bytes)
_Sn_TX_RD = const(0x0022)    # Socket TX Read Pointer Register (2 bytes)
_Sn_TX_WR = const(0x0024)    # Socket TX Write Pointer Register (2 bytes)
_Sn_RX_RSR = const(0x0026)   # Socket RX Received Size Register (2 bytes)
_Sn_RX_RD = const(0x0028)    # Socket RX Read Pointer Register (2 bytes)
_Sn_RX_WR = const(0x002A)    # Socket RX Write Pointer Register (2 bytes)
_Sn_IMR = const(0x002C)      # Socket Interrupt Mask Register

# Socket Commands
_CMD_OPEN = const(0x01)
_CMD_LISTEN = const(0x02)
_CMD_CONNECT = const(0x04)
_CMD_DISCON = const(0x08)
_CMD_CLOSE = const(0x10)
_CMD_SEND = const(0x20)
_CMD_RECV = const(0x40)

# Socket Status Values
_SOCK_CLOSED = const(0x00)
_SOCK_INIT = const(0x13)
_SOCK_LISTEN_STATE = const(0x14)
_SOCK_ESTABLISHED = const(0x17)
_SOCK_UDP = const(0x22)

# Socket Mode Values
_Sn_MR_CLOSE = const(0x00)
_Sn_MR_TCP = const(0x01)
_Sn_MR_UDP = const(0x02)

# SPI Operation Mode
_VDM = const(0x00)   # Variable Data Mode
_FDM1 = const(0x01)  # Fixed Data Mode, 1 byte
_FDM2 = const(0x02)  # Fixed Data Mode, 2 bytes
_FDM4 = const(0x03)  # Fixed Data Mode, 4 bytes


class W5500:
    def __init__(self, sck_pin=10, mosi_pin=11, miso_pin=12, cs_pin=13, rst_pin=15, 
                 spi_freq=10000000):
        """
        Initialize W5500 Ethernet controller
        
        Args:
            sck_pin: SPI clock pin (default GP10)
            mosi_pin: SPI MOSI pin (default GP11)  
            miso_pin: SPI MISO pin (default GP12)
            cs_pin: Chip select pin (default GP13)
            rst_pin: Reset pin (default GP15)
            spi_freq: SPI frequency in Hz (default 10MHz)
        """
        # Initialize GPIO pins
        self.cs = machine.Pin(cs_pin, machine.Pin.OUT)
        self.rst = machine.Pin(rst_pin, machine.Pin.OUT)
        
        # Initialize SPI
        self.spi = machine.SPI(1, baudrate=spi_freq, 
                              sck=machine.Pin(sck_pin),
                              mosi=machine.Pin(mosi_pin), 
                              miso=machine.Pin(miso_pin),
                              polarity=0, phase=0)
        
        # Set initial pin states
        self.cs.value(1)  # CS high (deselected)
        self.rst.value(0) # Reset low
        
        # Hardware reset
        self.reset()
    
    def reset(self):
        """Hardware reset of W5500"""
        self.rst.value(0)
        time.sleep_ms(1)
        self.rst.value(1)
        time.sleep_ms(10)
    
    def prepare_for_configuration(self):
        """Prepare W5500 for network configuration - resets everything"""
        print("Preparing W5500 for configuration...")
        
        # Full reset sequence
        self.full_reset()
        
        # Wait for everything to stabilize
        time.sleep_ms(100)
        
        # Verify chip is responding
        for attempt in range(5):
            try:
                version = self.get_version()
                if version == 0x04:
                    print("W5500 ready for configuration")
                    return True
            except Exception:
                pass
            time.sleep_ms(50)
        
        print("WARNING: W5500 may not be responding correctly after reset")
        return False  # Wait for reset to complete
    
    def _write_reg(self, addr, bsb, data):
        """Write data to W5500 register using Variable Data Mode"""
        if isinstance(data, int):
            data = bytes([data])
        elif isinstance(data, (list, tuple)):
            data = bytes(data)
            
        # Create SPI frame: Address(2) + Control(1) + Data(n)
        addr_bytes = struct.pack('>H', addr)  # 16-bit address, big-endian
        control = (bsb << 3) | 0x04  # BSB[4:0] + RWB(1) + OM[1:0](00)
        
        self.cs.value(0)  # Select chip
        try:
            self.spi.write(addr_bytes)
            self.spi.write(bytes([control]))
            self.spi.write(data)
        finally:
            self.cs.value(1)  # Deselect chip
    
    def _read_reg(self, addr, bsb, length=1):
        """Read data from W5500 register using Variable Data Mode"""
        # Create SPI frame: Address(2) + Control(1) 
        addr_bytes = struct.pack('>H', addr)  # 16-bit address, big-endian
        control = (bsb << 3) | 0x00  # BSB[4:0] + RWB(0) + OM[1:0](00)
        
        self.cs.value(0)  # Select chip
        try:
            self.spi.write(addr_bytes)
            self.spi.write(bytes([control]))
            data = self.spi.read(length)
        finally:
            self.cs.value(1)  # Deselect chip
            
        return data
    
    def get_version(self):
        """Get W5500 chip version (should return 0x04)"""
        return self._read_reg(_VERSIONR, _BSB_COMMON_REG, 1)[0]
    
    def set_mac_address(self, mac):
        """Set MAC address (6 bytes)"""
        if isinstance(mac, str):
            # Convert string format "00:11:22:33:44:55" to bytes
            mac = bytes([int(x, 16) for x in mac.split(':')])
        self._write_reg(_SHAR, _BSB_COMMON_REG, mac)
    
    def get_mac_address(self):
        """Get MAC address"""
        mac_bytes = self._read_reg(_SHAR, _BSB_COMMON_REG, 6)
        return ':'.join(['{:02x}'.format(b) for b in mac_bytes])
    
    def set_ip_address(self, ip):
        """Set IP address"""
        if isinstance(ip, str):
            ip = bytes([int(x) for x in ip.split('.')])
        self._write_reg(_SIPR, _BSB_COMMON_REG, ip)
    
    def get_ip_address(self):
        """Get IP address"""
        ip_bytes = self._read_reg(_SIPR, _BSB_COMMON_REG, 4)
        return '.'.join([str(b) for b in ip_bytes])
    
    def set_subnet_mask(self, mask):
        """Set subnet mask"""
        if isinstance(mask, str):
            mask = bytes([int(x) for x in mask.split('.')])
        self._write_reg(_SUBR, _BSB_COMMON_REG, mask)
    
    def set_gateway(self, gateway):
        """Set gateway address"""
        if isinstance(gateway, str):
            gateway = bytes([int(x) for x in gateway.split('.')])
        self._write_reg(_GAR, _BSB_COMMON_REG, gateway)
    
    def get_phy_status(self):
        """Get PHY configuration and status"""
        phycfgr = self._read_reg(_PHYCFGR, _BSB_COMMON_REG, 1)[0]
        return {
            'link': bool(phycfgr & 0x01),
            'speed_100m': bool(phycfgr & 0x02),
            'full_duplex': bool(phycfgr & 0x04),
            'raw_value': phycfgr
        }
    
    def socket_open(self, socket_num, mode, port):
        """Open a socket"""
        if socket_num > 7:
            raise ValueError("Socket number must be 0-7")
            
        # Calculate socket register BSB
        socket_bsb = 0x01 + (socket_num * 4)
        
        # Set socket mode
        self._write_reg(_Sn_MR, socket_bsb, mode)
        
        # Set source port
        self._write_reg(_Sn_PORT, socket_bsb, struct.pack('>H', port))
        
        # Open socket
        self._write_reg(_Sn_CR, socket_bsb, _CMD_OPEN)
        
        # Wait for command to complete
        while self._read_reg(_Sn_CR, socket_bsb, 1)[0] != 0:
            time.sleep_ms(1)
        
        # Check if socket opened successfully
        status = self._read_reg(_Sn_SR, socket_bsb, 1)[0]
        return status
    
    def socket_close(self, socket_num):
        """Close a socket"""
        socket_bsb = 0x01 + (socket_num * 4)
        self._write_reg(_Sn_CR, socket_bsb, _CMD_CLOSE)
        
        # Wait for command to complete
        while self._read_reg(_Sn_CR, socket_bsb, 1)[0] != 0:
            time.sleep_ms(1)
    
    def socket_status(self, socket_num):
        """Get socket status"""
        socket_bsb = 0x01 + (socket_num * 4)
        return self._read_reg(_Sn_SR, socket_bsb, 1)[0]
    
    def socket_connect(self, socket_num, dest_ip, dest_port):
        """Connect socket to destination (TCP)"""
        socket_bsb = 0x01 + (socket_num * 4)
        
        # Set destination IP
        if isinstance(dest_ip, str):
            dest_ip = bytes([int(x) for x in dest_ip.split('.')])
        self._write_reg(_Sn_DIPR, socket_bsb, dest_ip)
        
        # Set destination port
        self._write_reg(_Sn_DPORT, socket_bsb, struct.pack('>H', dest_port))
        
        # Connect
        self._write_reg(_Sn_CR, socket_bsb, _CMD_CONNECT)
        
        # Wait for command to complete
        while self._read_reg(_Sn_CR, socket_bsb, 1)[0] != 0:
            time.sleep_ms(1)
    
    def socket_send(self, socket_num, data):
        """Send data through socket"""
        if isinstance(data, str):
            data = data.encode('utf-8')
            
        socket_bsb = 0x01 + (socket_num * 4)
        tx_buf_bsb = 0x02 + (socket_num * 4)
        
        # Get current TX write pointer
        tx_wr_bytes = self._read_reg(_Sn_TX_WR, socket_bsb, 2)
        tx_wr = struct.unpack('>H', tx_wr_bytes)[0]
        
        # Write data to TX buffer
        for i, byte in enumerate(data):
            addr = (tx_wr + i) & 0xFFFF
            self._write_reg(addr, tx_buf_bsb, byte)
        
        # Update TX write pointer
        new_tx_wr = (tx_wr + len(data)) & 0xFFFF
        self._write_reg(_Sn_TX_WR, socket_bsb, struct.pack('>H', new_tx_wr))
        
        # Send command
        self._write_reg(_Sn_CR, socket_bsb, _CMD_SEND)
        
        # Wait for command to complete
        while self._read_reg(_Sn_CR, socket_bsb, 1)[0] != 0:
            time.sleep_ms(1)
    
    def socket_recv(self, socket_num, max_length=1024):
        """Receive data from socket"""
        socket_bsb = 0x01 + (socket_num * 4)
        rx_buf_bsb = 0x03 + (socket_num * 4)
        
        # Check received data size
        rx_rsr_bytes = self._read_reg(_Sn_RX_RSR, socket_bsb, 2)
        rx_rsr = struct.unpack('>H', rx_rsr_bytes)[0]
        
        if rx_rsr == 0:
            return b''
        
        # Limit to max_length
        read_size = min(rx_rsr, max_length)
        
        # Get current RX read pointer
        rx_rd_bytes = self._read_reg(_Sn_RX_RD, socket_bsb, 2)
        rx_rd = struct.unpack('>H', rx_rd_bytes)[0]
        
        # Read data from RX buffer
        data = bytearray()
        for i in range(read_size):
            addr = (rx_rd + i) & 0xFFFF
            byte = self._read_reg(addr, rx_buf_bsb, 1)[0]
            data.append(byte)
        
        # Update RX read pointer
        new_rx_rd = (rx_rd + read_size) & 0xFFFF
        self._write_reg(_Sn_RX_RD, socket_bsb, struct.pack('>H', new_rx_rd))
        
        # RECV command to update pointers
        self._write_reg(_Sn_CR, socket_bsb, _CMD_RECV)
        
        # Wait for command to complete
        while self._read_reg(_Sn_CR, socket_bsb, 1)[0] != 0:
            time.sleep_ms(1)
        
        return bytes(data)


class W5500ModbusTCP:
    """Simple Modbus TCP client using W5500"""
    
    def __init__(self, w5500):
        self.w5500 = w5500
        self.socket = 0
        self.connected = False
    
    def connect(self, server_ip, server_port=502):
        """Connect to Modbus TCP server"""
        # Open TCP socket
        status = self.w5500.socket_open(self.socket, _Sn_MR_TCP, 12345)
        if status != _SOCK_INIT:
            raise RuntimeError(f"Failed to open socket, status: 0x{status:02x}")
        
        # Connect to server
        self.w5500.socket_connect(self.socket, server_ip, server_port)
        
        # Wait for connection
        timeout = 50  # 5 second timeout
        while timeout > 0:
            status = self.w5500.socket_status(self.socket)
            if status == _SOCK_ESTABLISHED:
                self.connected = True
                return True
            elif status == _SOCK_CLOSED:
                raise RuntimeError("Connection failed")
            time.sleep_ms(100)
            timeout -= 1
        
        raise RuntimeError("Connection timeout")
    
    def disconnect(self):
        """Disconnect from Modbus server"""
        if self.connected:
            self.w5500.socket_close(self.socket)
            self.connected = False
    
    def read_holding_registers(self, slave_id, start_addr, count):
        """Read holding registers (function code 3)"""
        if not self.connected:
            raise RuntimeError("Not connected")
        
        # Build Modbus TCP frame
        transaction_id = 1
        protocol_id = 0
        length = 6
        
        # MBAP Header
        mbap = struct.pack('>HHHB', transaction_id, protocol_id, length, slave_id)
        
        # PDU
        pdu = struct.pack('>BHH', 3, start_addr, count)  # Function 3, start, count
        
        # Send request
        frame = mbap + pdu
        self.w5500.socket_send(self.socket, frame)
        
        # Wait for response
        timeout = 50  # 5 second timeout
        while timeout > 0:
            response = self.w5500.socket_recv(self.socket, 256)
            if len(response) > 0:
                # Parse response
                if len(response) >= 9:  # Minimum response length
                    resp_trans_id, resp_proto_id, resp_length, resp_slave_id, resp_func = struct.unpack('>HHHBB', response[:8])
                    if resp_func == 3:  # Read holding registers response
                        byte_count = response[8]
                        if len(response) >= 9 + byte_count:
                            data = response[9:9+byte_count]
                            # Convert to 16-bit registers
                            registers = []
                            for i in range(0, len(data), 2):
                                registers.append(struct.unpack('>H', data[i:i+2])[0])
                            return registers
                return None
            time.sleep_ms(100)
            timeout -= 1
        
        raise RuntimeError("Read timeout")