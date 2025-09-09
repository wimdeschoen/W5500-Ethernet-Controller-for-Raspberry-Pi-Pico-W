"""
Detailed W5500 Socket Debug Script
Focuses on socket state debugging and proper initialization
"""

import time
from w5500_driver import W5500

# Network configuration
IP_ADDR = "192.168.15.28"
SUBNET_MASK = "255.255.255.0"
GATEWAY = "192.168.15.1"
MAC_ADDR = "02:08:dc:15:00:28"

def print_socket_details(w, sock_num):
    """Print detailed socket information for debugging"""
    try:
        socket_bsb = 0x01 + (sock_num * 4)
        
        # Read socket registers
        mode = w._read_reg(0x0000, socket_bsb, 1)[0]  # Sn_MR
        cmd = w._read_reg(0x0001, socket_bsb, 1)[0]   # Sn_CR
        status = w._read_reg(0x0003, socket_bsb, 1)[0] # Sn_SR
        port_bytes = w._read_reg(0x0004, socket_bsb, 2) # Sn_PORT
        port = (port_bytes[0] << 8) | port_bytes[1]
        
        print(f"Socket {sock_num}:")
        print(f"  Mode: 0x{mode:02x}, Cmd: 0x{cmd:02x}, Status: 0x{status:02x}")
        print(f"  Port: {port}")
        
        if status != 0x00:  # Not closed
            # Read destination info if available
            dest_ip = w._read_reg(0x000C, socket_bsb, 4)  # Sn_DIPR
            dest_port_bytes = w._read_reg(0x0010, socket_bsb, 2)  # Sn_DPORT
            dest_port = (dest_port_bytes[0] << 8) | dest_port_bytes[1]
            print(f"  Dest: {'.'.join(map(str, dest_ip))}:{dest_port}")
            
    except Exception as e:
        print(f"Socket {sock_num}: Error reading - {e}")

def comprehensive_reset(w):
    """More comprehensive reset with verification"""
    print("Starting comprehensive reset...")
    
    # 1. Close all sockets first
    print("1. Closing all sockets...")
    for sock in range(8):
        try:
            socket_bsb = 0x01 + (sock * 4)
            w._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE command
            time.sleep_ms(5)
            # Wait for close to complete
            for _ in range(10):
                status = w._read_reg(0x0003, socket_bsb, 1)[0]
                if status == 0x00:  # SOCK_CLOSED
                    break
                time.sleep_ms(5)
        except:
            pass
    
    # 2. Hardware reset
    print("2. Hardware reset...")
    w.rst.value(0)
    time.sleep_ms(5)  # Longer reset pulse
    w.rst.value(1)
    time.sleep_ms(50)  # Longer stabilization
    
    # 3. Software reset
    print("3. Software reset...")
    w._write_reg(0x0000, 0x00, 0x80)  # Set RST bit in MR
    time.sleep_ms(50)
    
    # 4. Verify reset completed
    print("4. Verifying reset...")
    for attempt in range(10):
        try:
            version = w._read_reg(0x0039, 0x00, 1)[0]  # VERSIONR
            if version == 0x04:
                print("   Reset verified - chip responding")
                break
        except:
            pass
        time.sleep_ms(10)
    else:
        print("   WARNING: Reset verification failed")
        return False
    
    # 5. Reset PHY
    print("5. PHY reset...")
    try:
        # Read current PHYCFGR
        phycfgr = w._read_reg(0x002E, 0x00, 1)[0]
        print(f"   Current PHYCFGR: 0x{phycfgr:02x}")
        
        # Reset PHY (clear bit 7, then set it)
        w._write_reg(0x002E, 0x00, phycfgr & 0x7F)
        time.sleep_ms(10)
        w._write_reg(0x002E, 0x00, phycfgr | 0x80)
        time.sleep_ms(100)
        
        # Read back
        phycfgr_new = w._read_reg(0x002E, 0x00, 1)[0]
        print(f"   New PHYCFGR: 0x{phycfgr_new:02x}")
        
    except Exception as e:
        print(f"   PHY reset error: {e}")
    
    # 6. Clear any pending interrupts
    print("6. Clearing interrupts...")
    try:
        w._write_reg(0x0015, 0x00, 0xFF)  # Clear IR
        w._write_reg(0x0017, 0x00, 0x00)  # Clear SIR
    except:
        pass
    
    print("Reset sequence complete")
    return True

