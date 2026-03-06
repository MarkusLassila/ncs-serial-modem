#!/usr/bin/env python3
"""
PCAP Analyzer for UDP Echo Test with TCP Traffic Sweep - Data Loss Assessment
Analyzes UDP packets grouped by batches to assess trace data completeness

Since PCAP is generated from incomplete trace data, missing packets indicate
gaps in the trace rather than actual network loss. This tool helps assess
trace quality by calculating data loss percentage in each batch.

Each batch represents one test iteration with a specific TCP data size.
Sequences are continuous (1-200, 201-400, etc.) across all batches.

Defaults:
- Filters UDP port 21185 (UDP echo port)
- Batch size: 200 packets per test
- TCP sweep: starts at 10 KB, increments by 5 KB
- Shows combined data loss percentage (client + server) per batch
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


def save_results(filename, results_by_batch):
    """Save analysis results to CSV file"""
    with open(filename, 'w', newline='') as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(['Batch', 'TCP_Data_KB', 'Seq_Start', 'Seq_End', 'Total_Expected', 
                        'Total_Missing', 'Loss_Pct', 'Client_Missing', 'Client_Loss_Pct',
                        'Server_Missing', 'Server_Loss_Pct',
                        'Missing_Seqs', 'Delay_ms', 'Duration_s', 'Avg_RTT_ms'])
        
        # Sort by batch number
        for batch_num in sorted(results_by_batch.keys()):
            stats = results_by_batch[batch_num]
            missing_seqs_str = ','.join(map(str, stats['missing_seqs'][:20]))  # First 20
            if len(stats['missing_seqs']) > 20:
                missing_seqs_str += '...'
            
            writer.writerow([
                batch_num,
                stats['tcp_data_kb'],
                stats['seq_start'],
                stats['seq_end'],
                stats['expected'],
                stats['total_missing'],
                f"{stats['loss_pct']:.2f}",
                stats['client_missing'],
                f"{stats['client_loss_pct']:.2f}",
                stats['server_missing'],
                f"{stats['server_loss_pct']:.2f}",
                missing_seqs_str,
                stats['delay_ms'] if stats['delay_ms'] is not None else '',
                f"{stats['duration']:.2f}",
                f"{stats.get('avg_rtt', 0):.2f}"
            ])
    
    print(f"\nResults saved to: {filename}")


def analyze_udp_pcap(pcap_file, target_port=None, min_packets=10, batch_size=200, tcp_start_kb=10, tcp_step_kb=5):
    """Analyze PCAP file for UDP packets, grouping by batch to correlate with TCP data size"""
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
    results_by_batch = {}
    
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
        
        # Group packets by batch
        # Each batch has batch_size sequence numbers (e.g., 1-200, 201-400, etc.)
        client_seqs = [p['seq'] for p in client_pkts]
        server_seqs = [p['seq'] for p in server_pkts]
        
        if not client_seqs:
            print("No client sequences found")
            continue
        
        min_seq_all = min(client_seqs)
        max_seq_all = max(client_seqs)
        
        # Determine batches
        batches = defaultdict(lambda: {'client': [], 'server': []})
        
        for p in client_pkts:
            batch_num = (p['seq'] - 1) // batch_size + 1
            batches[batch_num]['client'].append(p)
        
        for p in server_pkts:
            batch_num = (p['seq'] - 1) // batch_size + 1
            batches[batch_num]['server'].append(p)
        
        print(f"Overall sequence range: {min_seq_all} to {max_seq_all}")
        print(f"Detected {len(batches)} batch(es) of ~{batch_size} packets each")
        print()
        
        # Analyze each batch
        for batch_num in sorted(batches.keys()):
            batch_data = batches[batch_num]
            batch_client_pkts = batch_data['client']
            batch_server_pkts = batch_data['server']
            
            if not batch_client_pkts:
                continue
            
            # Calculate TCP data size for this batch
            tcp_data_kb = tcp_start_kb + (batch_num - 1) * tcp_step_kb
            
            # Get sequence range for this batch
            batch_seqs_client = set(p['seq'] for p in batch_client_pkts)
            batch_seqs_server = set(p['seq'] for p in batch_server_pkts)
            
            seq_start = (batch_num - 1) * batch_size + 1
            seq_end = batch_num * batch_size
            expected_seqs = set(range(seq_start, seq_end + 1))
            
            # Find missing sequences (gaps in trace)
            missing_client = sorted(expected_seqs - batch_seqs_client)
            missing_server = sorted(expected_seqs - batch_seqs_server)
            
            # Count packets
            client_count = len(batch_client_pkts)
            server_count = len(batch_server_pkts)
            
            # Calculate combined data loss percentage (trace quality metric)
            total_missing = len(missing_client) + len(missing_server)
            total_expected = batch_size * 2  # Client + Server
            loss_pct = (total_missing / total_expected) * 100 if total_expected > 0 else 0
            client_loss_pct = (len(missing_client) / batch_size) * 100
            server_loss_pct = (len(missing_server) / batch_size) * 100
            
            # Calculate timing and RTT
            timestamps = [p['timestamp'] for p in batch_client_pkts]
            if timestamps:
                duration = float(max(timestamps) - min(timestamps))
            else:
                duration = 0
            
            # Calculate RTT if we have both client and server packets
            avg_rtt = 0
            if batch_server_pkts:
                # Match up packets by sequence to calculate RTT
                client_times = {p['seq']: p['timestamp'] for p in batch_client_pkts}
                server_times = {p['seq']: p['timestamp'] for p in batch_server_pkts}
                rtts = []
                for seq in client_times:
                    if seq in server_times:
                        rtt_ms = float(server_times[seq] - client_times[seq]) * 1000
                        if 0 < rtt_ms < 10000:  # Sanity check: RTT should be < 10s
                            rtts.append(rtt_ms)
                if rtts:
                    avg_rtt = sum(rtts) / len(rtts)
            
            # Display batch info with data loss emphasis
            print(f"  Batch {batch_num}: TCP {tcp_data_kb} KB | Seq {seq_start}-{seq_end} | "
                  f"Missing: {total_missing}/{total_expected} packets ({loss_pct:.1f}% loss) | "
                  f"RTT: {avg_rtt:.1f}ms")
            
            # Show missing sequences if any (helpful for debugging trace issues)
            if total_missing > 0 and total_missing <= 20:
                missing_all = sorted(set(missing_client + missing_server))
                print(f"    Missing seqs: {missing_all}")
            elif total_missing > 0:
                missing_all = sorted(set(missing_client + missing_server))
                print(f"    Missing seqs: {missing_all[:10]}...{missing_all[-10:]} ({total_missing} total)")
            
            stats = {
                'batch': batch_num,
                'tcp_data_kb': tcp_data_kb,
                'seq_start': seq_start,
                'seq_end': seq_end,
                'expected': total_expected,
                'client_captured': client_count,
                'client_missing': len(missing_client),
                'server_captured': server_count,
                'server_missing': len(missing_server),
                'total_missing': total_missing,
                'loss_pct': loss_pct,
                'client_loss_pct': client_loss_pct,
                'server_loss_pct': server_loss_pct,
                'missing_seqs': sorted(set(missing_client + missing_server)),
                'packet_size': packet_size,
                'delay_ms': delay_info.get(packet_size),
                'duration': duration,
                'avg_rtt': avg_rtt
            }
            
            results_by_batch[batch_num] = stats
        
        print()
    
    return results_by_batch


def main():
    parser = argparse.ArgumentParser(
        description='Analyze UDP+TCP sweep test PCAP - groups UDP by batch to correlate with TCP data size',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s capture.pcap                                    # Default: 200 pkts/batch, TCP 10-50KB in 5KB steps
  %(prog)s capture.pcap --batch-size 200                   # Explicitly set batch size
  %(prog)s capture.pcap --tcp-start 10 --tcp-step 5        # TCP starts at 10KB, increments by 5KB
  %(prog)s capture.pcap --tcp-start 15 --tcp-step 10       # TCP: 15, 25, 35, 45 KB
  %(prog)s capture.pcap -o results.csv                     # Save to specific file
  %(prog)s capture.pcap --port 12345                       # Use different UDP port
        """
    )
    
    parser.add_argument('pcap_file', help='PCAP file to analyze')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output CSV file (default: auto-numbered udp_analysis_N.csv)')
    parser.add_argument('--port', type=int, default=21185,
                       help='Filter by specific UDP port (default: 21185 for UDP echo)')
    parser.add_argument('--min-packets', type=int, default=10,
                       help='Minimum packets per size to analyze (default: 10, filters noise)')
    parser.add_argument('--batch-size', type=int, default=200,
                       help='UDP packets per batch/test (default: 200)')
    parser.add_argument('--tcp-start', type=int, default=10,
                       help='Starting TCP data size in KB (default: 10)')
    parser.add_argument('--tcp-step', type=int, default=5,
                       help='TCP data size increment in KB (default: 5)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.pcap_file):
        print(f"Error: File '{args.pcap_file}' not found")
        sys.exit(1)
    
    # Analyze the PCAP file
    results = analyze_udp_pcap(args.pcap_file, args.port, args.min_packets, 
                               args.batch_size, args.tcp_start, args.tcp_step)
    
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
    print(f"\n{'#'*80}")
    print(f"TRACE QUALITY SUMMARY - UDP Data Loss by Batch")
    print(f"{'#'*80}")
    print(f"{'Batch':<8} {'TCP(KB)':<10} {'Missing':<12} {'Loss%':<10} {'RTT(ms)':<10}")
    print(f"{'-'*80}")
    for batch_num in sorted(results.keys()):
        r = results[batch_num]
        print(f"{batch_num:<8} {r['tcp_data_kb']:<10} {r['total_missing']:<12} "
              f"{r['loss_pct']:<10.2f} {r.get('avg_rtt', 0):<10.2f}")
    
    # Calculate overall trace quality
    total_expected = sum(r['expected'] for r in results.values())
    total_missing = sum(r['total_missing'] for r in results.values())
    overall_loss_pct = (total_missing / total_expected * 100) if total_expected > 0 else 0
    
    print(f"{'-'*80}")
    print(f"{'OVERALL':<8} {'---':<10} {total_missing:<12} {overall_loss_pct:<10.2f}")
    print(f"\nTrace Quality: {100-overall_loss_pct:.2f}% complete")
    print(f"Total packets expected: {total_expected:,}")
    print(f"Total packets missing: {total_missing:,}")
    print(f"{'#'*80}\n")


if __name__ == "__main__":
    main()
