#!/usr/bin/env python3
"""
Plot Throughput (bytes/s) as a function of Delay (ms)
"""

import matplotlib.pyplot as plt
import numpy as np
import csv
import sys
import argparse
import os
import glob

def get_next_plot_filename(base_name="throughput_vs_delay", extension="png"):
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

def load_run_from_csv(filename):
    """Load run data from CSV file"""
    delays = []
    duration = []
    transmitted = []
    
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            delays.append(float(row['Delay_ms']))
            duration.append(float(row['Duration_s']))
            transmitted.append(int(row['Transmitted']))
    
    return delays, duration, transmitted

def plot_from_files(files, output_file=None):
    """Plot data from multiple CSV files"""
    # Define color and marker styles
    styles = [
        {'color': 'r', 'marker': 'o', 'label_prefix': 'Run'},
        {'color': 'b', 'marker': 's', 'label_prefix': 'Run'},
        {'color': 'g', 'marker': '^', 'label_prefix': 'Run'},
        {'color': 'm', 'marker': 'd', 'label_prefix': 'Run'},
        {'color': 'c', 'marker': 'v', 'label_prefix': 'Run'},
        {'color': 'y', 'marker': 'o', 'label_prefix': 'Run'},
        {'color': 'k', 'marker': 'p', 'label_prefix': 'Run'},
        {'color': 'orange', 'marker': '*', 'label_prefix': 'Run'},
        {'color': 'purple', 'marker': 'h', 'label_prefix': 'Run'},
        {'color': 'brown', 'marker': 'x', 'label_prefix': 'Run'},
    ]
    
    plt.figure(figsize=(14, 8))
    
    data_loaded = False
    for idx, filename in enumerate(files):
        try:
            delays, duration, transmitted = load_run_from_csv(filename)
            throughput = [t / d for t, d in zip(transmitted, duration)]
            style = styles[idx % len(styles)]
            
            # Extract run name from filename
            run_name = os.path.splitext(os.path.basename(filename))[0]
            
            plt.plot(delays, throughput, 
                    f"{style['color']}{style['marker']}-",
                    linewidth=2, markersize=8, 
                    label=run_name, alpha=0.7)
            
            data_loaded = True
            
            # Print statistics
            print(f"\n{run_name} - Throughput Statistics:")
            print(f"  Max: {max(throughput):.2f} bytes/s at {delays[throughput.index(max(throughput))]}ms delay")
            print(f"  Min: {min(throughput):.2f} bytes/s at {delays[throughput.index(min(throughput))]}ms delay")
            print(f"  Avg: {np.mean(throughput):.2f} bytes/s")
            
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
    
    if not data_loaded:
        print("\nERROR: No data was successfully loaded from any file!")
        print("Make sure the files exist and have the correct CSV format.")
        return
    
    # Add grid
    plt.grid(True, alpha=0.3)
    
    # Labels and title
    plt.xlabel('Delay (ms)', fontsize=12, fontweight='bold')
    plt.ylabel('Throughput (bytes/s)', fontsize=12, fontweight='bold')
    plt.title('Throughput vs Delay - Comparison of Test Runs', fontsize=14, fontweight='bold')
    
    # Invert x-axis so higher delays are on the left
    plt.gca().invert_xaxis()
    
    # Add legend
    plt.legend(fontsize=11, loc='best')
    
    # Format y-axis to show values in thousands
    ax = plt.gca()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.1f}K'))
    
    # Adjust layout
    plt.tight_layout()
    
    # Save and show
    if output_file is None:
        output_file = get_next_plot_filename("throughput_vs_delay")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\nPlot saved as '{output_file}'")
    plt.show()