def configure_network_detailed(w):
    """Configure network with detailed verification"""
    print("Configuring network settings...")
    
    # Set MAC
    w.set_mac_address(MAC_ADDR)
    time.sleep_ms(10)
    mac_verify = w.get_mac_address()
    print(f"MAC: Set {MAC_ADDR} -> Read {mac_verify}")
    
    # Set IP
    w.set_ip_address(IP_ADDR)
    time.sleep_ms(10)
    ip_verify = w.get_ip_address()
    print(f"IP:  Set {IP_ADDR} -> Read {ip_verify}")
    
    # Set Subnet
    w.set_subnet_mask(SUBNET_MASK)
    time.sleep_ms(10)
    subnet_bytes = w._read_reg(0x0005, 0x00, 4)
    subnet_verify = '.'.join(map(str, subnet_bytes))
    print(f"Subnet: Set {SUBNET_MASK} -> Read {subnet_verify}")
    
    # Set Gateway
    w.set_gateway(GATEWAY)
    time.sleep_ms(10)
    gw_bytes = w._read_reg(0x0001, 0x00, 4)
    gw_verify = '.'.join(map(str, gw_bytes))
    print(f"Gateway: Set {GATEWAY} -> Read {gw_verify}")
    
    # Verify all settings match
    config_ok = (mac_verify.lower() == MAC_ADDR.lower() and 
                ip_verify == IP_ADDR and 
                subnet_verify == SUBNET_MASK and 
                gw_verify == GATEWAY)
    
    print(f"Configuration: {'OK' if config_ok else 'MISMATCH'}")
    return config_ok

def wait_for_phy_link(w, timeout_ms=10000):
    """Wait for PHY link with detailed status"""
    print("Waiting for PHY link...")
    
    start_time = time.ticks_ms()
    link_attempts = 0
    
    while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
        try:
            phy = w.get_phy_status()
            link_attempts += 1
            
            if phy['link']:
                print(f"PHY Link UP after {link_attempts} attempts")
                print(f"  Speed: {'100M' if phy['speed_100m'] else '10M'}")
                print(f"  Duplex: {'Full' if phy['full_duplex'] else 'Half'}")
                print(f"  Raw: 0x{phy['raw_value']:02x}")
                return True
                
            if link_attempts % 20 == 0:  # Print status every 2 seconds
                print(f"  Attempt {link_attempts}: Link DOWN (raw: 0x{phy['raw_value']:02x})")
                
        except Exception as e:
            print(f"  PHY read error: {e}")
            
        time.sleep_ms(100)
    
    print(f"PHY link timeout after {link_attempts} attempts")
    return False

