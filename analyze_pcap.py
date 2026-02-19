#!/usr/bin/env python3
"""
PCAP Analyzer for TCP Echo Test
Analyzes TCP connections to calculate data loss based on ACK vs actual captured data
"""

import sys
import argparse
from collections import defaultdict
from scapy.all import rdpcap, TCP, IP
from datetime import datetime

class TCPConnection:
    """Track a single TCP connection"""
    def __init__(self, conn_id):
        self.conn_id = conn_id
        self.syn_time = None
        self.fin_time = None
        self.last_packet_time = None
        self.delay_ms = None  # Delay extracted from first packet
        
        # Track sequence/ack numbers for both directions
        self.client_initial_seq = None
        self.server_initial_seq = None
        self.client_max_ack = None  # Max ACK from client (acknowledging server data)
        self.server_max_ack = None  # Max ACK from server (acknowledging client data)
        
        # Track actual data seen in packets
        self.client_data_bytes = 0  # Data sent by client (captured)
        self.server_data_bytes = 0  # Data sent by server (captured)
        self.first_data_seen = False  # Track if we've seen first data packet
        
        self.client_addr = None
        self.server_addr = None
        
    def add_packet(self, pkt, timestamp):
        """Process a packet for this connection"""
        if not pkt.haslayer(TCP):
            return
            
        tcp = pkt[TCP]
        ip = pkt[IP]
        
        # Determine direction
        is_client_to_server = (ip.src, tcp.sport) == self.client_addr
        
        # Track timing
        if self.syn_time is None and tcp.flags & 0x02:  # SYN flag
            self.syn_time = timestamp
            
        if tcp.flags & 0x01:  # FIN flag
            self.fin_time = timestamp
            
        self.last_packet_time = timestamp
        
        # Track initial sequence numbers
        if tcp.flags & 0x02:  # SYN
            if is_client_to_server and self.client_initial_seq is None:
                self.client_initial_seq = tcp.seq
            elif not is_client_to_server and self.server_initial_seq is None:
                self.server_initial_seq = tcp.seq
        
        # Track ACK numbers (what has been acknowledged)
        if tcp.flags & 0x10:  # ACK flag
            if is_client_to_server:
                # Client ACKing server data
                if self.client_max_ack is None or tcp.ack > self.client_max_ack:
                    self.client_max_ack = tcp.ack
            else:
                # Server ACKing client data
                if self.server_max_ack is None or tcp.ack > self.server_max_ack:
                    self.server_max_ack = tcp.ack
        
        # Track actual payload data
        payload_len = len(tcp.payload)
        if payload_len > 0:
            # Extract delay from first data packet (client->server)
            if not self.first_data_seen and is_client_to_server and self.delay_ms is None:
                self.first_data_seen = True
                # Try to extract delay_ms from packet
                # Format: [SEQ (4)][TIMESTAMP (8)][DELAY_MS (4)][DELAY=Xms ...]
                try:
                    payload = bytes(tcp.payload)
                    if len(payload) >= 16:
                        # Extract delay_ms field (bytes 12-16)
                        import struct
                        delay_ms = struct.unpack('!I', payload[12:16])[0]
                        # Sanity check: delay should be reasonable (0-1000ms)
                        if 0 <= delay_ms <= 1000:
                            self.delay_ms = delay_ms
                        
                        # Also try to find DELAY= marker as confirmation
                        if b'DELAY=' in payload:
                            marker_idx = payload.find(b'DELAY=')
                            marker_end = payload.find(b'ms', marker_idx)
                            if marker_end > marker_idx:
                                delay_str = payload[marker_idx+6:marker_end].decode('utf-8', errors='ignore')
                                try:
                                    marker_delay = int(delay_str)
                                    # Use marker value if we didn't get a valid one from struct
                                    if self.delay_ms is None or not (0 <= self.delay_ms <= 1000):
                                        self.delay_ms = marker_delay
                                except ValueError:
                                    pass
                except Exception:
                    pass  # If extraction fails, just continue
            
            if is_client_to_server:
                self.client_data_bytes += payload_len
            else:
                self.server_data_bytes += payload_len
    
    def get_stats(self):
        """Calculate statistics for this connection"""
        stats = {
            'conn_id': self.conn_id,
            'client': f"{self.client_addr[0]}:{self.client_addr[1]}",
            'server': f"{self.server_addr[0]}:{self.server_addr[1]}",
        }
        
        # Duration
        if self.syn_time and self.fin_time:
            stats['duration'] = self.fin_time - self.syn_time
        elif self.syn_time and self.last_packet_time:
            stats['duration'] = self.last_packet_time - self.syn_time
        else:
            stats['duration'] = 0
        
        # Calculate transmitted data based on ACK numbers
        # Client -> Server transmission
        if self.server_max_ack and self.client_initial_seq is not None:
            stats['client_transmitted'] = self.server_max_ack - self.client_initial_seq - 1
        else:
            stats['client_transmitted'] = 0
            
        # Server -> Client transmission  
        if self.client_max_ack and self.server_initial_seq is not None:
            stats['server_transmitted'] = self.client_max_ack - self.server_initial_seq - 1
        else:
            stats['server_transmitted'] = 0
        
        # Actual captured data
        stats['client_captured'] = self.client_data_bytes
        stats['server_captured'] = self.server_data_bytes
        
        # Calculate loss
        stats['client_loss'] = max(0, stats['client_transmitted'] - stats['client_captured'])
        stats['server_loss'] = max(0, stats['server_transmitted'] - stats['server_captured'])
        
        # Loss percentages
        if stats['client_transmitted'] > 0:
            stats['client_loss_pct'] = (stats['client_loss'] / stats['client_transmitted']) * 100
        else:
            stats['client_loss_pct'] = 0
            
        if stats['server_transmitted'] > 0:
            stats['server_loss_pct'] = (stats['server_loss'] / stats['server_transmitted']) * 100
        else:
            stats['server_loss_pct'] = 0
        
        # Total
        stats['total_transmitted'] = stats['client_transmitted'] + stats['server_transmitted']
        stats['total_captured'] = stats['client_captured'] + stats['server_captured']
        stats['total_loss'] = stats['client_loss'] + stats['server_loss']
        
        if stats['total_transmitted'] > 0:
            stats['total_loss_pct'] = (stats['total_loss'] / stats['total_transmitted']) * 100
        else:
            stats['total_loss_pct'] = 0
        
        # Add delay information
        stats['delay_ms'] = self.delay_ms
        
        return stats


