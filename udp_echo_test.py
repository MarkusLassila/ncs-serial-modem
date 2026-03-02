#!/usr/bin/env python3
"""
UDP Echo Test over PPP interface
Sends small UDP packets to echo server and receives them back

Default configuration:
- Packet delay: 80ms (for consistent timing)
- Packet size: 100-150 bytes (configurable)
- Target speed: 10-14 Kbps
- Port: 21185

With 80ms delay and 125 byte packets: ~12.5 Kbps
"""

import socket
import time
import struct
import sys
import argparse
import csv
import glob
import os
from collections import defaultdict

# Configuration defaults
SERVER_HOST = "dev2.testncs.com"
SERVER_PORT = 21185
INTERFACE = "ppp0"
PACKET_SIZE = 125        # Default: ~12.5 Kbps with 80ms delay
NUM_PACKETS = 200
SEND_DELAY_MS = 80       # 80ms delay between packets
TIMEOUT_SEC = 5.0        # Socket timeout for receiving

def bind_to_interface(sock, interface):
    """Bind socket to specific network interface"""
    SO_BINDTODEVICE = 25
    sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, 
                    interface.encode('utf-8'))

def create_packet(seq_num, size=PACKET_SIZE, delay_ms=None):
    """Create identifiable UDP packet with sequence number"""
    # Header: [SEQ_NUM (4 bytes)][TIMESTAMP (8 bytes)][DELAY_MS (4 bytes if seq==1)]
    header = struct.pack('!IQ', seq_num, int(time.time() * 1000000))
    
    # First packet includes delay_ms for identification in pcap
    if seq_num == 1 and delay_ms is not None:
        header += struct.pack('!I', delay_ms)
        marker = f"DELAY={delay_ms}ms ".encode('utf-8')
        header += marker
    
    # Fill rest with pattern
    remaining = size - len(header)
    if remaining > 0:
        pattern = b'ABCDEFGHIJKLMNOP' * (remaining // 16)
        padding = b'X' * (remaining % 16)
        return header + pattern + padding
    else:
        return header[:size]  # Truncate if header too long

def run_test(delay_ms, packet_size, num_packets, server_host, server_port, test_label=None):
    """Run UDP echo test with specified parameters"""
    print(f"\n{'='*60}")
    if test_label:
        print(f"{test_label}")
        print(f"{'='*60}")
    print(f"UDP Echo Test Configuration:")
    print(f"  Packet size: {packet_size} bytes")
    print(f"  Delay: {delay_ms}ms")
    print(f"  Number of packets: {num_packets}")
    print(f"  Target speed: ~{(packet_size * 8 * 1000 / delay_ms):.1f} bps")
    print(f"  Server: {server_host}:{server_port}")
    print(f"{'='*60}\n")
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(TIMEOUT_SEC)
    
    try:
        # Bind to ppp0 interface
        bind_to_interface(sock, INTERFACE)
        print(f"Bound to {INTERFACE}")
        print(f"Starting UDP echo test...\n")
        
        # Statistics
        sent_packets = {}      # seq -> send_timestamp
        received_packets = {}  # seq -> (recv_timestamp, rtt)
        
        start_time = time.time()
        
        # Send all packets with specified delay
        for seq in range(1, num_packets + 1):
            try:
                packet = create_packet(seq, packet_size, delay_ms if seq == 1 else None)
                send_time = time.time()
                sock.sendto(packet, (server_host, server_port))
                sent_packets[seq] = send_time
                
                if seq % 50 == 0 or seq == num_packets:
                    print(f"Sent {seq}/{num_packets} packets...")
                
                # Delay before next packet (except after last one)
                if seq < num_packets:
                    time.sleep(delay_ms / 1000.0)
                    
            except Exception as e:
                print(f"Error sending packet {seq}: {e}")
                break
        
        send_end_time = time.time()
        print(f"\nAll packets sent in {send_end_time - start_time:.2f}s")
        print(f"Waiting for echo responses...\n")
        
        # Receive echoed packets
        last_receive_time = time.time()
        while len(received_packets) < len(sent_packets):
            try:
                # Check if we've waited too long
                if time.time() - last_receive_time > TIMEOUT_SEC:
                    print(f"Timeout waiting for responses (received {len(received_packets)}/{len(sent_packets)})")
                    break
                
                # Receive echoed packet
                data, addr = sock.recvfrom(4096)
                recv_time = time.time()
                last_receive_time = recv_time
                
                # Parse sequence number
                if len(data) >= 4:
                    recv_seq = struct.unpack('!I', data[:4])[0]
                    
                    if recv_seq in sent_packets:
                        rtt = (recv_time - sent_packets[recv_seq]) * 1000  # RTT in ms
                        received_packets[recv_seq] = (recv_time, rtt)
                        
                        if len(received_packets) % 50 == 0 or len(received_packets) == len(sent_packets):
                            print(f"Received {len(received_packets)}/{len(sent_packets)} echoes...")
                    else:
                        print(f"Warning: Received unexpected sequence {recv_seq}")
                        
            except socket.timeout:
                # Timeout on individual receive - check if we got all packets
                if len(received_packets) == len(sent_packets):
                    break
                else:
                    print(f"Receive timeout (got {len(received_packets)}/{len(sent_packets)})")
                    break
            except Exception as e:
                print(f"Error receiving: {e}")
                break
        
        end_time = time.time()
        total_time = end_time - start_time
        
        # Calculate statistics
        print(f"\n{'='*60}")
        print(f"UDP Echo Test Results:")
        print(f"{'='*60}")
        print(f"Total test duration: {total_time:.2f}s")
        print(f"Packets sent: {len(sent_packets)}")
        print(f"Packets received: {len(received_packets)}")
        print(f"Packet loss: {len(sent_packets) - len(received_packets)} ({100 * (1 - len(received_packets)/len(sent_packets)):.2f}%)")
        
        if received_packets:
            rtts = [rtt for _, rtt in received_packets.values()]
            print(f"\nRound-Trip Time:")
            print(f"  Min: {min(rtts):.2f}ms")
            print(f"  Max: {max(rtts):.2f}ms")
            print(f"  Avg: {sum(rtts)/len(rtts):.2f}ms")
        
        bytes_sent = len(sent_packets) * packet_size
        bytes_received = len(received_packets) * packet_size
        print(f"\nData transfer:")
        print(f"  Sent: {bytes_sent} bytes ({bytes_sent * 8 / total_time:.1f} bps)")
        print(f"  Received: {bytes_received} bytes ({bytes_received * 8 / total_time:.1f} bps)")
        
        # Find lost packets
        lost_packets = sorted(set(sent_packets.keys()) - set(received_packets.keys()))
        if lost_packets:
            print(f"\nLost packet sequences: {lost_packets[:20]}")  # Show first 20
            if len(lost_packets) > 20:
                print(f"  ... and {len(lost_packets) - 20} more")
        
        print(f"{'='*60}\n")
        
        # Return statistics for aggregation
        return {
            'packet_size': packet_size,
            'delay_ms': delay_ms,
            'total_time': total_time,
            'sent': len(sent_packets),
            'received': len(received_packets),
            'lost': len(sent_packets) - len(received_packets),
            'loss_pct': 100 * (1 - len(received_packets)/len(sent_packets)) if sent_packets else 0,
            'avg_rtt': sum(rtts)/len(rtts) if rtts else 0,
            'min_rtt': min(rtts) if rtts else 0,
            'max_rtt': max(rtts) if rtts else 0,
            'throughput_bps': bytes_received * 8 / total_time if total_time > 0 else 0
        }
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        sock.close()

def save_results(results, output_file=None):
    """Save test results to CSV file"""
    if output_file is None:
        # Find next available filename
        existing = glob.glob("udp_result_*.csv")
        if existing:
            numbers = []
            for f in existing:
                try:
                    num = int(f.split('_')[-1].split('.')[0])
                    numbers.append(num)
                except:
                    pass
            next_num = max(numbers) + 1 if numbers else 1
        else:
            next_num = 1
        output_file = f"udp_result_{next_num}.csv"
    
    with open(output_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['Packet_Size', 'Delay_ms', 'Duration_s', 'Transmitted', 
                        'Received', 'Lost', 'Loss_pct', 'Avg_RTT_ms', 'Throughput_bps'])
        
        for r in results:
            if r:  # Skip None results
                writer.writerow([
                    r['packet_size'],
                    r['delay_ms'],
                    f"{r['total_time']:.2f}",
                    r['sent'],
                    r['received'],
                    r['lost'],
                    f"{r['loss_pct']:.2f}",
                    f"{r['avg_rtt']:.2f}",
                    f"{r['throughput_bps']:.1f}"
                ])
    
    print(f"\nResults saved to: {output_file}")
    return output_file

def main():
    global SERVER_HOST, SERVER_PORT
    
    parser = argparse.ArgumentParser(
        description='UDP Echo Test - Test UDP packet loss and latency over PPP',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Default: sweep 100-200 bytes, 80ms delay
  %(prog)s --size 125                # Single test: 125 byte packets
  %(prog)s --start 120 --end 160     # Sweep from 120 to 160 bytes
  %(prog)s --step 5                  # Sweep with 5 byte increments
  %(prog)s --delay 100               # 100ms delay between packets
  %(prog)s --packets 500             # Send 500 packets per size
  %(prog)s -o mytest.csv             # Save results to specific file
        """
    )
    
    parser.add_argument('--size', type=int, default=None,
                       help='Single packet size in bytes (disables sweep mode)')
    parser.add_argument('--start', type=int, default=100,
                       help='Starting packet size for sweep (default: 100)')
    parser.add_argument('--end', type=int, default=200,
                       help='Ending packet size for sweep (default: 200)')
    parser.add_argument('--step', type=int, default=10,
                       help='Packet size increment for sweep (default: 10)')
    parser.add_argument('--delay', type=int, default=SEND_DELAY_MS,
                       help=f'Delay between packets in ms (default: {SEND_DELAY_MS})')
    parser.add_argument('--packets', type=int, default=NUM_PACKETS,
                       help=f'Number of packets to send (default: {NUM_PACKETS})')
    parser.add_argument('--server', type=str, default=SERVER_HOST,
                       help=f'Echo server hostname/IP (default: {SERVER_HOST})')
    parser.add_argument('--port', type=int, default=SERVER_PORT,
                       help=f'Echo server port (default: {SERVER_PORT})')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output CSV file (default: auto-numbered udp_result_N.csv)')
    
    args = parser.parse_args()
    
    # Update globals for potential use in functions
    SERVER_HOST = args.server
    SERVER_PORT = args.port
    
    results = []
    
    if args.size is not None:
        # Single packet size mode
        if args.size < 12:
            print("Error: Packet size must be at least 12 bytes (for header)")
            sys.exit(1)
        if args.size > 1472:
            print("Warning: Packet size > 1472 may cause IP fragmentation")
        
        result = run_test(args.delay, args.size, args.packets, args.server, args.port)
        if result:
            results.append(result)
    else:
        # Sweep mode (default)
        packet_sizes = range(args.start, args.end + 1, args.step)
        total_tests = len(list(packet_sizes))
        
        print(f"\n{'#'*60}")
        print(f"UDP ECHO TEST SUITE")
        print(f"{'#'*60}")
        print(f"Running {total_tests} tests with packet sizes from {args.start} to {args.end} bytes")
        print(f"Increment: {args.step} bytes, Delay: {args.delay}ms, Packets per test: {args.packets}")
        print(f"{'#'*60}\n")
        
        for idx, size in enumerate(packet_sizes, 1):
            test_label = f"Test {idx}/{total_tests}: Packet size {size} bytes"
            result = run_test(args.delay, size, args.packets, args.server, args.port, test_label)
            if result:
                results.append(result)
            
            # Small delay between tests
            if idx < total_tests:
                print("Waiting 2 seconds before next test...")
                time.sleep(2)
    
    # Save results if any tests completed
    if results:
        save_results(results, args.output)
        
        # Print summary
        print(f"\n{'#'*60}")
        print(f"TEST SUITE SUMMARY")
        print(f"{'#'*60}")
        print(f"{'Size(B)':<10} {'Loss%':<10} {'RTT(ms)':<12} {'Speed(bps)':<15}")
        print(f"{'-'*60}")
        for r in results:
            print(f"{r['packet_size']:<10} {r['loss_pct']:<10.2f} {r['avg_rtt']:<12.2f} {r['throughput_bps']:<15.1f}")
        print(f"{'#'*60}\n")
    else:
        print("\nNo test results to save.")

if __name__ == "__main__":
    main()
