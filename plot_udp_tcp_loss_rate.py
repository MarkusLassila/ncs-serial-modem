#!/usr/bin/env python3
"""
Plot UDP Loss % as a function of TCP Data Size (KB)
Reads UDP analysis CSV files from analyze_udp_tcp_pcap.py
Shows how concurrent TCP transmission size affects UDP trace quality
"""

import matplotlib.pyplot as plt
import numpy as np
import csv
import sys
import argparse
import os
import glob

def get_next_plot_filename(base_name="udp_loss_vs_tcp_size", extension="png"):
    """Find the next available filename with auto-incrementing number"""
    pattern = f"{base_name}_*.{extension}"
    existing_files = glob.glob(pattern)
    
    if not existing_files:
        return f"{base_name}_1.{extension}"
    
    # Extract numbers from existing files
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

def load_udp_data_from_csv(filename):
    """Load UDP trace analysis data from CSV file"""
    tcp_sizes = []
    loss_percent = []
    
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            tcp_sizes.append(float(row['TCP_Data_KB']))
            loss_percent.append(float(row['Loss_Pct']))
    
    return tcp_sizes, loss_percent

def plot_from_files(files, output_file=None):
    """Plot UDP loss data from multiple CSV files"""
    # Define color and marker styles
    styles = [
        {'color': 'r', 'marker': 'o'},
        {'color': 'b', 'marker': 's'},
        {'color': 'g', 'marker': '^'},
        {'color': 'm', 'marker': 'd'},
        {'color': 'c', 'marker': 'v'},
        {'color': 'orange', 'marker': 'p'},
        {'color': 'purple', 'marker': '*'},
        {'color': 'brown', 'marker': 'h'},
        {'color': 'k', 'marker': 'x'},
        {'color': 'darkgreen', 'marker': '+'},
    ]
    
    plt.figure(figsize=(14, 8))
    
    max_loss = 0
    data_loaded = False
    
    for idx, filename in enumerate(files):
        try:
            tcp_sizes, loss_percent = load_udp_data_from_csv(filename)
            if not tcp_sizes:
                print(f"Warning: No data in {filename}")
                continue
                
            style = styles[idx % len(styles)]
            
            # Extract run name from filename
            run_name = os.path.splitext(os.path.basename(filename))[0]
            
            plt.plot(tcp_sizes, loss_percent, 
                    f"{style['color']}{style['marker']}-",
                    linewidth=2, markersize=8, 
                    label=run_name, alpha=0.7)
            
            max_loss = max(max_loss, max(loss_percent))
            data_loaded = True
            
        except FileNotFoundError:
            print(f"Error: File not found: {filename}")
            continue
        except KeyError as e:
            print(f"Error: Missing column {e} in {filename}")
            continue
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
    
    if not data_loaded:
        print("Error: No valid data loaded from any file")
        return False
    
    # Customize plot
    plt.xlabel('Concurrent TCP Data Size (KB)', fontsize=14, fontweight='bold')
    plt.ylabel('UDP Trace Data Loss (%)', fontsize=14, fontweight='bold')
    plt.title('UDP Trace Data Loss vs Concurrent TCP Transmission Size', fontsize=16, fontweight='bold')
    plt.grid(True, alpha=0.3, linestyle='--')
    plt.legend(fontsize=11, loc='best')
    
    # Set y-axis range with some margin
    plt.ylim(-2, max_loss + 10)
    
    # Add horizontal line at 0% loss
    plt.axhline(y=0, color='gray', linestyle='--', linewidth=1, alpha=0.5)
    
    plt.tight_layout()
    
    # Save figure
    if output_file is None:
        output_file = get_next_plot_filename()
    
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved to: {output_file}")
    
    # Show plot
    plt.show()
    
    return True

def main():
    parser = argparse.ArgumentParser(
        description='Plot UDP trace data loss as a function of concurrent TCP data size',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s udp_analysis_1.csv                           # Plot single file
  %(prog)s udp_analysis_*.csv                           # Plot all matching files
  %(prog)s udp_analysis_1.csv udp_analysis_2.csv        # Plot multiple files
  %(prog)s udp_analysis_1.csv -o my_plot.png            # Custom output filename
        """
    )
    
    parser.add_argument('files', nargs='+', help='UDP analysis CSV file(s) to plot')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output plot filename (default: auto-numbered udp_loss_vs_tcp_size_N.png)')
    
    args = parser.parse_args()
    
    # Expand wildcards
    files = []
    for pattern in args.files:
        matched = glob.glob(pattern)
        if matched:
            files.extend(matched)
        else:
            # Not a wildcard, add as-is (will error later if doesn't exist)
            files.append(pattern)
    
    if not files:
        print("Error: No files specified")
        sys.exit(1)
    
    # Remove duplicates while preserving order
    files = list(dict.fromkeys(files))
    
    print(f"Plotting {len(files)} file(s):")
    for f in files:
        print(f"  - {f}")
    print()
    
    success = plot_from_files(files, args.output)
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