def analyze_pcap(pcap_file, target_port=None):
    """Analyze PCAP file for TCP connections"""
    print(f"Reading {pcap_file}...")
    
    try:
        packets = rdpcap(pcap_file)
    except Exception as e:
        print(f"Error reading pcap: {e}")
        return
    
    print(f"Loaded {len(packets)} packets\n")
    
    # Group packets by connection
    connections = {}
    
    for pkt in packets:
        if not pkt.haslayer(TCP) or not pkt.haslayer(IP):
            continue
        
        tcp = pkt[TCP]
        ip = pkt[IP]
        
        # Filter by port if specified
        if target_port and tcp.sport != target_port and tcp.dport != target_port:
            continue
        
        # Create connection identifier (normalize to always have lower port first for consistency)
        # But track client/server based on SYN direction
        conn_tuple = (
            (ip.src, tcp.sport),
            (ip.dst, tcp.dport)
        )
        
        # Reverse lookup too
        conn_tuple_rev = (
            (ip.dst, tcp.dport),
            (ip.src, tcp.sport)
        )
        
        # Find or create connection
        if conn_tuple in connections:
            conn = connections[conn_tuple]
        elif conn_tuple_rev in connections:
            conn = connections[conn_tuple_rev]
        else:
            # New connection - determine client/server by SYN flag
            conn = TCPConnection(len(connections) + 1)
            
            if tcp.flags & 0x02 and not (tcp.flags & 0x10):  # SYN without ACK = client
                conn.client_addr = (ip.src, tcp.sport)
                conn.server_addr = (ip.dst, tcp.dport)
            else:
                # Default assumption
                conn.client_addr = (ip.src, tcp.sport)
                conn.server_addr = (ip.dst, tcp.dport)
            
            connections[conn_tuple] = conn
        
        # Add packet to connection
        conn.add_packet(pkt, float(pkt.time))
    
    # Print results
    print(f"Found {len(connections)} TCP connection(s)\n")
    print("="*100)
    
    total_all_transmitted = 0
    total_all_captured = 0
    total_all_loss = 0
    all_stats = []  # Collect all stats for summary table
    
    for conn in connections.values():
        stats = conn.get_stats()
        all_stats.append(stats)
        
        print(f"\nConnection #{stats['conn_id']}")
        if stats['delay_ms'] is not None:
            print(f"  Test Delay: {stats['delay_ms']}ms")
        print(f"  Client: {stats['client']}")
        print(f"  Server: {stats['server']}")
        print(f"  Duration: {stats['duration']:.3f} seconds")
        print(f"\n  Client -> Server:")
        print(f"    Transmitted (from ACK): {stats['client_transmitted']:,} bytes")
        print(f"    Captured (in packets):  {stats['client_captured']:,} bytes")
        print(f"    Lost:                   {stats['client_loss']:,} bytes ({stats['client_loss_pct']:.2f}%)")
        print(f"\n  Server -> Client:")
        print(f"    Transmitted (from ACK): {stats['server_transmitted']:,} bytes")
        print(f"    Captured (in packets):  {stats['server_captured']:,} bytes")
        print(f"    Lost:                   {stats['server_loss']:,} bytes ({stats['server_loss_pct']:.2f}%)")
        print(f"\n  Total:")
        print(f"    Transmitted (from ACK): {stats['total_transmitted']:,} bytes")
        print(f"    Captured (in packets):  {stats['total_captured']:,} bytes")
        print(f"    Lost:                   {stats['total_loss']:,} bytes ({stats['total_loss_pct']:.2f}%)")
        print(f"-"*100)
        
        total_all_transmitted += stats['total_transmitted']
        total_all_captured += stats['total_captured']
        total_all_loss += stats['total_loss']
    
    # Overall summary
    if len(connections) > 1:
        print(f"\n{'='*100}")
        print(f"OVERALL SUMMARY (all connections)")
        print(f"  Total Transmitted (from ACK): {total_all_transmitted:,} bytes")
        print(f"  Total Captured (in packets):  {total_all_captured:,} bytes")
        print(f"  Total Lost:                   {total_all_loss:,} bytes", end="")
        if total_all_transmitted > 0:
            overall_pct = (total_all_loss / total_all_transmitted) * 100
            print(f" ({overall_pct:.2f}%)")
        else:
            print()
        
        # Print delay vs loss table if delays are available
        delay_stats = [s for s in all_stats if s['delay_ms'] is not None]
        if delay_stats:
            print(f"\n{'='*100}")
            print(f"DELAY vs DATA LOSS SUMMARY")
            print(f"{'='*100}")
            # Sort by delay descending (highest delay first)
            delay_stats.sort(key=lambda x: x['delay_ms'], reverse=True)
            print(f"{'Delay (ms)':<12} {'Duration (s)':<14} {'Transmitted':<16} {'Captured':<16} {'Lost':<16} {'Loss %':<10}")
            print(f"{'-'*100}")
            for stats in delay_stats:
                print(f"{stats['delay_ms']:<12} "
                      f"{stats['duration']:<14.2f} "
                      f"{stats['total_transmitted']:<16,} "
                      f"{stats['total_captured']:<16,} "
                      f"{stats['total_loss']:<16,} "
                      f"{stats['total_loss_pct']:<10.2f}")
            print(f"{'='*100}")
        
        print(f"{'='*100}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze PCAP file for TCP data loss',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Analyze all TCP connections
  %(prog)s capture.pcap
  
  # Analyze only connections using port 20180
  %(prog)s capture.pcap --port 20180
  
  # Analyze with specific port (matches tcp_echo_test.py default)
  %(prog)s capture.pcap -p 20180
        """
    )
    
    parser.add_argument('pcap_file', help='PCAP file to analyze')
    parser.add_argument('-p', '--port', type=int, default=20180,
                       help='Filter by TCP port (default: 20180, use 0 for all ports)')
    
    args = parser.parse_args()
    
    port_filter = args.port if args.port != 0 else None
    
    if port_filter:
        print(f"Filtering connections using port {port_filter}\n")
    else:
        print("Analyzing all TCP connections\n")
    
    analyze_pcap(args.pcap_file, port_filter)
    

if __name__ == "__main__":
    main()
