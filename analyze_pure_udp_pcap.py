#!/usr/bin/env python3
"""
PCAP Analyzer for UDP Echo Test
Analyzes UDP packets to calculate packet loss based on sequence numbers
Groups results by packet size for sweep test analysis
"""

import sys
import os
import glob
import argparse
import csv
import struct
from collections import defaultdict
from scapy.all import rdpcap, UDP, IP
from datetime import datetime

def extract_packet_info(udp_payload):
    """Extract sequence number and delay from UDP payload"""
    try:
        if len(udp_payload) < 12:
            return None, None
        
        # Extract sequence number (first 4 bytes)
        seq_num = struct.unpack('!I', udp_payload[:4])[0]
        
        # Try to extract delay from first packet (has extra header)
        delay_ms = None
        if len(udp_payload) >= 16:
            # Check if this might be first packet with delay
            potential_delay = struct.unpack('!I', udp_payload[12:16])[0]
            # Sanity check: delay should be reasonable (0-1000ms)
            if 0 <= potential_delay <= 1000:
                # Additional check: look for DELAY= marker
                if b'DELAY=' in udp_payload:
                    delay_ms = potential_delay
        
        return seq_num, delay_ms
    except:
        return None, None


def get_next_result_filename(base_name="udp_result", extension="csv"):
    """Find the next available filename with auto-incrementing number"""
    pattern = f"{base_name}_*.{extension}"
    existing_files = glob.glob(pattern)
    
    if not existing_files:
        return f"{base_name}_1.{extension}"
    
    numbers = []
    for filename in existing_files:
        try:
            num_str = filename[len(base_name)+1:-len(extension)-1]
            numbers.append(int(num_str))
        except (ValueError, IndexError):
            continue
    
    if not numbers:
        return f"{base_name}_1.{extension}"
    
    next_num = max(numbers) + 1
    return f"{base_name}_{next_num}.{extension}"


def save_results(filename, results_by_size):
    """Save analysis results to CSV file"""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Packet_Size', 'Delay_ms', 'Duration_s', 'Transmitted', 
                        'Captured', 'Lost', 'Loss_pct'])
        
        # Sort by packet size
        for packet_size in sorted(results_by_size.keys()):
            stats = results_by_size[packet_size]
            writer.writerow([
                packet_size,
                stats['delay_ms'] if stats['delay_ms'] is not None else '',
                f"{stats['duration']:.2f}",
                stats['transmitted'],
                stats['captured'],
                stats['lost'],
                f"{stats['loss_pct']:.2f}"
            ])
    
    print(f"\nResults saved to: {filename}")


