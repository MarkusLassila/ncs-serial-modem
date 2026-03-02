#!/usr/bin/env python3
"""
TCP Echo Test over PPP interface
Sends 1KB packets to echo server and receives them back

Default test range: 150ms to 80ms delay (most important range)
For full range testing (200ms to 0ms), use: --start 200 --min 0
"""

import socket
import time
import struct
import sys
import threading
from collections import defaultdict

# Configuration
SERVER_HOST = "dev2.testncs.com"  # Replace with your server
SERVER_PORT = 20180               # Replace with your port
INTERFACE = "ppp0"
PACKET_SIZE = 1024
NUM_PACKETS = 200
SEND_DELAY_MS = 10               # Delay between packets in milliseconds

def bind_to_interface(sock, interface):
    """Bind socket to specific network interface"""
    SO_BINDTODEVICE = 25
    sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, 
                    interface.encode('utf-8'))

def create_packet(seq_num, size=PACKET_SIZE, delay_ms=None):
    """Create identifiable packet with sequence number"""
    # Header: [SEQ_NUM (4 bytes)][TIMESTAMP (8 bytes)][DELAY_MS (4 bytes if seq==1)][PATTERN]
    header = struct.pack('!IQ', seq_num, int(time.time() * 1000000))
    
    # First packet includes delay_ms for identification in pcap
    if seq_num == 1 and delay_ms is not None:
        header += struct.pack('!I', delay_ms)
        marker = f"DELAY={delay_ms}ms ".encode('utf-8')
        header += marker
    
    pattern = b'ABCDEFGHIJKLMNOP' * ((size - len(header)) // 16)
    padding = b'X' * ((size - len(header)) % 16)
    return header + pattern + padding

def run_single_test(delay_ms):
    """Run a single test iteration with specified delay"""
    print(f"\n{'='*60}")
    print(f"Starting test with {delay_ms}ms delay")
    print(f"{'='*60}\n")
    
    # Create TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        # Bind to ppp0 interface
        bind_to_interface(sock, INTERFACE)
        print(f"Bound to {INTERFACE}")
        
        # Connect to echo server
        print(f"Connecting to {SERVER_HOST}:{SERVER_PORT}...")
        sock.connect((SERVER_HOST, SERVER_PORT))
        print("Connected!\n")
        
        # Shared state between threads
        stats = {
            'bytes_sent': 0,
            'bytes_received': 0,
            'packets_sent': 0,
            'packets_received': 0,
            'errors': 0,
            'running': True
        }
        stats_lock = threading.Lock()
        received_packets = {}  # seq -> (data, timestamp)
        received_lock = threading.Lock()
        
        start_time = time.time()
        
        def sender_thread():
            """Send packets continuously"""
            for seq in range(1, NUM_PACKETS + 1):
                if not stats['running']:
                    break
                try:
                    packet = create_packet(seq, PACKET_SIZE, delay_ms)
                    sock.sendall(packet)
                    
                    with stats_lock:
                        stats['bytes_sent'] += len(packet)
                        stats['packets_sent'] = seq
                    
                    # Delay before sending next packet
                    if seq < NUM_PACKETS:  # Don't delay after last packet
                        time.sleep(delay_ms / 1000.0)
                        
                except Exception as e:
                    print(f"Send error on packet {seq}: {e}")
                    with stats_lock:
                        stats['errors'] += 1
                        stats['running'] = False
                    break
            
            # Signal that sending is done
            with stats_lock:
                if stats['packets_sent'] == NUM_PACKETS:
                    print(f"\nAll {NUM_PACKETS} packets sent. Waiting for echoes...")
                    stats['running'] = False  # Signal completion
        
        def receiver_thread():
            """Receive packets continuously"""
            buffer = b''
            packets_received = 0
            
            while stats['running'] or packets_received < stats['packets_sent']:
                try:
                    # Check if we've received all packets
                    if packets_received >= stats['packets_sent'] and stats['packets_sent'] >= NUM_PACKETS:
                        break
                    
                    # Receive data
                    chunk = sock.recv(4096)
                    if not chunk:
                        print("Connection closed by server")
                        with stats_lock:
                            stats['running'] = False
                        break
                    
                    buffer += chunk
                    
                    # Process complete packets from buffer
                    while len(buffer) >= PACKET_SIZE:
                        packet = buffer[:PACKET_SIZE]
                        buffer = buffer[PACKET_SIZE:]
                        
                        # Parse packet
                        recv_seq = struct.unpack('!I', packet[:4])[0]
                        recv_timestamp = struct.unpack('!Q', packet[4:12])[0]
                        
                        packets_received += 1
                        
                        with stats_lock:
                            stats['bytes_received'] += len(packet)
                            stats['packets_received'] = packets_received
                        
                        with received_lock:
                            received_packets[recv_seq] = (packet, time.time())
                        
                except socket.timeout:
                    # Check if we should exit on timeout
                    if packets_received >= stats['packets_sent'] and not stats['running']:
                        break
                    continue
                except Exception as e:
                    print(f"Receive error: {e}")
                    with stats_lock:
                        stats['errors'] += 1
                        stats['running'] = False
                    break
        
        def progress_thread():
            """Display progress updates"""
            last_sent = 0
            last_received = 0
            last_time = start_time
            
            while True:
                time.sleep(1)
                
                with stats_lock:
                    sent = stats['packets_sent']
                    received = stats['packets_received']
                    bytes_sent = stats['bytes_sent']
                    bytes_received = stats['bytes_received']
                    errors = stats['errors']
                    running = stats['running']
                
                # Exit if all packets sent and received
                if not running and received >= sent and sent >= NUM_PACKETS:
                    break
                
                now = time.time()
                elapsed = now - last_time
                
                if elapsed > 0:
                    tx_rate = (sent - last_sent) / elapsed
                    rx_rate = (received - last_received) / elapsed
                    
                    print(f"TX: {sent}/{NUM_PACKETS} ({tx_rate:.1f} pkt/s) | "
                          f"RX: {received}/{NUM_PACKETS} ({rx_rate:.1f} pkt/s) | "
                          f"Errors: {errors}")
                    
                    last_sent = sent
                    last_received = received
                    last_time = now
        
        # Set socket timeout for receiver
        sock.settimeout(5.0)
        
        # Start threads
        sender = threading.Thread(target=sender_thread, name="Sender")
        receiver = threading.Thread(target=receiver_thread, name="Receiver")
        progress = threading.Thread(target=progress_thread, name="Progress")
        
        sender.start()
        receiver.start()
        progress.start()
        
        # Wait for completion
        sender.join()
        receiver.join()
        progress.join()
        
        # Final statistics
        elapsed = time.time() - start_time
        
        with stats_lock:
            packets_sent = stats['packets_sent']
            packets_received = stats['packets_received']
            bytes_sent = stats['bytes_sent']
            bytes_received = stats['bytes_received']
            errors = stats['errors']
        
        # Check for missing/out-of-order packets
        with received_lock:
            missing = set(range(1, packets_sent + 1)) - set(received_packets.keys())
            if missing:
                print(f"\nWARNING: Missing packets: {sorted(missing)[:10]}{'...' if len(missing) > 10 else ''}")
        
        print(f"\n{'='*60}")
        print(f"Test Complete! (Delay: {delay_ms}ms)")
        print(f"{'='*60}")
        print(f"Packets sent:     {packets_sent}/{NUM_PACKETS}")
        print(f"Packets received: {packets_received}/{NUM_PACKETS}")
        print(f"Bytes sent:       {bytes_sent:,} ({bytes_sent/1024/1024:.2f} MB)")
        print(f"Bytes received:   {bytes_received:,} ({bytes_received/1024/1024:.2f} MB)")
        print(f"Total bytes:      {(bytes_sent + bytes_received):,} "
              f"({(bytes_sent + bytes_received)/1024/1024:.2f} MB)")
        print(f"Duration:         {elapsed:.2f} seconds")
        print(f"Throughput (TX):  {bytes_sent / elapsed / 1024:.1f} KB/s")
        print(f"Throughput (RX):  {bytes_received / elapsed / 1024:.1f} KB/s")
        print(f"Packet loss:      {(packets_sent - packets_received) / packets_sent * 100:.2f}%")
        print(f"Errors:           {errors}")
        
        return {
            'delay_ms': delay_ms,
            'packets_sent': packets_sent,
            'packets_received': packets_received,
            'bytes_sent': bytes_sent,
            'bytes_received': bytes_received,
            'duration': elapsed,
            'errors': errors,
            'packet_loss_pct': (packets_sent - packets_received) / packets_sent * 100 if packets_sent > 0 else 0
        }
        
    except PermissionError:
        print("ERROR: Need root/sudo to bind to network interface")
        print("Run with: sudo python3 tcp_echo_test.py")
        return None
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        sock.close()


def main():
    """Main function - runs tests with decreasing delays"""
    global SERVER_HOST, SERVER_PORT
    
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(
        description='TCP Echo Test over PPP interface',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run focused test (150ms to 80ms, default)
  %(prog)s
  
  # Run full range test (200ms to 0ms)
  %(prog)s --start 200 --min 0
  
  # Custom server and port
  %(prog)s --server dev2.testncs.com --port 20180
  
  # Custom delay range
  %(prog)s --start 100 --min 50 --step 5
        """
    )
    
    parser.add_argument('--server', type=str, default=SERVER_HOST,
                       help=f'Echo server hostname/IP (default: {SERVER_HOST})')
    parser.add_argument('--port', type=int, default=SERVER_PORT,
                       help=f'Echo server port (default: {SERVER_PORT})')
    parser.add_argument('--start', type=int, default=150,
                       help='Starting delay in ms (default: 150)')
    parser.add_argument('--min', type=int, default=80,
                       help='Minimum delay in ms (default: 80)')
    parser.add_argument('--step', type=int, default=10,
                       help='Delay step in ms (default: 10)')
    parser.add_argument('--pause', type=int, default=3,
                       help='Pause between tests in seconds (default: 3)')
    
    args = parser.parse_args()
    
    # Apply settings
    SERVER_HOST = args.server
    SERVER_PORT = args.port
    
    # Test parameters - focused on most important range (150ms to 80ms)
    start_delay = args.start
    delay_step = args.step
    min_delay = args.min
    pause_between_tests = args.pause
    
    print(f"{'='*80}")
    print(f"TCP Echo Test Suite via {INTERFACE}")
    print(f"{'='*80}")
    print(f"Server: {SERVER_HOST}:{SERVER_PORT}")
    print(f"Packets per test: {NUM_PACKETS} x {PACKET_SIZE} bytes")
    print(f"Delay range: {start_delay}ms -> {min_delay}ms (step: {delay_step}ms)")
    print(f"Pause between tests: {pause_between_tests}s")
    print(f"{'='*80}\n")
    
    # Run tests with decreasing delays
    results = []
    current_delay = start_delay
    
    while current_delay >= min_delay:
        result = run_single_test(current_delay)
        
        if result:
            results.append(result)
        else:
            print(f"\nTest with {current_delay}ms delay failed!")
            if current_delay == start_delay:
                # First test failed, likely a configuration issue
                return 1
        
        # Move to next delay
        current_delay -= delay_step
        
        # Pause between tests (except after the last one)
        if current_delay >= min_delay:
            print(f"\nWaiting {pause_between_tests}s before next test...\n")
            time.sleep(pause_between_tests)
    
    # Print summary of all tests
    print(f"\n{'='*80}")
    print(f"ALL TESTS COMPLETE - SUMMARY")
    print(f"{'='*80}")
    print(f"{'Delay (ms)':<12} {'Packets Sent':<14} {'Packets Rcvd':<14} {'Loss %':<10} {'Duration (s)':<14} {'Errors'}")
    print(f"{'-'*80}")
    
    for result in results:
        print(f"{result['delay_ms']:<12} "
              f"{result['packets_sent']:<14} "
              f"{result['packets_received']:<14} "
              f"{result['packet_loss_pct']:<10.2f} "
              f"{result['duration']:<14.2f} "
              f"{result['errors']}")
    
    print(f"{'='*80}")
    print(f"Total tests completed: {len(results)}/{(start_delay - min_delay) // delay_step + 1}")
    print(f"{'='*80}\n")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
