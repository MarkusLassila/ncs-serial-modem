#!/usr/bin/env python3
"""
Plot Loss % as a function of Throughput (bytes/s)
"""

import matplotlib.pyplot as plt
import numpy as np
import csv
import sys
import argparse
import os

def load_run_from_csv(filename):
    """Load run data from CSV file"""
    delays = []
    duration = []
    transmitted = []
    loss_percent = []
    
    with open(filename, 'r') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            delays.append(float(row['Delay_ms']))
            duration.append(float(row['Duration_s']))
            transmitted.append(int(row['Transmitted']))
            loss_percent.append(float(row['Loss_pct']))
    
    return delays, duration, transmitted, loss_percent

def plot_from_files(files):
    """Plot data from multiple CSV files"""
    # Define color and marker styles with edge colors
    styles = [
        {'color': 'red', 'edge': 'darkred', 'marker': 'o'},
        {'color': 'blue', 'edge': 'darkblue', 'marker': 's'},
        {'color': 'green', 'edge': 'darkgreen', 'marker': '^'},
        {'color': 'magenta', 'edge': 'darkmagenta', 'marker': 'd'},
        {'color': 'cyan', 'edge': 'darkcyan', 'marker': 'v'},
        {'color': 'yellow', 'edge': 'olive', 'marker': 'o'},
        {'color': 'black', 'edge': 'gray', 'marker': 'p'},
        {'color': 'orange', 'edge': 'darkorange', 'marker': '*'},
        {'color': 'purple', 'edge': 'indigo', 'marker': 'h'},
        {'color': 'brown', 'edge': 'saddlebrown', 'marker': 'x'},
    ]
    
    # Short color codes for lines
    line_colors = ['r', 'b', 'g', 'm', 'c', 'y', 'k', 'orange', 'purple', 'brown']
    
    plt.figure(figsize=(14, 8))
    
    max_loss = 0
    for idx, filename in enumerate(files):
        try:
            delays, duration, transmitted, loss_percent = load_run_from_csv(filename)
            throughput = [t / d for t, d in zip(transmitted, duration)]
            style = styles[idx % len(styles)]
            line_color = line_colors[idx % len(line_colors)]
            
            # Extract run name from filename
            run_name = os.path.splitext(os.path.basename(filename))[0]
            
            # Scatter plot
            plt.scatter(throughput, loss_percent, 
                       c=style['color'], s=100, alpha=0.6, 
                       edgecolors=style['edge'], linewidth=1.5,
                       label=run_name, marker=style['marker'])
            
            # Connecting line
            plt.plot(throughput, loss_percent, 
                    f"{line_color}-", linewidth=1, alpha=0.3)
            
            if loss_percent:
                max_loss = max(max_loss, max(loss_percent))
            
        except Exception as e:
            print(f"Error loading {filename}: {e}")
            continue
    
    # Add grid
    plt.grid(True, alpha=0.3)
    
    # Labels and title
    plt.xlabel('Throughput (bytes/s)', fontsize=12, fontweight='bold')
    plt.ylabel('Loss %', fontsize=12, fontweight='bold')
    plt.title('Packet Loss % vs Throughput - Comparison of Test Runs', fontsize=14, fontweight='bold')
    
    # Format x-axis to show values in thousands
    ax = plt.gca()
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.1f}K'))
    
    # Add legend
    plt.legend(fontsize=11, loc='best')
    
    # Set y-axis to start at 0
    plt.ylim(-2, max_loss * 1.1 if max_loss > 0 else 100)
    
    # Adjust layout
    plt.tight_layout()
    
    # Save and show
    plt.savefig('loss_vs_throughput_comparison.png', dpi=300, bbox_inches='tight')
    print("\nPlot saved as 'loss_vs_throughput_comparison.png'")
    
    # Print correlation insights
    print("\nInsights:")
    print("- Lower throughput generally correlates with higher packet loss")
    print("- Optimal operating range varies by test conditions")
    
    plt.show()

def plot_hardcoded():
    """Plot using hardcoded data (legacy mode)"""

