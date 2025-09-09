"""
W5500 ARP Debug and Fix Script
The issue appears to be ARP-related. This script addresses ARP table clearing and timing.
"""

import time
from w5500_driver import W5500

# Network configuration
IP_ADDR = "192.168.15.28"
SUBNET_MASK = "255.255.255.0"
GATEWAY = "192.168.15.1"
MAC_ADDR = "02:08:dc:15:00:28"

def clear_arp_and_reset(w):
    """Clear ARP table and perform targeted reset"""
    print("Clearing ARP and performing targeted reset...")
    
    # 1. Close all sockets (ARP entries might be tied to sockets)
    print("1. Force closing all sockets...")
    for sock in range(8):
        socket_bsb = 0x01 + (sock * 4)
        try:
            # Force close without waiting
            w._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE command
        except:
            pass
    time.sleep_ms(50)
    
    # 2. Reset mode register (this clears internal state)
    print("2. Mode register reset...")
    w._write_reg(0x0000, 0x00, 0x80)  # Software reset
    time.sleep_ms(100)  # Longer wait for reset
    
    # 3. Hardware reset to ensure clean state
    print("3. Hardware reset...")
    w.rst.value(0)
    time.sleep_ms(10)  # Longer reset pulse
    w.rst.value(1)
    time.sleep_ms(100)  # Longer stabilization
    
    # 4. Verify chip responds
    for attempt in range(10):
        try:
            version = w._read_reg(0x0039, 0x00, 1)[0]
            if version == 0x04:
                print("4. Reset verified")
                return True
        except:
            pass
        time.sleep_ms(10)
    
    print("4. Reset verification failed")
    return False

def configure_with_arp_settings(w):
    """Configure network with ARP-specific settings"""
    print("Configuring network with ARP optimization...")
    
    # Standard network config
    w.set_mac_address(MAC_ADDR)
    w.set_ip_address(IP_ADDR)
    w.set_subnet_mask(SUBNET_MASK)
    w.set_gateway(GATEWAY)
    
    # Set retry parameters for ARP (more aggressive)
    # RTR = Retry Time Register (default 2000 = 200ms)
    # RCR = Retry Count Register (default 8)
    
    # Increase retry time to 400ms (4000 in units of 100us)
    w._write_reg(0x0019, 0x00, [0x0F, 0xA0])  # RTR = 4000
    
    # Increase retry count to 15
    w._write_reg(0x001B, 0x00, 0x0F)  # RCR = 15
    
    print("ARP retry settings: RTR=400ms, RCR=15 attempts")
    
    # Enable Force ARP mode (forces ARP for every packet)
    mr = w._read_reg(0x0000, 0x00, 1)[0]
    w._write_reg(0x0000, 0x00, mr | 0x02)  # Set FARP bit
    print("Force ARP mode enabled")
    
    return True

def test_arp_resolution(w, target_ip):
    """Test ARP resolution by attempting UDP first"""
    print(f"Testing ARP resolution for {target_ip}...")
    
    try:
        # Use UDP socket for ARP test (simpler than TCP)
        socket_bsb = 0x01  # Socket 0
        
        # Close socket first
        w._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE
        time.sleep_ms(10)
        
        # Open UDP socket
        w._write_reg(0x0000, socket_bsb, 0x02)  # UDP mode
        w._write_reg(0x0004, socket_bsb, [0xC3, 0x50])  # Port 50000
        w._write_reg(0x0001, socket_bsb, 0x01)  # OPEN command
        
        # Wait for open
        for i in range(50):
            if w._read_reg(0x0001, socket_bsb, 1)[0] == 0x00:  # Command done
                break
            time.sleep_ms(10)
        
        status = w._read_reg(0x0003, socket_bsb, 1)[0]
        if status != 0x22:  # SOCK_UDP
            print(f"   UDP socket open failed: 0x{status:02x}")
            return False
        
        print("   UDP socket opened successfully")
        
        # Set destination for ARP resolution
        dest_bytes = [int(x) for x in target_ip.split('.')]
        w._write_reg(0x000C, socket_bsb, dest_bytes)  # Destination IP
        w._write_reg(0x0010, socket_bsb, [0x00, 0x35])  # Port 53 (DNS)
        
        # Try to send a small packet to trigger ARP
        # Write dummy data to TX buffer
        tx_buf_bsb = 0x02  # Socket 0 TX buffer
        w._write_reg(0x0000, tx_buf_bsb, [0x00, 0x00, 0x01, 0x00])  # 4 bytes dummy
        
        # Update TX write pointer
        w._write_reg(0x0024, socket_bsb, [0x00, 0x04])  # TX_WR = 4
        
        # Send command
        w._write_reg(0x0001, socket_bsb, 0x20)  # SEND command
        
        # Wait for send to complete or timeout
        arp_success = False
        for i in range(100):  # 10 second timeout for ARP
            cmd = w._read_reg(0x0001, socket_bsb, 1)[0]
            status = w._read_reg(0x0003, socket_bsb, 1)[0]
            
            if cmd == 0x00:  # Command completed
                # Check socket interrupt register for status
                sir = w._read_reg(0x0002, socket_bsb, 1)[0]
                if sir & 0x10:  # SEND_OK
                    print("   ARP resolution and send successful!")
                    arp_success = True
                    # Clear interrupt
                    w._write_reg(0x0002, socket_bsb, 0x10)
                    break
                elif sir & 0x08:  # TIMEOUT
                    print("   ARP timeout occurred")
                    # Clear interrupt
                    w._write_reg(0x0002, socket_bsb, 0x08)
                    break
            
            time.sleep_ms(100)
        
        # Close UDP socket
        w._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE
        
        return arp_success
        
    except Exception as e:
        print(f"   ARP test error: {e}")
        return False

