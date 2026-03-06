#!/usr/bin/env python3
"""
PCAP Analyzer for TCP Traffic - Trace Quality Assessment
Analyzes TCP packets to assess trace data completeness

Since PCAP is generated from incomplete trace data, gaps in TCP sequence
numbers and missing segments indicate trace quality issues rather than
actual network loss.

Defaults:
- Filters TCP port 20180 (TCP control/data port)
- Detects sequence number gaps (missing trace data)
- Analyzes data completeness per batch
- Groups by time windows to correlate with UDP test batches
"""

import sys
import os
import glob
import argparse
import csv
import struct
from collections import defaultdict
from scapy.all import rdpcap, TCP, IP
from datetime import datetime

def get_next_result_filename(base_name="tcp_analysis", extension="csv"):
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


def save_results(filename, results_by_batch):
    """Save analysis results to CSV file"""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Batch', 'Expected_KB', 'Captured_Bytes', 'Lost_Bytes', 'Loss_Pct',
                        'Packets_Captured', 'Start_Time', 'Duration_s', 'Throughput_kbps'])
        
        # Sort by batch number, filtering out None
        valid_batches = [k for k in results_by_batch.keys() if k is not None]
        for batch_num in sorted(valid_batches):
            stats = results_by_batch[batch_num]
            expected_kb = stats['expected_bytes'] / 1024 if stats['expected_bytes'] else 0
            writer.writerow([
                batch_num,
                f"{expected_kb:.1f}",
                stats['captured_bytes'],
                stats['bytes_lost'],
                f"{stats['loss_pct']:.2f}",
                stats['packets_captured'],
                f"{stats['start_time']:.2f}",
                f"{stats['duration']:.2f}",
                f"{stats['throughput_kbps']:.2f}"
            ])
    
    print(f"\nResults saved to: {filename}")