def plot_hardcoded(output_file=None):
    """Plot using hardcoded data (legacy mode)"""
    # Run 1 data
    delays_run1 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
    duration_run1 = [41.44, 39.21, 37.24, 35.26, 33.19, 31.25, 29.25, 27.18, 25.18, 23.21, 21.25, 19.18, 17.19, 15.26, 13.25, 14.14, 9.20, 24.29, 15.21, 22.21, 1172.69]
    transmitted_run1 = [409602] * 21

    # Run 2 data
    delays_run2 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
    duration_run2 = [41.17, 39.18, 37.17, 35.24, 33.19, 31.25, 29.25, 27.18, 25.09, 23.23, 21.17, 19.18, 17.25, 15.25, 13.18, 11.25, 11.26, 13.25, 24.29, 21.21, 20.29]
    transmitted_run2 = [409602] * 21

    # Run 3 data
    delays_run3 = [200, 190, 180, 170, 160, 150, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
    duration_run3 = [40.19, 38.17, 37.21, 35.20, 33.22, 31.25, 27.22, 25.18, 23.17, 21.26, 19.26, 17.18, 15.19, 13.22, 11.18, 10.18, 556.92, 16.15, 13.21, 17.25]
    transmitted_run3 = [409602] * 20

    # Run 4 data
    delays_run4 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
    duration_run4 = [40.34, 39.21, 37.18, 35.18, 33.18, 31.25, 29.25, 27.25, 25.25, 23.23, 21.26, 19.18, 17.18, 15.25, 13.26, 11.19, 9.18, 15.17, 12.20, 13.22, 14.15]
    transmitted_run4 = [409602] * 21

    # Run 5 data
    delays_run5 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
    duration_run5 = [41.23, 39.17, 37.17, 35.26, 33.24, 31.23, 29.25, 27.25, 25.24, 23.21, 21.25, 19.26, 17.23, 15.25, 13.26, 11.18, 10.22, 17.23, 18.14, 23.19, 15.23]
    transmitted_run5 = [409602] * 21

    # Run 6 data
    delays_run6 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
    duration_run6 = [40.17, 38.17, 36.17, 35.22, 33.19, 31.17, 29.23, 27.25, 25.24, 23.22, 21.25, 19.18, 17.18, 15.25, 13.25, 11.18, 9.18, 580.52, 39.28, 13.17, 16.14]
    transmitted_run6 = [409602] * 21

    # Calculate throughput (bytes/second)
    throughput_run1 = [t / d for t, d in zip(transmitted_run1, duration_run1)]
    throughput_run2 = [t / d for t, d in zip(transmitted_run2, duration_run2)]
    throughput_run3 = [t / d for t, d in zip(transmitted_run3, duration_run3)]
    throughput_run4 = [t / d for t, d in zip(transmitted_run4, duration_run4)]
    throughput_run5 = [t / d for t, d in zip(transmitted_run5, duration_run5)]
    throughput_run6 = [t / d for t, d in zip(transmitted_run6, duration_run6)]

    # Create the plot
    plt.figure(figsize=(14, 8))
    plt.plot(delays_run1, throughput_run1, 'ro-', linewidth=2, markersize=8, label='Run 1', alpha=0.7)
    plt.plot(delays_run2, throughput_run2, 'bs-', linewidth=2, markersize=8, label='Run 2', alpha=0.7)
    plt.plot(delays_run3, throughput_run3, 'g^-', linewidth=2, markersize=8, label='Run 3', alpha=0.7)
    plt.plot(delays_run4, throughput_run4, 'md-', linewidth=2, markersize=8, label='Run 4', alpha=0.7)
    plt.plot(delays_run5, throughput_run5, 'cv-', linewidth=2, markersize=8, label='Run 5', alpha=0.7)
    plt.plot(delays_run6, throughput_run6, 'yo-', linewidth=2, markersize=8, label='Run 6', alpha=0.7)

    # Add grid
    plt.grid(True, alpha=0.3)

    # Labels and title
    plt.xlabel('Delay (ms)', fontsize=12, fontweight='bold')
    plt.ylabel('Throughput (bytes/s)', fontsize=12, fontweight='bold')
    plt.title('Throughput vs Delay - Comparison of Two Test Runs', fontsize=14, fontweight='bold')

    # Invert x-axis so higher delays are on the left
    plt.gca().invert_xaxis()

    # Add legend
    plt.legend(fontsize=11, loc='best')

    # Format y-axis to show values in thousands
    ax = plt.gca()
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.1f}K'))

    # Adjust layout
    plt.tight_layout()

    # Save and show
    if output_file is None:
        output_file = get_next_plot_filename("throughput_vs_delay")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved as '{output_file}'")

    # Print some statistics
    print(f"\nRun 1 - Throughput Statistics:")
    print(f"  Max: {max(throughput_run1):.2f} bytes/s at {delays_run1[throughput_run1.index(max(throughput_run1))]}ms delay")
    print(f"  Min: {min(throughput_run1):.2f} bytes/s at {delays_run1[throughput_run1.index(min(throughput_run1))]}ms delay")
    print(f"  Avg (excluding 0ms): {np.mean(throughput_run1[:-1]):.2f} bytes/s")

    print(f"\nRun 2 - Throughput Statistics:")
    print(f"  Max: {max(throughput_run2):.2f} bytes/s at {delays_run2[throughput_run2.index(max(throughput_run2))]}ms delay")
    print(f"  Min: {min(throughput_run2):.2f} bytes/s at {delays_run2[throughput_run2.index(min(throughput_run2))]}ms delay")
    print(f"  Avg (excluding 0ms): {np.mean(throughput_run2[:-1]):.2f} bytes/s")

    print(f"\nRun 3 - Throughput Statistics:")
    print(f"  Max: {max(throughput_run3):.2f} bytes/s at {delays_run3[throughput_run3.index(max(throughput_run3))]}ms delay")
    print(f"  Min: {min(throughput_run3):.2f} bytes/s at {delays_run3[throughput_run3.index(min(throughput_run3))]}ms delay")
    print(f"  Avg (excluding 0ms): {np.mean(throughput_run3[:-1]):.2f} bytes/s")

    print(f"\nRun 4 - Throughput Statistics:")
    print(f"  Max: {max(throughput_run4):.2f} bytes/s at {delays_run4[throughput_run4.index(max(throughput_run4))]}ms delay")
    print(f"  Min: {min(throughput_run4):.2f} bytes/s at {delays_run4[throughput_run4.index(min(throughput_run4))]}ms delay")
    print(f"  Avg (excluding 0ms): {np.mean(throughput_run4[:-1]):.2f} bytes/s")

    print(f"\nRun 5 - Throughput Statistics:")
    print(f"  Max: {max(throughput_run5):.2f} bytes/s at {delays_run5[throughput_run5.index(max(throughput_run5))]}ms delay")
    print(f"  Min: {min(throughput_run5):.2f} bytes/s at {delays_run5[throughput_run5.index(min(throughput_run5))]}ms delay")
    print(f"  Avg (excluding 0ms): {np.mean(throughput_run5[:-1]):.2f} bytes/s")

    print(f"\nRun 6 - Throughput Statistics:")
    print(f"  Max: {max(throughput_run6):.2f} bytes/s at {delays_run6[throughput_run6.index(max(throughput_run6))]}ms delay")
    print(f"  Min: {min(throughput_run6):.2f} bytes/s at {delays_run6[throughput_run6.index(min(throughput_run6))]}ms delay")
    print(f"  Avg (excluding 0ms): {np.mean(throughput_run6[:-1]):.2f} bytes/s")

    plt.show()



def main():
    parser = argparse.ArgumentParser(
        description='Plot throughput vs delay from CSV files or hardcoded data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Plot data from CSV files
  %(prog)s result_1.csv result_2.csv result_3.csv
  
  # Plot using hardcoded data (no arguments)
  %(prog)s
        """
    )
    
    parser.add_argument('files', nargs='*', help='CSV files to plot (output from analyze_pcap.py)')
    parser.add_argument('-o', '--output', type=str, default=None,
                       help='Output PNG file (default: auto-numbered throughput_vs_delay_N.png)')
    
    args = parser.parse_args()
    
    if args.files:
        print(f"Plotting data from {len(args.files)} file(s)...")
        plot_from_files(args.files, args.output)
    else:
        print("No files specified, using hardcoded data...")
        plot_hardcoded(args.output)


if __name__ == "__main__":
    main()
