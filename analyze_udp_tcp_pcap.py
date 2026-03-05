#!/usr/bin/env python3
"""
PCAP Analyzer for UDP Echo Test
Analyzes UDP packets to calculate packet loss based on sequence numbers
Groups results by packet size for sweep test analysis

Defaults:
- Filters UDP port 21185 (UDP echo port)
- Requires minimum 10 packets per size (filters noise)
- Skips packet sizes with sequences not starting near 1 (not echo tests)
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


def analyze_udp_pcap(pcap_file, target_port=None, min_packets=10):
    """Analyze PCAP file for UDP packets"""
    print(f"Reading {pcap_file}...")
    
    try:
        packets = rdpcap(pcap_file)
    except Exception as e:
        print(f"Error reading pcap: {e}")
        return None
    
    print(f"Loaded {len(packets)} packets\n")
    
    if target_port:
        print(f"Filtering for UDP port {target_port}")
    
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
    
    # Filter out noise - packet sizes with too few packets or invalid sequences
    filtered_sizes = {}
    for size, pkts in packets_by_size.items():
        # Get all unique sequence numbers
        seqs = set(p['seq'] for p in pkts)
        
        # Skip if too few packets (likely noise)
        if len(pkts) < min_packets:
            print(f"Skipping size {size}B - only {len(pkts)} packet(s) (noise)")
            continue
        
        # Skip if doesn't look like a valid echo test (seq doesn't start near 1)
        min_seq = min(seqs)
        if min_seq > 100:  # Allow some flexibility but filter obvious outliers
            print(f"Skipping size {size}B - sequence starts at {min_seq} (not an echo test)")
            continue
        
        filtered_sizes[size] = pkts
    
    if not filtered_sizes:
        print("No valid UDP echo test data found after filtering\n")
        return None
    
    print(f"Analyzing {len(filtered_sizes)} valid packet size(s)\n")
    packets_by_size = filtered_sizes
    
    # Analyze each packet size group
    results_by_size = {}
    
    for packet_size in sorted(packets_by_size.keys()):
        pkts = packets_by_size[packet_size]
        
        print(f"{'='*60}")
        print(f"Packet Size: {packet_size} bytes")
        print(f"{'='*60}")
        
        # Separate client->server and server->client
        # In UDP echo tests, client sends TO server port, server echoes FROM server port
        # This handles multiple test runs with different client source ports
        
        # Identify server port (most common destination port, or 21185)
        dest_ports = [p['dport'] for p in pkts]
        server_port = max(set(dest_ports), key=dest_ports.count) if dest_ports else 21185
        
        # Group by role: packets TO server_port are client->server
        client_pkts = [p for p in pkts if p['dport'] == server_port]
        server_pkts = [p for p in pkts if p['sport'] == server_port]
        
        print(f"Total packets in pcap: {len(pkts)}")
        print(f"Identified server port: {server_port}")
        
        # Get unique source ports (indicates number of test runs/batches)
        client_src_ports = set(p['sport'] for p in client_pkts)
        if len(client_src_ports) > 1:
            print(f"Found {len(client_src_ports)} different client source ports (multiple test runs)")
        
        # Analyze sequences
        client_seqs = set(p['seq'] for p in client_pkts)
        server_seqs = set(p['seq'] for p in server_pkts)
        
        # Calculate statistics
        if client_seqs:
            min_seq = min(client_seqs)
            max_seq = max(client_seqs)
            expected_total = max_seq - min_seq + 1
        else:
            min_seq = max_seq = expected_total = 0
        
        # Count actual packets
        client_count = len(client_pkts)
        server_count = len(server_pkts)
        
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
            # We have echo data
            # Lost from client perspective = what we expected but didn't capture on client side
            lost_client = expected_total - client_count
            # Lost echoes = what was sent but not echoed back
            lost_echo = client_count - server_count
            
            print(f"Sequence range: {min_seq} to {max_seq}")
            print(f"Expected packets: {expected_total}")
            print(f"Client->Server captured: {client_count}")
            print(f"Server->Client echoes: {server_count}")
            print(f"Lost in transit (client->server): {lost_client}")
            print(f"Lost echoes (server->client): {lost_echo}")
            print(f"Total loss: {lost_client + lost_echo}")
            
            # For CSV, use total transmitted (both directions)
            stats = {
                'packet_size': packet_size,
                'delay_ms': delay_info.get(packet_size),
                'duration': duration,
                'transmitted': expected_total * 2,  # Both directions
                'captured': client_count + server_count,
                'lost': lost_client + lost_echo,
                'loss_pct': ((lost_client + lost_echo) / (expected_total * 2) * 100) if expected_total > 0 else 0
            }
        else:
            # No echo data - only client->server
            lost = expected_total - client_count
            
            print(f"Sequence range: {min_seq} to {max_seq}")
            print(f"Expected packets: {expected_total}")
            print(f"Captured packets: {client_count}")
            print(f"Lost packets: {lost}")
            
            stats = {
                'packet_size': packet_size,
                'delay_ms': delay_info.get(packet_size),
                'duration': duration,
                'transmitted': expected_total,
                'captured': client_count,
                'lost': lost,
                'loss_pct': (lost / expected_total * 100) if expected_total > 0 else 0
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
        description='Analyze UDP PCAP files from UDP echo tests (filters port 21185 by default)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s capture.pcap                    # Analyze UDP echo (port 21185, auto-save)
  %(prog)s capture.pcap -o results.csv     # Save to specific file
  %(prog)s capture.pcap --port 12345       # Use different UDP port
  %(prog)s capture.pcap --min-packets 50   # Require 50+ packets per size
        """
    )
    
    parser.add_argument('pcap_file', help='PCAP file to analyze')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output CSV file (default: auto-numbered udp_analysis_N.csv)')
    parser.add_argument('--port', type=int, default=21185,
                       help='Filter by specific UDP port (default: 21185 for UDP echo)')
    parser.add_argument('--min-packets', type=int, default=10,
                       help='Minimum packets per size to analyze (default: 10, filters noise)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pcap_file):
        print(f"Error: File '{args.pcap_file}' not found")
        sys.exit(1)
    
    # Analyze the PCAP file
    results = analyze_udp_pcap(args.pcap_file, args.port, args.min_packets)
    
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