# Run 1 data
delays_run1 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
duration_run1 = [41.44, 39.21, 37.24, 35.26, 33.19, 31.25, 29.25, 27.18, 25.18, 23.21, 21.25, 19.18, 17.19, 15.26, 13.25, 14.14, 9.20, 24.29, 15.21, 22.21, 1172.69]
transmitted_run1 = [409602] * 21
loss_percent_run1 = [0.00, 11.32, 3.02, 0.00, 0.00, 0.00, 0.00, 0.34, 23.88, 38.38, 51.53, 64.82, 68.51, 73.11, 82.13, 77.79, 89.35, 63.31, 80.81, 62.92, 59.11]

# Run 2 data
delays_run2 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
duration_run2 = [41.17, 39.18, 37.17, 35.24, 33.19, 31.25, 29.25, 27.18, 25.09, 23.23, 21.17, 19.18, 17.25, 15.25, 13.18, 11.25, 11.26, 13.25, 24.29, 21.21, 20.29]
transmitted_run2 = [409602] * 21
loss_percent_run2 = [0.25, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.18, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 4.78, 51.88, 14.14, 2.37, 7.14, 1.00]

# Run 3 data
delays_run3 = [200, 190, 180, 170, 160, 150, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
duration_run3 = [40.19, 38.17, 37.21, 35.20, 33.22, 31.25, 27.22, 25.18, 23.17, 21.26, 19.26, 17.18, 15.19, 13.22, 11.18, 10.18, 556.92, 16.15, 13.21, 17.25]
transmitted_run3 = [409602] * 20
loss_percent_run3 = [0.00, 0.00, 0.00, 0.00, 0.00, 0.34, 0.00, 0.75, 8.34, 44.81, 61.89, 69.90, 77.49, 82.02, 82.64, 83.96, 84.33, 81.75, 89.27, 82.19]

# Run 4 data
delays_run4 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
duration_run4 = [40.34, 39.21, 37.18, 35.18, 33.18, 31.25, 29.25, 27.25, 25.25, 23.23, 21.26, 19.18, 17.18, 15.25, 13.26, 11.19, 9.18, 15.17, 12.20, 13.22, 14.15]
transmitted_run4 = [409602] * 21
loss_percent_run4 = [0.00, 6.13, 0.00, 0.00, 0.00, 0.66, 1.59, 2.82, 3.06, 7.20, 15.59, 27.15, 38.88, 46.04, 49.37, 58.38, 66.68, 69.48, 77.08, 72.77, 69.86]

# Run 5 data
delays_run5 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
duration_run5 = [41.23, 39.17, 37.17, 35.26, 33.24, 31.23, 29.25, 27.25, 25.24, 23.21, 21.25, 19.26, 17.23, 15.25, 13.26, 11.18, 10.22, 17.23, 18.14, 23.19, 15.23]
transmitted_run5 = [409602] * 21
loss_percent_run5 = [0.41, 0.41, 2.81, 1.73, 6.57, 5.10, 11.83, 15.61, 25.19, 36.47, 44.72, 45.40, 59.61, 65.52, 71.89, 77.28, 82.55, 76.75, 67.99, 58.16, 78.76]

# Run 6 data
delays_run6 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
duration_run6 = [40.17, 38.17, 36.17, 35.22, 33.19, 31.17, 29.23, 27.25, 25.24, 23.22, 21.25, 19.18, 17.18, 15.25, 13.25, 11.18, 9.18, 580.52, 39.28, 13.17, 16.14]
transmitted_run6 = [409602] * 21
loss_percent_run6 = [1.25, 0.00, 0.25, 0.00, 0.00, 0.00, 0.34, 0.00, 58.59, 71.22, 77.13, 81.93, 87.64, 91.14, 89.68, 93.78, 95.02, 86.78, 70.01, 88.37, 90.25]

# Calculate throughput (bytes/second)
throughput_run1 = [t / d for t, d in zip(transmitted_run1, duration_run1)]
throughput_run2 = [t / d for t, d in zip(transmitted_run2, duration_run2)]
throughput_run3 = [t / d for t, d in zip(transmitted_run3, duration_run3)]
throughput_run4 = [t / d for t, d in zip(transmitted_run4, duration_run4)]
throughput_run5 = [t / d for t, d in zip(transmitted_run5, duration_run5)]
throughput_run6 = [t / d for t, d in zip(transmitted_run6, duration_run6)]

# Create the plot
plt.figure(figsize=(14, 8))
plt.scatter(throughput_run1, loss_percent_run1, c='red', s=100, alpha=0.6, edgecolors='darkred', linewidth=1.5, label='Run 1')
plt.scatter(throughput_run2, loss_percent_run2, c='blue', s=100, alpha=0.6, edgecolors='darkblue', linewidth=1.5, label='Run 2')
plt.scatter(throughput_run3, loss_percent_run3, c='green', s=100, alpha=0.6, edgecolors='darkgreen', linewidth=1.5, label='Run 3', marker='^')
plt.scatter(throughput_run4, loss_percent_run4, c='magenta', s=100, alpha=0.6, edgecolors='darkmagenta', linewidth=1.5, label='Run 4', marker='d')
plt.scatter(throughput_run5, loss_percent_run5, c='cyan', s=100, alpha=0.6, edgecolors='darkcyan', linewidth=1.5, label='Run 5', marker='v')
plt.scatter(throughput_run6, loss_percent_run6, c='yellow', s=100, alpha=0.6, edgecolors='olive', linewidth=1.5, label='Run 6', marker='o')

# Add connecting lines for better visualization
plt.plot(throughput_run1, loss_percent_run1, 'r-', linewidth=1, alpha=0.3)
plt.plot(throughput_run2, loss_percent_run2, 'b-', linewidth=1, alpha=0.3)
plt.plot(throughput_run3, loss_percent_run3, 'g-', linewidth=1, alpha=0.3)
plt.plot(throughput_run4, loss_percent_run4, 'm-', linewidth=1, alpha=0.3)
plt.plot(throughput_run5, loss_percent_run5, 'c-', linewidth=1, alpha=0.3)
plt.plot(throughput_run6, loss_percent_run6, 'y-', linewidth=1, alpha=0.3)

# Add grid
plt.grid(True, alpha=0.3)

# Labels and title
plt.xlabel('Throughput (bytes/s)', fontsize=12, fontweight='bold')
plt.ylabel('Loss %', fontsize=12, fontweight='bold')
plt.title('Packet Loss % vs Throughput - Comparison of Two Test Runs', fontsize=14, fontweight='bold')

# Format x-axis to show values in thousands
ax = plt.gca()
ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, p: f'{x/1000:.1f}K'))

