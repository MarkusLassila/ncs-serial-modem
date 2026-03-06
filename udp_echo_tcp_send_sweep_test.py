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
import threading
from collections import defaultdict
import queue

# Configuration defaults
SERVER_HOST = "dev2.testncs.com"
SERVER_PORT = 21185
TCP_CONTROL_PORT = 20180
INTERFACE = "ppp0"
PACKET_SIZE = 100        # Default: ~10 Kbps with 80ms delay
NUM_PACKETS = 200
SEND_DELAY_MS = 80       # 80ms delay between packets
TIMEOUT_SEC = 5.0        # Socket timeout for receiving
TCP_DATA_SIZE = 20 * 1024  # 20KB per UDP packet
TCP_SPEED_KBPS = 100     # 100 kbps rate limit

def bind_to_interface(sock, interface):
    """Bind socket to specific network interface"""
    SO_BINDTODEVICE = 25
    sock.setsockopt(socket.SOL_SOCKET, SO_BINDTODEVICE, 
                    interface.encode('utf-8'))

def tcp_uplink_thread(server_host, tcp_port, data_size, speed_kbps, trigger_queue, stop_event):
    """
    TCP uplink thread that:
    1. Sends initial control message to disable loopback
    2. Sends data_size bytes after each UDP cycle completion
    Rate limited to speed_kbps
    """
    try:
        # Create TCP socket
        tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        tcp_sock.settimeout(10.0)
        
        # Bind to interface
        bind_to_interface(tcp_sock, INTERFACE)
        
        # Connect to server
        print(f"TCP: Connecting to {server_host}:{tcp_port}...")
        tcp_sock.connect((server_host, tcp_port))
        print(f"TCP: Connected to {server_host}:{tcp_port}")
        
        # Send initial control message to disable loopback
        control_msg = b"enable_ul_data_only"
        tcp_sock.sendall(control_msg)
        print(f"TCP: Sent control message: '{control_msg.decode()}'")
        
        # Wait for UDP cycle completion signals
        bytes_per_second = (speed_kbps * 1000) // 8
        chunk_size = 1024  # Send in 1KB chunks
        
        while not stop_event.is_set():
            try:
                # Wait for trigger (with timeout to check stop_event)
                cycle_num = trigger_queue.get(timeout=0.5)
                
                print(f"TCP: Starting transmission of {data_size} bytes (batch {cycle_num})...")
                
                # Send batch marker so analyzer can detect batch boundaries
                # Format: 'BTCH' (4 bytes) + cycle_num (4 bytes) + data_size (4 bytes)
                # Include data_size as fallback in case marker packet is lost from trace
                marker = struct.pack('!4sII', b'BTCH', cycle_num, data_size)
                tcp_sock.sendall(marker)
                
                bytes_sent = 0
                start_time = time.time()
                
                # Generate and send data in chunks
                while bytes_sent < data_size and not stop_event.is_set():
                    # Calculate how much to send
                    to_send = min(chunk_size, data_size - bytes_sent)
                    
                    # Create data chunk (simple pattern)
                    data = b'T' * to_send
                    
                    # Send chunk
                    chunk_start = time.time()
                    tcp_sock.sendall(data)
                    bytes_sent += to_send
                    
                    # Rate limiting: sleep to maintain target speed
                    expected_duration = bytes_sent / bytes_per_second
                    actual_duration = time.time() - start_time
                    sleep_time = expected_duration - actual_duration
                    
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                
                elapsed = time.time() - start_time
                actual_kbps = (bytes_sent * 8 / 1000) / elapsed if elapsed > 0 else 0
                print(f"TCP: Sent {bytes_sent} bytes in {elapsed:.2f}s ({actual_kbps:.1f} kbps)")
                
            except queue.Empty:
                # No trigger yet, continue waiting
                continue
            except Exception as e:
                if not stop_event.is_set():
                    print(f"TCP: Error during transmission: {e}")
                break
        
        print("TCP: Thread stopping...")
        tcp_sock.close()
        
    except Exception as e:
        print(f"TCP: Connection error: {e}")
        import traceback
        traceback.print_exc()

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