def analyze_tcp_pcap(pcap_file, target_port=20180, gap_threshold=2.0):
    """Analyze PCAP file for TCP packets
    
    Args:
        pcap_file: Path to pcap file
        target_port: TCP port to filter (default: 20180)
        gap_threshold: Time gap in seconds to separate batches (default: 2.0s)
    """
    print(f"Reading {pcap_file}...")
    
    try:
        packets = rdpcap(pcap_file)
    except Exception as e:
        print(f"Error reading pcap: {e}")
        return None
    
    print(f"Loaded {len(packets)} packets\n")
    print(f"Filtering for TCP port {target_port}")
    print(f"Detecting batch markers in TCP payload\n")
    
    # Collect TCP packets and detect batch markers
    tcp_packets = []
    tcp_packet_count = 0
    batch_markers = {}  # seq_num -> (batch_num, expected_data_size)
    
    for pkt in packets:
        if not pkt.haslayer(TCP) or not pkt.haslayer(IP):
            continue
        
        tcp = pkt[TCP]
        ip = pkt[IP]
        
        # Filter by port
        if tcp.sport != target_port and tcp.dport != target_port:
            continue
        
        tcp_packet_count += 1
        
        # Determine direction
        if tcp.dport == target_port:
            direction = 'to_server'
        else:
            direction = 'from_server'
        
        # Check for batch marker in payload (client->server packets)
        if direction == 'to_server' and len(tcp.payload) >= 12:
            payload_bytes = bytes(tcp.payload)
            if payload_bytes[:4] == b'BTCH':
                # Extract batch number and data size
                batch_num, data_size = struct.unpack('!II', payload_bytes[4:12])
                batch_markers[tcp.seq] = (batch_num, data_size)
                print(f"Found batch marker: batch {batch_num}, expected {data_size} bytes at seq {tcp.seq}")
        
        tcp_packets.append({
            'timestamp': pkt.time,
            'src': ip.src,
            'dst': ip.dst,
            'sport': tcp.sport,
            'dport': tcp.dport,
            'seq': tcp.seq,
            'ack': tcp.ack,
            'flags': tcp.flags,
            'payload_len': len(tcp.payload),
            'direction': direction
        })
    
    print(f"Found {tcp_packet_count} TCP packets")
    
    if not tcp_packets:
        print("No TCP packets found\n")
        return None
    
    # Separate client->server (uplink) and server->client (downlink)
    uplink_pkts = [p for p in tcp_packets if p['direction'] == 'to_server']
    downlink_pkts = [p for p in tcp_packets if p['direction'] == 'from_server']
    
    print(f"Uplink packets (client->server): {len(uplink_pkts)}")
    print(f"Downlink packets (server->client): {len(downlink_pkts)}\n")
    
    if not uplink_pkts:
        print("No uplink TCP data found\n")
        return None
    
    # Get time range
    all_times = [p['timestamp'] for p in tcp_packets]
    start_time = min(all_times)
    end_time = max(all_times)
    total_duration = end_time - start_time
    
    print(f"TCP traffic duration: {total_duration:.2f}s")
    print(f"Found {len(batch_markers)} batch marker(s)\n")
    
    # Group packets by batch markers
    # Sort uplink packets by sequence number
    uplink_pkts.sort(key=lambda x: x['seq'])
    
    # Create batches based on markers
    batches = []
    current_batch = []
    current_batch_num = None
    current_expected_size = None
    marker_seqs = sorted(batch_markers.keys())
    
    for pkt in uplink_pkts:
        # Check if this packet starts a new batch
        if pkt['seq'] in batch_markers:
            # Save previous batch
            if current_batch:
                batches.append({
                    'batch_num': current_batch_num,
                    'expected_size': current_expected_size,
                    'packets': current_batch
                })
            # Start new batch
            current_batch = [pkt]
            current_batch_num, current_expected_size = batch_markers[pkt['seq']]
        else:
            current_batch.append(pkt)
    
    # Add last batch
    if current_batch:
        batches.append({
            'batch_num': current_batch_num,
            'expected_size': current_expected_size,
            'packets': current_batch
        })
    
    print(f"Grouped into {len(batches)} batch(es)\n")
    
    results_by_batch = {}
    
    for batch_info in batches:
        batch_num = batch_info['batch_num']
        expected_size = batch_info['expected_size']
        batch_pkts = batch_info['packets']
        
        if not batch_pkts:
            continue
        
        # Track sequence numbers to detect missing data in trace
        seq_data = []  # List of (seq, payload_len) for packets with data
        bytes_captured = 0
        
        # Sort by timestamp
        batch_pkts.sort(key=lambda x: x['timestamp'])
        
        for pkt in batch_pkts:
            payload_len = pkt['payload_len']
            
            # Count data bytes (skip pure ACKs)
            if payload_len > 0:
                bytes_captured += payload_len
                seq_data.append((pkt['seq'], payload_len, pkt['timestamp']))
        
        packets_captured = len(seq_data)
        
        if packets_captured == 0:
            continue
        
        # Calculate missing bytes from sequence number gaps
        seq_data.sort(key=lambda x: x[0])  # Sort by sequence number
        
        missing_bytes = 0
        expected_next_seq = None
        
        for seq, payload_len, _ in seq_data:
            if expected_next_seq is not None:
                if seq > expected_next_seq:
                    # Gap detected: missing data between packets
                    gap_size = seq - expected_next_seq
                    missing_bytes += gap_size
            
            expected_next_seq = seq + payload_len
        
        # Use expected size from marker if available, otherwise estimate from captured data
        if expected_size:
            # We know the expected size - calculate loss directly
            # Note: bytes_captured includes the 12-byte marker, so subtract it
            marker_bytes = 12
            actual_data_captured = bytes_captured - marker_bytes
            total_expected = expected_size + marker_bytes
            
            # Missing = expected - captured + sequence gaps
            missing_bytes_total = (total_expected - bytes_captured)
            bytes_lost = max(0, missing_bytes_total)  # Can't be negative
            loss_pct = (bytes_lost / total_expected * 100) if total_expected > 0 else 0
        else:
            # No marker info - estimate from sequence numbers only
            total_bytes_expected = bytes_captured + missing_bytes
            bytes_lost = missing_bytes
            loss_pct = (bytes_lost / total_bytes_expected * 100) if total_bytes_expected > 0 else 0
        
        batch_duration_actual = max([p['timestamp'] for p in batch_pkts]) - min([p['timestamp'] for p in batch_pkts])
        batch_start_time = min([p['timestamp'] for p in batch_pkts])
        
        if batch_duration_actual > 0:
            throughput_kbps = (bytes_captured * 8 / 1000) / float(batch_duration_actual)
        else:
            throughput_kbps = 0
        
        if expected_size:
            print(f"Batch {batch_num}: Expected {expected_size/1024:.0f} KB | "
                  f"Captured {bytes_captured:,} bytes | Lost {bytes_lost:,} bytes ({loss_pct:.1f}%)")
        else:
            print(f"Batch {batch_num}: Captured {bytes_captured:,} bytes | "
                  f"Estimated lost {bytes_lost:,} bytes ({loss_pct:.1f}%) [no marker]")
        
        stats = {
            'batch': batch_num,
            'expected_bytes': expected_size if expected_size else 0,
            'captured_bytes': bytes_captured,
            'bytes_lost': bytes_lost,
            'loss_pct': loss_pct,
            'packets_captured': packets_captured,
            'start_time': float(batch_start_time - start_time),
            'duration': float(batch_duration_actual),
            'throughput_kbps': throughput_kbps
        }
        
        results_by_batch[batch_num] = stats
    
    return results_by_batch


