#!/usr/bin/env python3
"""
PCAP Analyzer for TCP Downlink Reception - Packet Loss Assessment
Analyzes TCP downlink (server->client) packets to assess reception quality

This analyzer focuses on TCP data received from the server, where the payload
contains a repeated pattern of: data_size + "X" in ASCII (e.g., "51200X51200X...")

The script:
1. Detects batch markers (BTCH) sent to server to identify test batches
2. Analyzes downlink TCP packets from server to client
3. Validates payload pattern matches expected data_size
4. Detects missing data through sequence number gaps
5. Reports packet loss and reception quality per batch

Defaults:
- TCP port 20180 (TCP control/data port)
- Detects BTCH markers in uplink to identify batches
- Analyzes downlink sequence numbers for gaps
- Validates payload pattern integrity
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

def get_next_result_filename(base_name="tcp_recv_analysis", extension="csv"):
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
        writer.writerow(['Batch', 'Expected_KB', 'Received_Bytes', 'Lost_Bytes', 'Loss_Pct',
                        'Packets_Received', 'Seq_Gaps', 'Pattern_Valid', 'Start_Time', 
                        'Duration_s', 'Throughput_kbps'])
        
        # Sort by batch number, filtering out None
        valid_batches = [k for k in results_by_batch.keys() if k is not None]
        for batch_num in sorted(valid_batches):
            stats = results_by_batch[batch_num]
            expected_kb = stats['expected_bytes'] / 1024 if stats['expected_bytes'] else 0
            writer.writerow([
                batch_num,
                f"{expected_kb:.1f}",
                stats['received_bytes'],
                stats['bytes_lost'],
                f"{stats['loss_pct']:.2f}",
                stats['packets_received'],
                stats['seq_gaps'],
                stats['pattern_valid'],
                f"{stats['start_time']:.2f}",
                f"{stats['duration']:.2f}",
                f"{stats['throughput_kbps']:.2f}"
            ])
    
    print(f"\nResults saved to: {filename}")


def validate_payload_pattern(payload_bytes, expected_data_size):
    """Validate that payload contains repeated pattern of 'data_size + X'
    
    Args:
        payload_bytes: The TCP payload as bytes
        expected_data_size: The expected data size value
    
    Returns:
        (is_valid, pattern_description)
    """
    if not payload_bytes:
        return False, "empty"
    
    # Expected pattern
    expected_pattern = f"{expected_data_size}X".encode('ascii')
    pattern_len = len(expected_pattern)
    
    # Check if payload starts with the pattern
    if len(payload_bytes) >= pattern_len:
        if payload_bytes[:pattern_len] == expected_pattern:
            # Verify pattern repeats throughout (sample check)
            # Check at multiple positions
            positions_to_check = [0, len(payload_bytes) // 2, len(payload_bytes) - pattern_len]
            all_match = True
            
            for pos in positions_to_check:
                if pos >= 0 and pos + pattern_len <= len(payload_bytes):
                    # Account for pattern misalignment at boundaries
                    chunk = payload_bytes[pos:pos + pattern_len]
                    # Check if this chunk either matches the pattern or is part of it
                    if expected_pattern not in payload_bytes[max(0, pos - pattern_len):pos + pattern_len * 2]:
                        all_match = False
                        break
            
            return all_match, expected_pattern.decode('ascii')
        else:
            # Try to identify what pattern we got
            try:
                actual_start = payload_bytes[:min(20, len(payload_bytes))].decode('ascii', errors='replace')
                return False, f"unexpected: {actual_start}"
            except:
                return False, "binary/non-ascii"
    
    return False, "too_short"


def analyze_tcp_recv_pcap(pcap_file, target_port=20180, server_ip=None):
    """Analyze PCAP file for TCP downlink reception
    
    Args:
        pcap_file: Path to pcap file
        target_port: TCP port to filter (default: 20180)
        server_ip: Optional server IP to identify direction. If None, auto-detect from first packet
    """
    print(f"Reading {pcap_file}...")
    
    try:
        packets = rdpcap(pcap_file)
    except Exception as e:
        print(f"Error reading pcap: {e}")
        return None
    
    print(f"Loaded {len(packets)} packets\n")
    print(f"Filtering for TCP port {target_port}")
    print(f"Analyzing downlink (server->client) reception\n")
    
    # Collect TCP packets and detect batch markers
    tcp_packets = []
    tcp_packet_count = 0
    batch_timestamps = []  # List of (timestamp, batch_num, data_size)
    
    # Auto-detect server IP from first TCP packet if not provided
    detected_server_ip = server_ip
    
    for pkt in packets:
        if not pkt.haslayer(TCP) or not pkt.haslayer(IP):
            continue
        
        tcp = pkt[TCP]
        ip = pkt[IP]
        
        # Filter by port
        if tcp.sport != target_port and tcp.dport != target_port:
            continue
        
        tcp_packet_count += 1
        
        # Auto-detect server IP from first packet with port
        if detected_server_ip is None:
            if tcp.sport == target_port:
                detected_server_ip = ip.src
                print(f"Auto-detected server IP: {detected_server_ip}")
        
        # Determine direction
        if detected_server_ip:
            if ip.src == detected_server_ip:
                direction = 'from_server'  # Downlink
            else:
                direction = 'to_server'    # Uplink
        else:
            # Fallback to port-based detection
            if tcp.dport == target_port:
                direction = 'to_server'
            else:
                direction = 'from_server'
        
        # Check for batch marker in uplink payload (client->server packets)
        if direction == 'to_server' and len(tcp.payload) >= 12:
            payload_bytes = bytes(tcp.payload)
            if payload_bytes[:4] == b'BTCH':
                # Extract batch number and data size
                batch_num, data_size = struct.unpack('!II', payload_bytes[4:12])
                batch_timestamps.append((pkt.time, batch_num, data_size))
                # Don't print here - will print after detecting runs
        
        tcp_packets.append({
            'timestamp': pkt.time,
            'src': ip.src,
            'dst': ip.dst,
            'sport': tcp.sport,
            'dport': tcp.dport,
            'seq': tcp.seq,
            'ack': tcp.ack,
            'flags': tcp.flags,
            'payload': bytes(tcp.payload) if tcp.payload else b'',
            'payload_len': len(tcp.payload),
            'direction': direction
        })
    
    print(f"\nFound {tcp_packet_count} TCP packets")
    
    if not tcp_packets:
        print("No TCP packets found\n")
        return None
    
    # Separate uplink and downlink
    uplink_pkts = [p for p in tcp_packets if p['direction'] == 'to_server']
    downlink_pkts = [p for p in tcp_packets if p['direction'] == 'from_server']
    
    print(f"Uplink packets (client->server): {len(uplink_pkts)}")
    print(f"Downlink packets (server->client): {len(downlink_pkts)}")
    print(f"Found {len(batch_timestamps)} batch marker(s)\n")
    
    if not downlink_pkts:
        print("No downlink TCP data found\n")
        return None
    
    if not batch_timestamps:
        print("Warning: No batch markers found. Cannot determine expected data size.")
        print("Continuing with sequence-based analysis only.\n")
    
    # Get time range
    all_times = [p['timestamp'] for p in tcp_packets]
    start_time = min(all_times)
    end_time = max(all_times)
    total_duration = end_time - start_time
    
    print(f"TCP traffic duration: {total_duration:.2f}s\n")
    
    # Group downlink packets by batch
    # Sort batch timestamps to assign packets to batches
    batch_timestamps.sort(key=lambda x: x[0])
    
    # Create batch windows with start and end times
    # Each batch window: from marker time to next marker time (or end of capture)
    batch_windows = []
    for i, (marker_time, batch_num, data_size) in enumerate(batch_timestamps):
        if i < len(batch_timestamps) - 1:
            # End time is when next batch starts
            window_end = batch_timestamps[i + 1][0]
        else:
            # Last batch: end at capture end + margin
            window_end = end_time + 100  # 100 seconds should be plenty
        
        batch_windows.append({
            'batch_num': batch_num,
            'expected_size': data_size,
            'start_time': marker_time,
            'end_time': window_end
        })
        
        window_duration = window_end - marker_time
        print(f"Batch {batch_num} window: {marker_time:.3f} -> {window_end:.3f} ({window_duration:.2f}s), expect {data_size/1024:.0f} KB")
    
    print()  # Blank line after windows
    
    # Assign packets to batch windows
    batches = defaultdict(list)
    unassigned_count = 0
    
    for pkt in downlink_pkts:
        # Find which batch window this packet falls into
        assigned = False
        for window in batch_windows:
            if window['start_time'] <= pkt['timestamp'] < window['end_time']:
                batches[window['batch_num']].append({
                    'pkt': pkt,
                    'expected_size': window['expected_size']
                })
                assigned = True
                break
        
        if not assigned:
            # Packet doesn't fall in any batch window - assign to batch 0 (unknown)
            batches[0].append({
                'pkt': pkt,
                'expected_size': None
            })
            unassigned_count += 1
    
    if unassigned_count > 0:
        print(f"Warning: {unassigned_count} downlink packets could not be assigned to any batch")
    print(f"Grouped downlink packets into {len(batches)} batch(es)")
    
    # Show initial grouping stats
    print("\nInitial packet assignment:")
    for batch_num in sorted(batches.keys()):
        batch_data = batches[batch_num]
        total_bytes = sum(item['pkt']['payload_len'] for item in batch_data)
        total_pkts = len(batch_data)
        expected = batch_data[0]['expected_size'] if batch_data else 0
        if expected:
            print(f"  Batch {batch_num}: {total_pkts} packets, {total_bytes:,} bytes (expected {expected:,} bytes, {expected/1024:.0f} KB)")
        else:
            print(f"  Batch {batch_num}: {total_pkts} packets, {total_bytes:,} bytes (no expected size)")
    print()
    
    results_by_batch = {}
    
    for batch_num in sorted(batches.keys()):
        batch_data = batches[batch_num]
        
        if not batch_data:
            continue
        
        # Extract expected size (should be same for all packets in batch)
        expected_size = batch_data[0]['expected_size']
        
        # Track sequence numbers and data
        seq_data = []  # List of (seq, payload_len, timestamp, payload_bytes)
        bytes_received = 0
        packets_with_data = 0
        pattern_validations = []
        
        for item in batch_data:
            pkt = item['pkt']
            payload_len = pkt['payload_len']
            
            # Count data bytes (skip pure ACKs)
            if payload_len > 0:
                bytes_received += payload_len
                packets_with_data += 1
                seq_data.append((pkt['seq'], payload_len, pkt['timestamp'], pkt['payload']))
                
                # Validate payload pattern if we know expected size
                if expected_size and payload_len >= 6:  # At least enough for pattern
                    is_valid, pattern_desc = validate_payload_pattern(pkt['payload'], expected_size)
                    pattern_validations.append(is_valid)
        
        if packets_with_data == 0:
            continue
        
        # Analyze sequence number gaps
        seq_data.sort(key=lambda x: x[0])  # Sort by sequence number
        
        seq_gaps = 0
        gap_details = []
        
        # Normalize sequence numbers to detect gaps in THIS flow
        # TCP uses absolute sequence numbers, so we need to work with relative offsets
        if seq_data:
            base_seq = seq_data[0][0]  # First sequence number in this batch
            
            expected_next_seq = None
            
            for seq, payload_len, ts, payload in seq_data:
                if expected_next_seq is not None:
                    if seq > expected_next_seq:
                        # Gap detected: missing data
                        gap_size = seq - expected_next_seq
                        seq_gaps += 1
                        gap_details.append((expected_next_seq, seq, gap_size))
                    elif seq < expected_next_seq:
                        # Retransmission or out-of-order - don't count as gap
                        # Just update expected if this packet extends beyond current expectation
                        if seq + payload_len > expected_next_seq:
                            expected_next_seq = seq + payload_len
                        continue
                
                expected_next_seq = seq + payload_len
        
        # Calculate loss - use simple comparison of expected vs received
        if expected_size:
            # We know the expected size from batch marker
            if bytes_received > expected_size:
                # Received more than expected - might be retransmissions, protocol overhead, or window issue
                bytes_lost = 0
                loss_pct = 0
                # Note: bytes_received includes all TCP payload, which might include retransmissions
            else:
                bytes_lost = expected_size - bytes_received
                loss_pct = (bytes_lost / expected_size * 100)
            total_expected = expected_size
        else:
            # No expected size - cannot accurately calculate loss
            bytes_lost = 0
            total_expected = bytes_received
            loss_pct = 0
        
        # Pattern validation summary
        if pattern_validations:
            pattern_valid_pct = (sum(pattern_validations) / len(pattern_validations)) * 100
            pattern_valid_str = f"{pattern_valid_pct:.0f}%"
        else:
            pattern_valid_str = "N/A"
        
        # Time analysis
        batch_times = [item['pkt']['timestamp'] for item in batch_data]
        batch_start = min(batch_times)
        batch_end = max(batch_times)
        batch_duration = batch_end - batch_start
        
        if batch_duration > 0:
            throughput_kbps = (bytes_received * 8 / 1000) / float(batch_duration)
        else:
            throughput_kbps = 0
        
        # Report
        if expected_size:
            if bytes_received > expected_size:
                overflow = bytes_received - expected_size
                print(f"Batch {batch_num}: Expected {expected_size/1024:.0f} KB | "
                      f"Received {bytes_received:,} bytes (+{overflow:,} overflow) | Lost {bytes_lost:,} bytes ({loss_pct:.1f}%)")
                print(f"  WARNING: Received more than expected (possible retransmissions/protocol overhead)")
            else:
                print(f"Batch {batch_num}: Expected {expected_size/1024:.0f} KB | "
                      f"Received {bytes_received:,} bytes | Lost {bytes_lost:,} bytes ({loss_pct:.1f}%)")
        else:
            print(f"Batch {batch_num}: Received {bytes_received:,} bytes | "
                  f"Missing {bytes_lost:,} bytes ({loss_pct:.1f}%) [no marker]")
        
        print(f"  Packets: {packets_with_data} | Seq gaps: {seq_gaps} | "
              f"Pattern valid: {pattern_valid_str} | Throughput: {throughput_kbps:.1f} kbps")
        
        if gap_details and len(gap_details) <= 10:
            print(f"  Sequence gaps:")
            for gap_start, gap_end, gap_size in gap_details:
                print(f"    {gap_start} -> {gap_end} (missing {gap_size} bytes)")
        elif len(gap_details) > 10:
            print(f"  Sequence gaps: {seq_gaps} gaps (showing first 5):")
            for gap_start, gap_end, gap_size in gap_details[:5]:
                print(f"    {gap_start} -> {gap_end} (missing {gap_size} bytes)")
        
        stats = {
            'batch': batch_num,
            'expected_bytes': expected_size if expected_size else 0,
            'received_bytes': bytes_received,
            'bytes_lost': bytes_lost,
            'loss_pct': loss_pct,
            'packets_received': packets_with_data,
            'seq_gaps': seq_gaps,
            'pattern_valid': pattern_valid_str,
            'start_time': float(batch_start - start_time),
            'duration': float(batch_duration),
            'throughput_kbps': throughput_kbps
        }
        
        results_by_batch[batch_num] = stats
    
    return results_by_batch


def main():
    parser = argparse.ArgumentParser(
        description='Analyze TCP downlink reception - assess packet loss and data integrity',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s capture.pcap                          # Default: TCP port 20180
  %(prog)s capture.pcap --port 8080              # Use different TCP port
  %(prog)s capture.pcap --server-ip 1.2.3.4      # Specify server IP explicitly
  %(prog)s capture.pcap -o tcp_recv_results.csv  # Save to specific file

This tool analyzes TCP downlink (server->client) reception quality by:
- Detecting batch markers (BTCH) in uplink to identify test batches
- Analyzing sequence numbers for gaps indicating packet loss
- Validating payload pattern (data_size + "X" repeated)
- Calculating reception quality and throughput per batch
        """
    )
    
    parser.add_argument('pcap_file', help='PCAP file to analyze')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output CSV file (default: auto-numbered tcp_recv_analysis_N.csv)')
    parser.add_argument('--port', type=int, default=20180,
                       help='TCP port to filter (default: 20180)')
    parser.add_argument('--server-ip', type=str, default=None,
                       help='Server IP address (auto-detected if not specified)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pcap_file):
        print(f"Error: File '{args.pcap_file}' not found")
        sys.exit(1)
    
    # Analyze the PCAP file
    results = analyze_tcp_recv_pcap(args.pcap_file, args.port, args.server_ip)
    
    if not results:
        print("No results to save.")
        sys.exit(1)
    
    # Determine output filename
    if args.output:
        output_file = args.output
    else:
        output_file = get_next_result_filename("tcp_recv_analysis", "csv")
    
    # Save results
    save_results(output_file, results)
    
    # Print summary
    print(f"\n{'#'*80}")
    print(f"TCP DOWNLINK RECEPTION SUMMARY - Packet Loss Analysis")
    print(f"{'#'*80}")
    print(f"{'Batch':<8} {'Expected(KB)':<14} {'Received':<12} {'Lost':<12} {'Loss%':<10} {'Gaps':<8}")
    print(f"{'-'*80}")
    
    total_expected = 0
    total_received = 0
    total_lost = 0
    total_gaps = 0
    
    # Filter out None batches and sort
    valid_batches = [k for k in results.keys() if k is not None]
    for batch_num in sorted(valid_batches):
        r = results[batch_num]
        expected_kb = r['expected_bytes'] / 1024 if r['expected_bytes'] else 0
        print(f"{batch_num:<8} {expected_kb:<14.1f} {r['received_bytes']:<12,} "
              f"{r['bytes_lost']:<12,} {r['loss_pct']:<10.2f} {r['seq_gaps']:<8}")
        total_expected += r['expected_bytes'] if r['expected_bytes'] else 0
        total_received += r['received_bytes']
        total_lost += r['bytes_lost']
        total_gaps += r['seq_gaps']
    
    print(f"{'-'*80}")
    overall_loss_pct = (total_lost / total_expected * 100) if total_expected > 0 else 0
    print(f"{'TOTAL':<8} {total_expected/1024:<14.1f} {total_received:<12,} "
          f"{total_lost:<12,} {overall_loss_pct:<10.2f} {total_gaps:<8}")
    print(f"\nOverall Reception Quality: {100 - overall_loss_pct:.2f}% ({total_received:,}/{total_expected:,} bytes)")
    print(f"Total data lost: {total_lost:,} bytes ({total_lost/1024:.1f} KB)")
    print(f"Total sequence gaps: {total_gaps}")
    print(f"{'#'*80}\n")


if __name__ == "__main__":
    main()