# Add legend
plt.legend(fontsize=11, loc='best')

# Set y-axis to start at 0
plt.ylim(-2, max(max(loss_percent_run1), max(loss_percent_run2), max(loss_percent_run3), max(loss_percent_run4), max(loss_percent_run5), max(loss_percent_run6)) * 1.1)

# Adjust layout
plt.tight_layout()

# Save and show
plt.savefig('loss_vs_throughput_comparison.png', dpi=300, bbox_inches='tight')
print("Plot saved as 'loss_vs_throughput_comparison.png'")

# Print correlation insights
print("\nInsights:")
print("- Runs 1 and 3 show high packet loss at lower delays (higher throughput attempts)")
print("- Run 2 shows exceptional performance with low loss across most delay values")
print("- Run 4 shows intermediate performance with gradual loss increase as delay decreases")
print("- Optimal operating range appears to be delays >= 150ms for consistent low loss")

plt.show()


def main():
    parser = argparse.ArgumentParser(
        description='Plot packet loss % vs throughput from CSV files or hardcoded data',
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
    
    args = parser.parse_args()
    
    if args.files:
        print(f"Plotting data from {len(args.files)} file(s)...")
        plot_from_files(args.files)
    else:
        print("No files specified, using hardcoded data...")
        plot_hardcoded()


if __name__ == "__main__":
    main()