def analyze_udp_pcap(pcap_file, target_port=None):
    """Analyze PCAP file for UDP packets"""
    print(f"Reading {pcap_file}...")
    
    try:
        packets = rdpcap(pcap_file)
    except Exception as e:
        print(f"Error reading pcap: {e}")
        return None
    
    print(f"Loaded {len(packets)} packets\n")
    
    # Group packets by size
    packets_by_size = defaultdict(list)
    delay_info = {}  # packet_size -> delay_ms
    
    udp_packet_count = 0
    for pkt in packets:
        if not pkt.haslayer(UDP) or not pkt.haslayer(IP):
            continue
        
        udp = pkt[UDP]
        ip = pkt[IP]
        
        # Filter by port if specified
        if target_port and udp.sport != target_port and udp.dport != target_port:
            continue
        
        udp_packet_count += 1
        
        # Get packet size (UDP payload length)
        packet_size = len(udp.payload)
        
        # Extract sequence number and delay
        seq_num, delay_ms = extract_packet_info(bytes(udp.payload))
        
        if seq_num is not None:
            packets_by_size[packet_size].append({
                'seq': seq_num,
                'timestamp': pkt.time,
                'src': ip.src,
                'dst': ip.dst,
                'sport': udp.sport,
                'dport': udp.dport
            })
            
            # Store delay info for this packet size
            if delay_ms is not None:
                delay_info[packet_size] = delay_ms
    
    print(f"Found {udp_packet_count} UDP packets")
    print(f"Grouped into {len(packets_by_size)} different packet sizes\n")
    
    # Analyze each packet size group
    results_by_size = {}
    
    for packet_size in sorted(packets_by_size.keys()):
        pkts = packets_by_size[packet_size]
        
        print(f"{'='*60}")
        print(f"Packet Size: {packet_size} bytes")
        print(f"{'='*60}")
        
        # Separate client->server and server->client
        # Assume client sends first (lower sequence numbers initially)
        # Or use port numbers if available
        
        # Group by direction based on source port
        by_direction = defaultdict(list)
        for p in pkts:
            direction = (p['src'], p['sport'], p['dst'], p['dport'])
            by_direction[direction].append(p)
        
        # Find the direction with sending pattern (client to server, then echoes back)
        # Client direction should have sequential sequence numbers
        client_to_server = None
        server_to_client = None
        
        for direction, dir_pkts in by_direction.items():
            seqs = sorted([p['seq'] for p in dir_pkts])
            # Direction with seq starting from 1 is likely client->server
            if seqs and seqs[0] == 1:
                client_to_server = direction
                server_to_client = (direction[2], direction[3], direction[0], direction[1])
                break
        
        if not client_to_server:
            # Fallback: direction with more unique sequences
            client_to_server = max(by_direction.keys(), 
                                   key=lambda d: len(set(p['seq'] for p in by_direction[d])))
            server_to_client = None
        
        # Analyze client->server packets (transmitted)
        client_pkts = by_direction[client_to_server]
        client_seqs = set(p['seq'] for p in client_pkts)
        
        # Analyze server->client packets (echoed/received)
        server_pkts = []
        if server_to_client and server_to_client in by_direction:
            server_pkts = by_direction[server_to_client]
        
        server_seqs = set(p['seq'] for p in server_pkts)
        
        # Calculate statistics
        if client_seqs:
            min_seq = min(client_seqs)
            max_seq = max(client_seqs)
            expected_count = max_seq - min_seq + 1
        else:
            min_seq = max_seq = expected_count = 0
        
        captured_count = len(client_seqs)
        echoed_count = len(server_seqs)
        
        # Calculate timing
        timestamps = [p['timestamp'] for p in client_pkts]
        if timestamps:
            duration = max(timestamps) - min(timestamps)
        else:
            duration = 0
        
        # Determine what "transmitted" means
        # If we see echoes, we know server got them, so transmitted = echoed + lost
        # Otherwise, transmitted = expected (based on max seq)
        if server_seqs:
            # We have echo data - transmitted is what server acknowledged
            transmitted = expected_count
            # Lost from client perspective = what we expected but didn't capture on client side
            lost_client = expected_count - captured_count
            # Lost echoes = what was sent but not echoed back
            lost_echo = captured_count - echoed_count
            
            print(f"Sequence range: {min_seq} to {max_seq}")
            print(f"Expected packets: {expected_count}")
            print(f"Client->Server captured: {captured_count}")
            print(f"Server->Client echoes: {echoed_count}")
            print(f"Lost in transit (client->server): {lost_client}")
            print(f"Lost echoes (server->client): {lost_echo}")
            print(f"Total loss: {lost_client + lost_echo}")
            
            # For CSV, use total transmitted (both directions)
            stats = {
                'packet_size': packet_size,
                'delay_ms': delay_info.get(packet_size),
                'duration': duration,
                'transmitted': expected_count * 2,  # Both directions
                'captured': captured_count + echoed_count,
                'lost': lost_client + lost_echo,
                'loss_pct': ((lost_client + lost_echo) / (expected_count * 2) * 100) if expected_count > 0 else 0
            }
        else:
            # No echo data - only client->server
            transmitted = expected_count
            lost = expected_count - captured_count
            
            print(f"Sequence range: {min_seq} to {max_seq}")
            print(f"Expected packets: {expected_count}")
            print(f"Captured packets: {captured_count}")
            print(f"Lost packets: {lost}")
            
            stats = {
                'packet_size': packet_size,
                'delay_ms': delay_info.get(packet_size),
                'duration': duration,
                'transmitted': transmitted,
                'captured': captured_count,
                'lost': lost,
                'loss_pct': (lost / transmitted * 100) if transmitted > 0 else 0
            }
        
        print(f"Duration: {duration:.2f}s")
        print(f"Loss percentage: {stats['loss_pct']:.2f}%")
        if stats['delay_ms'] is not None:
            print(f"Delay: {stats['delay_ms']}ms")
        print()
        
        results_by_size[packet_size] = stats
    
    return results_by_size


def main():
    parser = argparse.ArgumentParser(
        description='Analyze UDP PCAP files from UDP echo tests',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s capture.pcap                    # Analyze UDP packets (auto-save)
  %(prog)s capture.pcap -o results.csv     # Save to specific file
  %(prog)s capture.pcap --port 21185       # Filter by specific UDP port
        """
    )
    
    parser.add_argument('pcap_file', help='PCAP file to analyze')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output CSV file (default: auto-numbered udp_analysis_N.csv)')
    parser.add_argument('--port', type=int, default=None,
                       help='Filter by specific UDP port (default: all UDP traffic)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pcap_file):
        print(f"Error: File '{args.pcap_file}' not found")
        sys.exit(1)
    
    # Analyze the PCAP file
    results = analyze_udp_pcap(args.pcap_file, args.port)
    
    if not results:
        print("No results to save.")
        sys.exit(1)
    
    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        output_file = get_next_result_filename("udp_analysis", "csv")
    
    # Save results
    save_results(output_file, results)
    
    # Print summary
    print(f"\n{'#'*60}")
    print(f"ANALYSIS SUMMARY")
    print(f"{'#'*60}")
    print(f"{'Size(B)':<12} {'Loss%':<10} {'Transmitted':<12} {'Captured':<10}")
    print(f"{'-'*60}")
    for size in sorted(results.keys()):
        r = results[size]
        print(f"{size:<12} {r['loss_pct']:<10.2f} {r['transmitted']:<12} {r['captured']:<10}")
    print(f"{'#'*60}\n")


if __name__ == "__main__":
    main()
