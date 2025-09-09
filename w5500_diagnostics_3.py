"""
Simple W5500 Reset Test - Works in Thonny
Copy this code and run it directly in Thonny
"""

import time
from w5500_driver import W5500

# Network configuration
IP_ADDR = "192.168.15.28"
SUBNET_MASK = "255.255.255.0"
GATEWAY = "192.168.15.1"
MAC_ADDR = "02:08:DC:15:00:28"

def full_w5500_reset(w):
    """Complete W5500 reset sequence"""
    print("Performing full W5500 reset...")
    
    # 1. Hardware reset
    w.rst.value(0)
    time.sleep_ms(1)
    w.rst.value(1)
    time.sleep_ms(10)
    
    # 2. Software reset via Mode Register (MR)
    w._write_reg(0x0000, 0x00, 0x80)  # Set RST bit in MR
    time.sleep_ms(10)
    
    # 3. PHY reset via PHYCFGR
    phycfgr = w._read_reg(0x002E, 0x00, 1)[0]  # Read PHYCFGR
    w._write_reg(0x002E, 0x00, phycfgr & 0x7F)  # Clear RST bit
    time.sleep_ms(10)
    w._write_reg(0x002E, 0x00, phycfgr | 0x80)  # Set RST bit
    time.sleep_ms(50)
    
    # 4. Close all sockets
    for sock in range(8):
        try:
            w.socket_close(sock)
        except:
            pass
    
    time.sleep_ms(50)
    print("Reset complete!")

def configure_network(w):
    """Configure W5500 network settings"""
    print("Configuring network...")
    w.set_mac_address(MAC_ADDR)
    w.set_ip_address(IP_ADDR)
    w.set_subnet_mask(SUBNET_MASK)
    w.set_gateway(GATEWAY)
    time.sleep_ms(100)
    print("Network configured")

def check_configuration(w):
    """Verify network configuration"""
    print("\nNetwork Status:")
    print(f"MAC: {w.get_mac_address()}")
    print(f"IP:  {w.get_ip_address()}")
    
    # Check PHY
    phy = w.get_phy_status()
    print(f"Link: {'UP' if phy['link'] else 'DOWN'}")
    print(f"Speed: {'100M' if phy['speed_100m'] else '10M'}")

def test_ping(w, target_ip, port=80):
    """Simple ping test using TCP connect"""
    print(f"\nTesting connection to {target_ip}:{port}...")
    
    try:
        # Open socket
        status = w.socket_open(0, 0x01, 50000)  # TCP socket
        if status != 0x13:  # SOCK_INIT
            print(f"Socket open failed: 0x{status:02x}")
            return False
        
        # Connect
        w.socket_connect(0, target_ip, port)
        
        # Wait for connection
        for i in range(30):  # 3 second timeout
            status = w.socket_status(0)
            if status == 0x17:  # SOCK_ESTABLISHED
                print("Connection successful!")
                w.socket_close(0)
                return True
            elif status == 0x00:  # SOCK_CLOSED
                print("Connection refused/failed")
                break
            time.sleep_ms(100)
        
        print("Connection timeout")
        w.socket_close(0)
        return False
        
    except Exception as e:
        print(f"Error: {e}")
        try:
            w.socket_close(0)
        except:
            pass
        return False

def main():
    print("W5500 Reset & Reconnection Test")
    print("=" * 40)
    
    # Initialize W5500
    try:
        w = W5500(sck_pin=10, mosi_pin=11, miso_pin=12, cs_pin=13, rst_pin=15)
        print("W5500 initialized")
    except Exception as e:
        print(f"Initialization failed: {e}")
        return
    
    # Perform full reset
    full_w5500_reset(w)
    
    # Configure network
    configure_network(w)
    
    # Check configuration
    check_configuration(w)
    
    # Wait for PHY link
    print("\nWaiting for PHY link...")
    for i in range(50):  # 5 second timeout
        phy = w.get_phy_status()
        if phy['link']:
            print("PHY link is UP")
            break
        time.sleep_ms(100)
    else:
        print("PHY link timeout - check cable")
        return
    
    # Test gateway connection
    print("\n" + "=" * 40)
    print("CONNECTIVITY TESTS")
    print("=" * 40)
    
    gateway_ok = test_ping(w, GATEWAY, 80)
    if not gateway_ok:
        gateway_ok = test_ping(w, GATEWAY, 53)  # Try DNS port
    
    # Test Google
    google_ok = test_ping(w, "8.8.8.8", 53)  # Google DNS
    
    # Results
    print("\n" + "=" * 40)
    print("RESULTS")
    print("=" * 40)
    print(f"Gateway ({GATEWAY}): {'OK' if gateway_ok else 'FAIL'}")
    print(f"Google DNS (8.8.8.8): {'OK' if google_ok else 'FAIL'}")
    
    if gateway_ok and google_ok:
        print("\n✓ All tests passed - W5500 is working!")
    elif gateway_ok:
        print("\n⚠ Gateway OK, internet may be blocked")
    else:
        print("\n✗ Gateway unreachable - check network")

def test_reconnection():
    """Test reconnection after simulated disconnect"""
    print("\nRECONNECTION TEST")
    print("=" * 40)
    print("This simulates cable disconnect/reconnect")
    
    try:
        w = W5500(sck_pin=10, mosi_pin=11, miso_pin=12, cs_pin=13, rst_pin=15)
        
        # Initial setup
        full_w5500_reset(w)
        configure_network(w)
        
        print("1. Testing initial connection...")
        initial_ok = test_ping(w, GATEWAY, 80)
        print(f"   Initial: {'OK' if initial_ok else 'FAIL'}")
        
        print("2. Simulating disconnect (full reset)...")
        full_w5500_reset(w)
        configure_network(w)
        
        # Wait for link
        print("3. Waiting for PHY link recovery...")
        link_recovered = False
        for i in range(50):
            phy = w.get_phy_status()
            if phy['link']:
                link_recovered = True
                break
            time.sleep_ms(100)
        
        print(f"   PHY Link: {'RECOVERED' if link_recovered else 'FAILED'}")
        
        if link_recovered:
            print("4. Testing reconnection...")
            reconnect_ok = test_ping(w, GATEWAY, 80)
            print(f"   Reconnect: {'OK' if reconnect_ok else 'FAIL'}")
            
            if reconnect_ok:
                print("\n✓ Reconnection test PASSED!")
            else:
                print("\n✗ Reconnection test FAILED")
        else:
            print("\n✗ PHY link failed to recover")
            
    except Exception as e:
        print(f"Test error: {e}")

# Run the test
if __name__ == "__main__":
    main()
    
    # Ask user if they want to test reconnection
    print("\n" + "=" * 40)
    print("To test reconnection:")
    print("  test_reconnection()")