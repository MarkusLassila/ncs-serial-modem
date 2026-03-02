#!/usr/bin/env python3
"""
Plot Loss % as a function of Packet Size (bytes) for UDP tests
"""

import matplotlib.pyplot as plt
import numpy as np
import csv
import sys
import argparse
import os
import glob

def get_next_plot_filename(base_name="udp_loss_vs_size", extension="png"):
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

def load_run_from_csv(filename):
    """Load UDP test data from CSV file"""
    packet_sizes = []
    loss_percent = []
    
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            packet_sizes.append(float(row['Packet_Size']))
            loss_percent.append(float(row['Loss_pct']))
    
    return packet_sizes, loss_percent

def plot_from_files(files, output_file=None):
    """Plot data from multiple CSV files"""
    styles = [
        {'color': 'r', 'marker': 'o'},
        {'color': 'b', 'marker': 's'},
        {'color': 'g', 'marker': '^'},
        {'color': 'm', 'marker': 'd'},
        {'color': 'c', 'marker': 'v'},
        {'color': 'y', 'marker': 'p'},
        {'color': 'k', 'marker': '*'},
        {'color': 'orange', 'marker': 'h'},
        {'color': 'purple', 'marker': 'x'},
        {'color': 'brown', 'marker': '+'},
    ]
    
    plt.figure(figsize=(14, 8))
    
    max_loss = 0
    data_loaded = False
    
    for idx, filename in enumerate(files):
        try:
            packet_sizes, loss_percent = load_run_from_csv(filename)
            style = styles[idx % len(styles)]
            
            run_name = os.path.splitext(os.path.basename(filename))[0]
            
            plt.plot(packet_sizes, loss_percent, 
                    f"{style['color']}{style['marker']}-",
                    linewidth=2, markersize=8, 
                    label=run_name, alpha=0.7)
            
            data_loaded = True
            
            if loss_percent:
                max_loss = max(max_loss, max(loss_percent))
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
    
    if not data_loaded:
        print("\nERROR: No data was successfully loaded from any file!")
        print("Make sure the files exist and have the correct CSV format.")
        return
    
    plt.grid(True, alpha=0.3)
    
    plt.xlabel('Packet Size (bytes)', fontsize=12, fontweight='bold')
    plt.ylabel('Loss %', fontsize=12, fontweight='bold')
    plt.title('UDP Packet Loss % vs Packet Size - Comparison of Test Runs', 
              fontsize=14, fontweight='bold')
    
    plt.axhline(y=0, color='g', linestyle='--', alpha=0.5, label='0% Loss Reference')
    
    plt.legend(fontsize=11, loc='best')
    
    plt.ylim(-2, max(max_loss * 1.1, 5) if max_loss > 0 else 10)
    
    plt.tight_layout()
    
    if output_file is None:
        output_file = get_next_plot_filename("udp_loss_vs_size")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved as '{output_file}'")
    plt.show()

def main():
    parser = argparse.ArgumentParser(
        description='Plot UDP packet loss rate vs packet size from CSV files'
    )
    parser.add_argument('files', nargs='+', help='CSV files to plot')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output file (default: auto-numbered)')
    
    args = parser.parse_args()
    
    plot_from_files(args.files, args.output)

if __name__ == "__main__":
    main()