def detailed_tcp_connect(w, sock_num, dest_ip, dest_port, timeout_ms=5000):
    """TCP connect with detailed socket state monitoring"""
    print(f"Detailed TCP connect to {dest_ip}:{dest_port} using socket {sock_num}")
    
    socket_bsb = 0x01 + (sock_num * 4)
    
    try:
        # 1. Ensure socket is closed
        print("1. Ensuring socket is closed...")
        w._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE command
        time.sleep_ms(10)
        
        # Wait for close
        for i in range(10):
            status = w._read_reg(0x0003, socket_bsb, 1)[0]
            if status == 0x00:  # SOCK_CLOSED
                break
            time.sleep_ms(5)
        else:
            print("   WARNING: Socket didn't close properly")
        
        print_socket_details(w, sock_num)
        
        # 2. Open socket
        print("2. Opening TCP socket...")
        w._write_reg(0x0000, socket_bsb, 0x01)  # TCP mode
        w._write_reg(0x0004, socket_bsb, [(50000 + sock_num) >> 8, (50000 + sock_num) & 0xFF])  # Source port
        w._write_reg(0x0001, socket_bsb, 0x01)  # OPEN command
        
        # Wait for open to complete
        for i in range(50):  # 500ms timeout
            cmd = w._read_reg(0x0001, socket_bsb, 1)[0]
            if cmd == 0x00:  # Command completed
                break
            time.sleep_ms(10)
        
        status = w._read_reg(0x0003, socket_bsb, 1)[0]
        print(f"   Socket status after open: 0x{status:02x}")
        
        if status != 0x13:  # Not SOCK_INIT
            print(f"   ERROR: Expected SOCK_INIT (0x13), got 0x{status:02x}")
            return False
        
        print_socket_details(w, sock_num)
        
        # 3. Set destination
        print("3. Setting destination...")
        dest_bytes = [int(x) for x in dest_ip.split('.')]
        w._write_reg(0x000C, socket_bsb, dest_bytes)  # Destination IP
        w._write_reg(0x0010, socket_bsb, [dest_port >> 8, dest_port & 0xFF])  # Destination port
        
        # 4. Connect
        print("4. Initiating connection...")
        w._write_reg(0x0001, socket_bsb, 0x04)  # CONNECT command
        
        # 5. Wait for connection
        print("5. Waiting for connection...")
        start_time = time.ticks_ms()
        
        while time.ticks_diff(time.ticks_ms(), start_time) < timeout_ms:
            # Check if command completed
            cmd = w._read_reg(0x0001, socket_bsb, 1)[0]
            status = w._read_reg(0x0003, socket_bsb, 1)[0]
            
            print(f"   Status: 0x{status:02x}, Cmd: 0x{cmd:02x}")
            
            if status == 0x17:  # SOCK_ESTABLISHED
                print("   SUCCESS: Connection established!")
                return True
            elif status == 0x00:  # SOCK_CLOSED
                print("   FAILED: Socket closed (connection refused/reset)")
                break
            elif status == 0x13 and cmd == 0x00:  # Still in INIT but command done
                print("   FAILED: Connect command completed but no connection")
                break
                
            time.sleep_ms(100)
        
        print("   TIMEOUT: Connection attempt timed out")
        return False
        
    except Exception as e:
        print(f"   EXCEPTION: {e}")
        return False
    finally:
        # Always try to close socket
        try:
            w._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE command
        except:
            pass

def main_debug():
    print("W5500 Detailed Socket Debug")
    print("=" * 50)
    
    # Initialize
    try:
        w = W5500(sck_pin=10, mosi_pin=11, miso_pin=12, cs_pin=13, rst_pin=15)
        print("W5500 driver initialized")
    except Exception as e:
        print(f"Driver init failed: {e}")
        return
    
    # Check initial socket states
    print("\nInitial socket states:")
    for i in range(8):
        print_socket_details(w, i)
    
    # Comprehensive reset
    if not comprehensive_reset(w):
        print("Reset failed - aborting")
        return
    
    # Configure network
    if not configure_network_detailed(w):
        print("Network configuration failed")
        return
    
    # Wait for PHY
    if not wait_for_phy_link(w):
        print("PHY link failed - check cable")
        return
    
    # Check socket states after reset/config
    print("\nSocket states after reset/config:")
    for i in range(8):
        print_socket_details(w, i)
    
    # Test connections with detailed monitoring
    print("\n" + "=" * 50)
    print("DETAILED CONNECTION TESTS")
    print("=" * 50)
    
    # Test gateway
    gateway_ok = detailed_tcp_connect(w, 0, GATEWAY, 80)
    time.sleep_ms(500)
    
    if not gateway_ok:
        print("\nTrying gateway on port 53...")
        gateway_ok = detailed_tcp_connect(w, 1, GATEWAY, 53)
        time.sleep_ms(500)
    
    # Test Google DNS
    print(f"\nTesting Google DNS...")
    google_ok = detailed_tcp_connect(w, 2, "8.8.8.8", 53)
    
    # Results
    print("\n" + "=" * 50)
    print("FINAL RESULTS")
    print("=" * 50)
    print(f"Gateway: {'OK' if gateway_ok else 'FAIL'}")
    print(f"Google:  {'OK' if google_ok else 'FAIL'}")

if __name__ == "__main__":
    main_debug()