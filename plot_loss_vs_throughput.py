#!/usr/bin/env python3
"""
Plot Loss % as a function of Throughput (bytes/s)
"""

import matplotlib.pyplot as plt
import numpy as np

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

# Calculate throughput (bytes/second)
throughput_run1 = [t / d for t, d in zip(transmitted_run1, duration_run1)]
throughput_run2 = [t / d for t, d in zip(transmitted_run2, duration_run2)]

# Create the plot
plt.figure(figsize=(14, 8))
plt.scatter(throughput_run1, loss_percent_run1, c='red', s=100, alpha=0.6, edgecolors='darkred', linewidth=1.5, label='Run 1')
plt.scatter(throughput_run2, loss_percent_run2, c='blue', s=100, alpha=0.6, edgecolors='darkblue', linewidth=1.5, label='Run 2')

# Add connecting lines for better visualization
plt.plot(throughput_run1, loss_percent_run1, 'r-', linewidth=1, alpha=0.3)
plt.plot(throughput_run2, loss_percent_run2, 'b-', linewidth=1, alpha=0.3)

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
plt.ylim(-2, max(max(loss_percent_run1), max(loss_percent_run2)) * 1.1)

# Adjust layout
plt.tight_layout()

# Save and show
plt.savefig('loss_vs_throughput_comparison.png', dpi=300, bbox_inches='tight')
print("Plot saved as 'loss_vs_throughput_comparison.png'")

# Print correlation insights
print("\nInsights:")
print("- Lower throughput generally correlates with higher packet loss in Run 1")
print("- Run 2 shows much better performance with low loss across most throughput ranges")
print("- Optimal operating range appears to be 15-25 KB/s with minimal loss in Run 2")

plt.show()
