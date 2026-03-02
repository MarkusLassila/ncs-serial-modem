#!/usr/bin/env python3
"""
Plot Loss % as a function of Throughput (bytes/s) for UDP tests
Scatter plot showing correlation between throughput and packet loss
"""

import matplotlib.pyplot as plt
import numpy as np
import csv
import sys
import argparse
import os
import glob

def get_next_plot_filename(base_name="udp_loss_vs_throughput", extension="png"):
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
    throughput = []
    loss_percent = []
    
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            throughput.append(float(row['Throughput_bps']))
            loss_percent.append(float(row['Loss_pct']))
    
    return throughput, loss_percent

def plot_from_files(files, output_file=None):
    """Plot data from multiple CSV files"""
    styles = [
        {'color': 'red', 'edge': 'darkred', 'marker': 'o'},
        {'color': 'blue', 'edge': 'darkblue', 'marker': 's'},
        {'color': 'green', 'edge': 'darkgreen', 'marker': '^'},
        {'color': 'magenta', 'edge': 'darkmagenta', 'marker': 'd'},
        {'color': 'cyan', 'edge': 'darkcyan', 'marker': 'v'},
        {'color': 'yellow', 'edge': 'olive', 'marker': 'p'},
        {'color': 'black', 'edge': 'gray', 'marker': '*'},
        {'color': 'orange', 'edge': 'darkorange', 'marker': 'h'},
        {'color': 'purple', 'edge': 'indigo', 'marker': 'x'},
        {'color': 'brown', 'edge': 'saddlebrown', 'marker': '+'},
    ]
    
    line_colors = ['r', 'b', 'g', 'm', 'c', 'y', 'k', 'orange', 'purple', 'brown']
    
    plt.figure(figsize=(14, 8))
    
    max_loss = 0
    data_loaded = False
    
    for idx, filename in enumerate(files):
        try:
            throughput, loss_percent = load_run_from_csv(filename)
            style = styles[idx % len(styles)]
            line_color = line_colors[idx % len(line_colors)]
            
            run_name = os.path.splitext(os.path.basename(filename))[0]
            
            # Scatter plot
            plt.scatter(throughput, loss_percent, 
                       c=style['color'], s=100, alpha=0.6, 
                       edgecolors=style['edge'], linewidth=1.5,
                       label=run_name, marker=style['marker'])
            
            # Connecting line to show progression
            plt.plot(throughput, loss_percent, 
                    f"{line_color}-", linewidth=1, alpha=0.3)
            
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
    
    plt.xlabel('Throughput (bytes/s)', fontsize=12, fontweight='bold')
    plt.ylabel('Loss %', fontsize=12, fontweight='bold')
    plt.title('UDP Packet Loss % vs Throughput - Comparison of Test Runs', 
              fontsize=14, fontweight='bold')
    
    plt.axhline(y=0, color='g', linestyle='--', alpha=0.5, label='0% Loss Reference')
    
    plt.legend(fontsize=11, loc='best')
    
    plt.ylim(-2, max(max_loss * 1.1, 5) if max_loss > 0 else 10)
    
    # Format x-axis to show values in thousands
    ax = plt.gca()
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.1f}K'))
    
    plt.tight_layout()
    
    if output_file is None:
        output_file = get_next_plot_filename("udp_loss_vs_throughput")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved as '{output_file}'")
    plt.show()

def main():
    parser = argparse.ArgumentParser(
        description='Plot UDP packet loss vs throughput from CSV files'
    )
    parser.add_argument('files', nargs='+', help='CSV files to plot')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output file (default: auto-numbered)')
    
    args = parser.parse_args()
    
    plot_from_files(args.files, args.output)

if __name__ == "__main__":
    main()