def main():
    parser = argparse.ArgumentParser(
        description='Analyze TCP PCAP - assess trace data completeness by detecting sequence gaps',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s capture.pcap                        # Default: TCP port 20180, 2s gap threshold
  %(prog)s capture.pcap --port 8080            # Use different TCP port
  %(prog)s capture.pcap --gap-threshold 3.0    # Use 3 second gap to separate batches
  %(prog)s capture.pcap -o tcp_results.csv     # Save to specific file

Note: This tool focuses on trace quality. Sequence gaps indicate missing
trace data rather than network loss. Batches are detected by gaps in traffic.
        """
    )
    
    parser.add_argument('pcap_file', help='PCAP file to analyze')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output CSV file (default: auto-numbered tcp_analysis_N.csv)')
    parser.add_argument('--port', type=int, default=20180,
                       help='TCP port to filter (default: 20180)')
    parser.add_argument('--gap-threshold', type=float, default=2.0,
                       help='Time gap in seconds to separate batches (default: 2.0)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pcap_file):
        print(f"Error: File '{args.pcap_file}' not found")
        sys.exit(1)
    
    # Analyze the PCAP file
    results = analyze_tcp_pcap(args.pcap_file, args.port, args.gap_threshold)
    
    if not results:
        print("No results to save.")
        sys.exit(1)
    
    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        output_file = get_next_result_filename("tcp_analysis", "csv")
    
    # Save results
    save_results(output_file, results)
    
    # Print summary
    print(f"\n{'#'*80}")
    print(f"TRACE QUALITY SUMMARY - TCP Data Loss Analysis")
    print(f"{'#'*80}")
    print(f"{'Batch':<8} {'Expected(KB)':<14} {'Captured':<12} {'Lost':<12} {'Loss%':<10}")
    print(f"{'-'*80}")
    
    total_expected = 0
    total_captured = 0
    total_lost = 0
    
    # Filter out None batches and sort
    valid_batches = [k for k in results.keys() if k is not None]
    for batch_num in sorted(valid_batches):
        r = results[batch_num]
        expected_kb = r['expected_bytes'] / 1024 if r['expected_bytes'] else 0
        print(f"{batch_num:<8} {expected_kb:<14.1f} {r['captured_bytes']:<12,} "
              f"{r['bytes_lost']:<12,} {r['loss_pct']:<10.2f}")
        total_expected += r['expected_bytes'] if r['expected_bytes'] else 0
        total_captured += r['captured_bytes']
        total_lost += r['bytes_lost']
    
    print(f"{'-'*80}")
    overall_loss_pct = (total_lost / total_expected * 100) if total_expected > 0 else 0
    print(f"{'TOTAL':<8} {total_expected/1024:<14.1f} {total_captured:<12,} "
          f"{total_lost:<12,} {overall_loss_pct:<10.2f}")
    print(f"\nOverall Trace Quality: {100 - overall_loss_pct:.2f}% complete")
    print(f"Total data lost from trace: {total_lost:,} bytes ({total_lost/1024:.1f} KB)")
    print(f"{'#'*80}\n")


if __name__ == "__main__":
    main()
