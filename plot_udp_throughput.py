#!/usr/bin/env python3
"""
Plot Throughput (bytes/s) as a function of Packet Size (bytes) for UDP tests
"""

import matplotlib.pyplot as plt
import numpy as np
import csv
import sys
import argparse
import os
import glob

def get_next_plot_filename(base_name="udp_throughput_vs_size", extension="png"):
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
    throughput = []
    
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            packet_sizes.append(float(row['Packet_Size']))
            throughput.append(float(row['Throughput_bps']))
    
    return packet_sizes, throughput

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
    
    data_loaded = False
    
    for idx, filename in enumerate(files):
        try:
            packet_sizes, throughput = load_run_from_csv(filename)
            style = styles[idx % len(styles)]
            
            run_name = os.path.splitext(os.path.basename(filename))[0]
            
            plt.plot(packet_sizes, throughput, 
                    f"{style['color']}{style['marker']}-",
                    linewidth=2, markersize=8, 
                    label=run_name, alpha=0.7)
            
            data_loaded = True
            
            # Print statistics
            print(f"\n{run_name} - Throughput Statistics:")
            print(f"  Max: {max(throughput):.2f} bps at {packet_sizes[throughput.index(max(throughput))]} bytes")
            print(f"  Min: {min(throughput):.2f} bps at {packet_sizes[throughput.index(min(throughput))]} bytes")
            print(f"  Avg: {np.mean(throughput):.2f} bps")
            
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
    
    if not data_loaded:
        print("\nERROR: No data was successfully loaded from any file!")
        print("Make sure the files exist and have the correct CSV format.")
        return
    
    plt.grid(True, alpha=0.3)
    
    plt.xlabel('Packet Size (bytes)', fontsize=12, fontweight='bold')
    plt.ylabel('Throughput (bytes/s)', fontsize=12, fontweight='bold')
    plt.title('UDP Throughput vs Packet Size - Comparison of Test Runs', 
              fontsize=14, fontweight='bold')
    
    plt.legend(fontsize=11, loc='best')
    
    # Format y-axis to show values in thousands
    ax = plt.gca()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.1f}K'))
    
    plt.tight_layout()
    
    if output_file is None:
        output_file = get_next_plot_filename("udp_throughput_vs_size")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved as '{output_file}'")
    plt.show()

def main():
    parser = argparse.ArgumentParser(
        description='Plot UDP throughput vs packet size from CSV files'
    )
    parser.add_argument('files', nargs='+', help='CSV files to plot')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output file (default: auto-numbered)')
    
    args = parser.parse_args()
    
    plot_from_files(args.files, args.output)

if __name__ == "__main__":
    main()
