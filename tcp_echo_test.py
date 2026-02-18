#!/usr/bin/env python3
"""
TCP Echo Test over PPP interface
Sends 1KB packets to echo server and receives them back
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

def bind_to_interface(sock, interface):
    """Bind socket to specific network interface"""
    SO_BINDTODEVICE = 25
    sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, 
                    interface.encode('utf-8'))

def create_packet(seq_num, size=PACKET_SIZE):
    """Create identifiable packet with sequence number"""
    # Header: [SEQ_NUM (4 bytes)][TIMESTAMP (8 bytes)][PATTERN]
    header = struct.pack('!IQ', seq_num, int(time.time() * 1000000))
    pattern = b'ABCDEFGHIJKLMNOP' * ((size - len(header)) // 16)
    padding = b'X' * ((size - len(header)) % 16)
    return header + pattern + padding

def main():
    if len(sys.argv) >= 2:
        global SERVER_HOST
        SERVER_HOST = sys.argv[1]
    if len(sys.argv) >= 3:
        global SERVER_PORT
        SERVER_PORT = int(sys.argv[2])
    
    print(f"TCP Echo Test via {INTERFACE}")
    print(f"Server: {SERVER_HOST}:{SERVER_PORT}")
    print(f"Packets: {NUM_PACKETS} x {PACKET_SIZE} bytes\n")
    
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
                    packet = create_packet(seq, PACKET_SIZE)
                    sock.sendall(packet)
                    
                    with stats_lock:
                        stats['bytes_sent'] += len(packet)
                        stats['packets_sent'] = seq
                        
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
        print(f"Test Complete!")
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
        
    except PermissionError:
        print("ERROR: Need root/sudo to bind to network interface")
        print("Run with: sudo python3 tcp_echo_test.py")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1
    finally:
        sock.close()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
