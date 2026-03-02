#!/usr/bin/env python3
"""
Plot Loss % as a function of Delay (ms)
"""

import matplotlib.pyplot as plt
import numpy as np
import csv
import sys
import argparse
import os
import glob

def get_next_plot_filename(base_name="loss_rate_vs_delay", extension="png"):
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
    loss_percent = []
    
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            delays.append(float(row['Delay_ms']))
            loss_percent.append(float(row['Loss_pct']))
    
    return delays, loss_percent

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
    
    max_loss = 0
    for idx, filename in enumerate(files):
        try:
            delays, loss_percent = load_run_from_csv(filename)
            style = styles[idx % len(styles)]
            
            # Extract run name from filename
            run_name = os.path.splitext(os.path.basename(filename))[0]
            
            plt.plot(delays, loss_percent, 
                    f"{style['color']}{style['marker']}-",
                    linewidth=2, markersize=8, 
                    label=run_name, alpha=0.7)
            
            if loss_percent:
                max_loss = max(max_loss, max(loss_percent))
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
    
    # Add grid
    plt.grid(True, alpha=0.3)
    
    # Labels and title
    plt.xlabel('Delay (ms)', fontsize=12, fontweight='bold')
    plt.ylabel('Loss %', fontsize=12, fontweight='bold')
    plt.title('Packet Loss % vs Delay - Comparison of Test Runs', fontsize=14, fontweight='bold')
    
    # Add horizontal line at 0% loss for reference
    plt.axhline(y=0, color='g', linestyle='--', alpha=0.5, label='0% Loss Reference')
    
    # Invert x-axis so higher delays are on the left
    plt.gca().invert_xaxis()
    
    # Add legend
    plt.legend(fontsize=11, loc='upper right')
    
    # Set y-axis to start at 0
    plt.ylim(-2, max_loss * 1.1 if max_loss > 0 else 100)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save and show
    if output_file is None:
        output_file = get_next_plot_filename("loss_rate_vs_delay")
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved as '{output_file}'")
    plt.show()

def plot_hardcoded(output_file=None):
    """Plot using hardcoded data (legacy mode)"""

# Data from test results - Run 1
delays_run1 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
loss_percent_run1 = [0.00, 11.32, 3.02, 0.00, 0.00, 0.00, 0.00, 0.34, 23.88, 38.38, 51.53, 64.82, 68.51, 73.11, 82.13, 77.79, 89.35, 63.31, 80.81, 62.92, 59.11]

# Data from test results - Run 2
delays_run2 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
loss_percent_run2 = [0.25, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.18, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 4.78, 51.88, 14.14, 2.37, 7.14, 1.00]

# Data from test results - Run 3
delays_run3 = [200, 190, 180, 170, 160, 150, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
loss_percent_run3 = [0.00, 0.00, 0.00, 0.00, 0.00, 0.34, 0.00, 0.75, 8.34, 44.81, 61.89, 69.90, 77.49, 82.02, 82.64, 83.96, 84.33, 81.75, 89.27, 82.19]

# Data from test results - Run 4
delays_run4 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
loss_percent_run4 = [0.00, 6.13, 0.00, 0.00, 0.00, 0.66, 1.59, 2.82, 3.06, 7.20, 15.59, 27.15, 38.88, 46.04, 49.37, 58.38, 66.68, 69.48, 77.08, 72.77, 69.86]

# Data from test results - Run 5
delays_run5 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
loss_percent_run5 = [0.41, 0.41, 2.81, 1.73, 6.57, 5.10, 11.83, 15.61, 25.19, 36.47, 44.72, 45.40, 59.61, 65.52, 71.89, 77.28, 82.55, 76.75, 67.99, 58.16, 78.76]

# Data from test results - Run 6
delays_run6 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
loss_percent_run6 = [1.25, 0.00, 0.25, 0.00, 0.00, 0.00, 0.34, 0.00, 58.59, 71.22, 77.13, 81.93, 87.64, 91.14, 89.68, 93.78, 95.02, 86.78, 70.01, 88.37, 90.25]

# Create the plot
plt.figure(figsize=(14, 8))
plt.plot(delays_run1, loss_percent_run1, 'ro-', linewidth=2, markersize=8, label='Run 1', alpha=0.7)
plt.plot(delays_run2, loss_percent_run2, 'bs-', linewidth=2, markersize=8, label='Run 2', alpha=0.7)
plt.plot(delays_run3, loss_percent_run3, 'g^-', linewidth=2, markersize=8, label='Run 3', alpha=0.7)
plt.plot(delays_run4, loss_percent_run4, 'md-', linewidth=2, markersize=8, label='Run 4', alpha=0.7)
plt.plot(delays_run5, loss_percent_run5, 'cv-', linewidth=2, markersize=8, label='Run 5', alpha=0.7)
plt.plot(delays_run6, loss_percent_run6, 'yo-', linewidth=2, markersize=8, label='Run 6', alpha=0.7)

# Add grid
plt.grid(True, alpha=0.3)

# Labels and title
plt.xlabel('Delay (ms)', fontsize=12, fontweight='bold')
plt.ylabel('Loss %', fontsize=12, fontweight='bold')
plt.title('Packet Loss % vs Delay - Comparison of Two Test Runs', fontsize=14, fontweight='bold')

# Add horizontal line at 0% loss for reference
plt.axhline(y=0, color='g', linestyle='--', alpha=0.5, label='0% Loss Reference')

# Invert x-axis so higher delays are on the left
plt.gca().invert_xaxis()

# Add legend
plt.legend(fontsize=11, loc='upper right')

# Set y-axis to start at 0
plt.ylim(-2, max(max(loss_percent_run1), max(loss_percent_run2), max(loss_percent_run3), max(loss_percent_run4), max(loss_percent_run5), max(loss_percent_run6)) * 1.1)

# Adjust layout
plt.tight_layout()

# Save and show
if output_file is None:
    output_file = get_next_plot_filename("loss_rate_vs_delay")
plt.savefig(output_file, dpi=300, bbox_inches='tight')
print(f"Plot saved as '{output_file}'")
plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Plot packet loss % vs delay from CSV files or hardcoded data',
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
                       help='Output PNG file (default: auto-numbered loss_rate_vs_delay_N.png)')
    
    args = parser.parse_args()
    
    if args.files:
        print(f"Plotting data from {len(args.files)} file(s)...")
        plot_from_files(args.files, args.output)
    else:
        print("No files specified, using hardcoded data...")
        plot_hardcoded(args.output)


if __name__ == "__main__":
    main()