def enhanced_tcp_connect(w, sock_num, dest_ip, dest_port, with_arp_prep=True):
    """TCP connect with ARP preparation"""
    print(f"Enhanced TCP connect to {dest_ip}:{dest_port}")
    
    socket_bsb = 0x01 + (sock_num * 4)
    
    try:
        # Optional: Pre-resolve ARP
        if with_arp_prep:
            print("  Pre-resolving ARP...")
            arp_ok = test_arp_resolution(w, dest_ip)
            if not arp_ok:
                print("  WARNING: ARP resolution failed")
            time.sleep_ms(200)  # Brief pause after ARP
        
        # Close socket
        w._write_reg(0x0001, socket_bsb, 0x10)  # CLOSE
        time.sleep_ms(20)
        
        # Open TCP socket
        w._write_reg(0x0000, socket_bsb, 0x01)  # TCP mode
        w._write_reg(0x0004, socket_bsb, [(50000 + sock_num) >> 8, (50000 + sock_num) & 0xFF])
        w._write_reg(0x0001, socket_bsb, 0x01)  # OPEN
        
        # Wait for open
        for i in range(50):
            if w._read_reg(0x0001, socket_bsb, 1)[0] == 0x00:
                break
            time.sleep_ms(10)
        
        status = w._read_reg(0x0003, socket_bsb, 1)[0]
        if status != 0x13:  # SOCK_INIT
            print(f"  Socket open failed: 0x{status:02x}")
            return False
        
        # Set destination
        dest_bytes = [int(x) for x in dest_ip.split('.')]
        w._write_reg(0x000C, socket_bsb, dest_bytes)
        w._write_reg(0x0010, socket_bsb, [dest_port >> 8, dest_port & 0xFF])
        
        # Clear any existing interrupts
        w._write_reg(0x0002, socket_bsb, 0xFF)
        
        # Connect with longer timeout
        w._write_reg(0x0001, socket_bsb, 0x04)  # CONNECT
        
        # Monitor connection with interrupt checking
        start_time = time.ticks_ms()
        while time.ticks_diff(time.ticks_ms(), start_time) < 10000:  # 10 second timeout
            cmd = w._read_reg(0x0001, socket_bsb, 1)[0]
            status = w._read_reg(0x0003, socket_bsb, 1)[0]
            sir = w._read_reg(0x0002, socket_bsb, 1)[0]  # Socket interrupt register
            
            print(f"  Status: 0x{status:02x}, Cmd: 0x{cmd:02x}, INT: 0x{sir:02x}")
            
            if status == 0x17:  # SOCK_ESTABLISHED
                print("  SUCCESS: Connection established!")
                w._write_reg(0x0001, socket_bsb, 0x10)  # Close
                return True
            elif sir & 0x08:  # TIMEOUT interrupt
                print("  FAILED: Connection timeout (ARP or TCP)")
                w._write_reg(0x0002, socket_bsb, 0x08)  # Clear timeout int
                break
            elif status == 0x00:  # SOCK_CLOSED
                print("  FAILED: Connection refused/reset")
                break
            
            time.sleep_ms(200)  # Check every 200ms
        
        print("  TIMEOUT: Overall connection timeout")
        return False
        
    except Exception as e:
        print(f"  EXCEPTION: {e}")
        return False
    finally:
        try:
            w._write_reg(0x0001, socket_bsb, 0x10)  # Always close socket
        except:
            pass

def main_arp_debug():
    print("W5500 ARP Debug and Fix")
    print("=" * 40)
    
    try:
        w = W5500(sck_pin=10, mosi_pin=11, miso_pin=12, cs_pin=13, rst_pin=15)
        print("W5500 initialized")
    except Exception as e:
        print(f"Init failed: {e}")
        return
    
    # Clear ARP and reset
    if not clear_arp_and_reset(w):
        print("Reset failed")
        return
    
    # Configure with ARP settings
    configure_with_arp_settings(w)
    
    # Wait for PHY
    print("\nWaiting for PHY link...")
    link_ok = False
    for i in range(50):
        phy = w.get_phy_status()
        if phy['link']:
            link_ok = True
            print(f"PHY Link UP: {phy}")
            break
        time.sleep_ms(100)
    
    if not link_ok:
        print("PHY link failed")
        return
    
    # Test ARP resolution first
    print("\n" + "=" * 40)
    print("ARP RESOLUTION TESTS")
    print("=" * 40)
    
    gateway_arp = test_arp_resolution(w, GATEWAY)
    print(f"Gateway ARP: {'OK' if gateway_arp else 'FAIL'}")
    
    google_arp = test_arp_resolution(w, "8.8.8.8")
    print(f"Google ARP: {'OK' if google_arp else 'FAIL'}")
    
    # TCP connection tests
    print("\n" + "=" * 40)
    print("TCP CONNECTION TESTS")
    print("=" * 40)
    
    gateway_tcp = enhanced_tcp_connect(w, 0, GATEWAY, 80, with_arp_prep=True)
    print(f"Gateway TCP: {'OK' if gateway_tcp else 'FAIL'}")
    
    if not gateway_tcp:
        # Try different port
        gateway_tcp = enhanced_tcp_connect(w, 1, GATEWAY, 53, with_arp_prep=True)
        print(f"Gateway TCP (port 53): {'OK' if gateway_tcp else 'FAIL'}")
    
    # Final results
    print("\n" + "=" * 40)
    print("RESULTS")
    print("=" * 40)
    print(f"Gateway connectivity: {'OK' if gateway_tcp else 'FAIL'}")
    
    if gateway_arp and not gateway_tcp:
        print("ARP works but TCP fails - likely firewall/port blocking")
    elif not gateway_arp:
        print("ARP resolution failed - network/routing issue")

if __name__ == "__main__":
    main_arp_debug()