def run_test(delay_ms, packet_size, num_packets, server_host, server_port, tcp_data_size=20*1024, seq_offset=0, batch_num=1, test_label=None):
    """Run UDP echo test with specified parameters
    
    Args:
        seq_offset: Starting sequence number (for continuous numbering across batches)
        batch_num: Batch number for TCP marker (for correlation in analyzer)
    """
    print(f"\n{'='*60}")
    if test_label:
        print(f"{test_label}")
        print(f"{'='*60}")
    print(f"UDP Echo Test Configuration:")
    print(f"  UDP Packet size: {packet_size} bytes")
    print(f"  UDP Delay: {delay_ms}ms")
    print(f"  Number of UDP packets: {num_packets}")
    print(f"  Sequence range: {seq_offset + 1} to {seq_offset + num_packets}")
    print(f"  UDP Target speed: ~{(packet_size * 8 * 1000 / delay_ms):.1f} bps")
    print(f"  TCP Data size: {tcp_data_size/1024:.0f} KB")
    print(f"  TCP Speed: {TCP_SPEED_KBPS} kbps")
    print(f"  Server: {server_host}:{server_port}")
    print(f"{'='*60}\n")
    
    # Create UDP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    # Set socket to non-blocking mode to prevent sendto() from blocking
    sock.setblocking(False)
    
    # Increase send buffer to handle bursts
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 256*1024)  # 256KB send buffer
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 256*1024)  # 256KB recv buffer
    except:
        pass  # Ignore if can't set buffer size
    
    try:
        # Bind to ppp0 interface
        bind_to_interface(sock, INTERFACE)
        print(f"Bound to {INTERFACE}")
        print(f"Starting UDP echo test with concurrent send/receive...\n")
        
        # Shared statistics with locks
        sent_packets = {}      # seq -> send_timestamp
        received_packets = {}  # seq -> (recv_timestamp, rtt)
        sent_lock = threading.Lock()
        recv_lock = threading.Lock()
        
        # Control flags
        sending_complete = threading.Event()
        stop_receiving = threading.Event()
        tcp_stop = threading.Event()
        tcp_trigger = queue.Queue()
        
        start_time = time.time()
        
        # Start TCP uplink thread
        tcp_thread = threading.Thread(
            target=tcp_uplink_thread,
            args=(server_host, TCP_CONTROL_PORT, tcp_data_size, TCP_SPEED_KBPS, tcp_trigger, tcp_stop),
            daemon=True
        )
        tcp_thread.start()
        time.sleep(0.5)  # Give TCP time to connect and send control message
        
        def sender_thread():
            """Send packets with specified delay"""
            
            # Trigger TCP transmission to start with UDP cycle
            print(f"UDP: Starting batch {batch_num}, triggering TCP transmission")
            tcp_trigger.put(batch_num)
            
            for seq in range(1, num_packets + 1):
                try:
                    actual_seq = seq_offset + seq  # Apply offset for continuous numbering
                    packet = create_packet(actual_seq, packet_size, delay_ms if seq == 1 else None)
                    send_time = time.time()
                    
                    # Retry sendto if socket buffer is full
                    max_retries = 10
                    sent_successfully = False
                    for retry in range(max_retries):
                        try:
                            sock.sendto(packet, (server_host, server_port))
                            sent_successfully = True
                            break  # Success
                        except BlockingIOError:
                            # Socket buffer full, wait a bit and retry
                            if retry < max_retries - 1:
                                time.sleep(0.01)  # 10ms wait
                            else:
                                print(f"Failed to send packet {actual_seq} after {max_retries} retries")
                                raise
                    
                    if not sent_successfully:
                        break
                    
                    with sent_lock:
                        sent_packets[actual_seq] = send_time
                    
                    if seq % 50 == 0 or seq == num_packets:
                        with recv_lock:
                            recv_count = len(received_packets)
                        print(f"Sent {actual_seq}/{seq_offset + num_packets} packets, Received {recv_count} echoes")
                    
                    # Delay before next packet (except after last one)
                    if seq < num_packets:
                        time.sleep(delay_ms / 1000.0)
                        
                except Exception as e:
                    print(f"Error sending packet {actual_seq}: {e}")
                    import traceback
                    traceback.print_exc()
                    break
            
            print(f"UDP: Batch {batch_num} complete")
            
            # Signal that sending is complete
            sending_complete.set()
        
        def receiver_thread():
            """Receive echo packets continuously"""
            MAX_RTT_SECONDS = 2.0  # Treat packets taking >2s as lost
            last_activity_time = time.time()
            
            while not stop_receiving.is_set():
                try:
                    # Try to receive data (non-blocking)
                    try:
                        data, addr = sock.recvfrom(4096)
                        recv_time = time.time()
                        last_activity_time = recv_time
                        
                        # Parse sequence number
                        if len(data) >= 4:
                            recv_seq = struct.unpack('!I', data[:4])[0]
                            
                            # Get send_time without holding lock for long
                            send_time = None
                            with sent_lock:
                                if recv_seq in sent_packets:
                                    send_time = sent_packets[recv_seq]
                            
                            if send_time is not None:
                                rtt = (recv_time - send_time) * 1000  # RTT in ms
                                
                                # Only count packets that came back within 2 seconds
                                if (recv_time - send_time) <= MAX_RTT_SECONDS:
                                    with recv_lock:
                                        received_packets[recv_seq] = (recv_time, rtt)
                                        total_received = len(received_packets)
                                    
                                    if total_received % 50 == 0:
                                        with sent_lock:
                                            total_sent = len(sent_packets)
                                        print(f"Received {total_received}/{total_sent} echoes")
                                else:
                                    # Packet took too long, treat as lost
                                    print(f"Packet {recv_seq} RTT {rtt:.0f}ms > 2s, treating as lost")
                    
                    except BlockingIOError:
                        # No data available (normal), just continue
                        pass
                    
                    # Small sleep to prevent busy-waiting
                    time.sleep(0.01)  # 10ms
                    
                    # Check if we should stop
                    if sending_complete.is_set():
                        with sent_lock:
                            total_sent = len(sent_packets)
                        with recv_lock:
                            total_received = len(received_packets)
                        
                        # Stop if we got all packets or no activity for TIMEOUT_SEC
                        if total_received >= total_sent:
                            break
                        if time.time() - last_activity_time > TIMEOUT_SEC:
                            print(f"Receive timeout (got {total_received}/{total_sent})")
                            break
                        
                except Exception as e:
                    if not stop_receiving.is_set():
                        print(f"Receiver error: {e}")
                        import traceback
                        traceback.print_exc()
                    break
        
        # Start receiver first, then sender
        recv_thread = threading.Thread(target=receiver_thread, daemon=True)
        send_thread = threading.Thread(target=sender_thread, daemon=True)
        
        recv_thread.start()
        time.sleep(0.1)  # Small delay to ensure receiver is ready
        send_thread.start()
        
        # Wait for sender to complete
        send_thread.join()
        
        # Wait for receiver to complete (with timeout)
        recv_thread.join(timeout=TIMEOUT_SEC + 2)
        stop_receiving.set()
        
        # Wait for TCP thread to finish current transmission
        tcp_stop.set()
        tcp_thread.join(timeout=5)
        
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
            'tcp_data_size': tcp_data_size,
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
        writer.writerow(['TCP_Data_KB', 'UDP_Packet_Size', 'Delay_ms', 'Duration_s', 'Transmitted', 
                        'Received', 'Lost', 'Loss_pct', 'Avg_RTT_ms', 'Throughput_bps'])
        
        for r in results:
            if r:  # Skip None results
                writer.writerow([
                    f"{r['tcp_data_size']/1024:.0f}",
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
        description='UDP Echo Test - Test UDP packet loss and latency with concurrent TCP traffic',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s                           # Default: sweep TCP 10-50 KB, UDP 125 bytes
  %(prog)s --tcp-size 20             # Single test: 20 KB TCP data
  %(prog)s --tcp-start 15 --tcp-end 40  # Sweep TCP from 15 to 40 KB
  %(prog)s --tcp-step 5              # Sweep with 5 KB increments
  %(prog)s --udp-size 150            # UDP packet size (default: 125 bytes)
  %(prog)s --delay 100               # 100ms delay between UDP packets
  %(prog)s --packets 500             # Send 500 UDP packets per test
  %(prog)s -o mytest.csv             # Save results to specific file
        """
    )
    
    parser.add_argument('--tcp-size', type=int, default=None,
                       help='Single TCP data size in KB (disables sweep mode)')
    parser.add_argument('--tcp-start', type=int, default=10,
                       help='Starting TCP data size for sweep in KB (default: 10)')
    parser.add_argument('--tcp-end', type=int, default=50,
                       help='Ending TCP data size for sweep in KB (default: 50)')
    parser.add_argument('--tcp-step', type=int, default=5,
                       help='TCP data size increment for sweep in KB (default: 5)')
    parser.add_argument('--udp-size', type=int, default=PACKET_SIZE,
                       help=f'UDP packet size in bytes (default: {PACKET_SIZE})')
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
    
    # Validate UDP packet size
    if args.udp_size < 12:
        print("Error: UDP packet size must be at least 12 bytes (for header)")
        sys.exit(1)
    if args.udp_size > 1472:
        print("Warning: UDP packet size > 1472 may cause IP fragmentation")
    
    seq_offset = 0  # Track cumulative sequence numbers across tests
    
    if args.tcp_size is not None:
        # Single TCP size mode
        tcp_data_size = args.tcp_size * 1024  # Convert KB to bytes
        result = run_test(args.delay, args.udp_size, args.packets, args.server, args.port, tcp_data_size, seq_offset, batch_num=1)
        if result:
            results.append(result)
            seq_offset += args.packets
    else:
        # Sweep mode (default) - sweep TCP data sizes
        tcp_sizes_kb = range(args.tcp_start, args.tcp_end + 1, args.tcp_step)
        total_tests = len(list(tcp_sizes_kb))
        
        print(f"\n{'#'*60}")
        print(f"UDP ECHO TEST SUITE WITH TCP TRAFFIC")
        print(f"{'#'*60}")
        print(f"Running {total_tests} tests with TCP data sizes from {args.tcp_start} to {args.tcp_end} KB")
        print(f"TCP Increment: {args.tcp_step} KB, TCP Speed: {TCP_SPEED_KBPS} kbps")
        print(f"UDP Packet size: {args.udp_size} bytes, Delay: {args.delay}ms, Packets per test: {args.packets}")
        print(f"Total UDP packets across all tests: {total_tests * args.packets} (seq 1 to {total_tests * args.packets})")
        print(f"{'#'*60}\n")
        
        for idx, tcp_size_kb in enumerate(tcp_sizes_kb, 1):
            tcp_data_size = tcp_size_kb * 1024  # Convert KB to bytes
            test_label = f"Test {idx}/{total_tests}: TCP data size {tcp_size_kb} KB"
            result = run_test(args.delay, args.udp_size, args.packets, args.server, args.port, tcp_data_size, seq_offset, batch_num=idx, test_label=test_label)
            if result:
                results.append(result)
                seq_offset += args.packets  # Increment for next test
            
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
        print(f"{'TCP(KB)':<10} {'UDP(B)':<10} {'Loss%':<10} {'RTT(ms)':<12} {'Speed(bps)':<15}")
        print(f"{'-'*60}")
        for r in results:
            print(f"{r['tcp_data_size']/1024:<10.0f} {r['packet_size']:<10} {r['loss_pct']:<10.2f} {r['avg_rtt']:<12.2f} {r['throughput_bps']:<15.1f}")
        print(f"{'#'*60}\n")
    else:
        print("\nNo test results to save.")

if __name__ == "__main__":
    main()
