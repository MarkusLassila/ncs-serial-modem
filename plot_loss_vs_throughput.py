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

# Calculate throughput (bytes/second)
throughput_run1 = [t / d for t, d in zip(transmitted_run1, duration_run1)]
throughput_run2 = [t / d for t, d in zip(transmitted_run2, duration_run2)]
throughput_run3 = [t / d for t, d in zip(transmitted_run3, duration_run3)]
throughput_run4 = [t / d for t, d in zip(transmitted_run4, duration_run4)]

# Create the plot
plt.figure(figsize=(14, 8))
plt.scatter(throughput_run1, loss_percent_run1, c='red', s=100, alpha=0.6, edgecolors='darkred', linewidth=1.5, label='Run 1')
plt.scatter(throughput_run2, loss_percent_run2, c='blue', s=100, alpha=0.6, edgecolors='darkblue', linewidth=1.5, label='Run 2')
plt.scatter(throughput_run3, loss_percent_run3, c='green', s=100, alpha=0.6, edgecolors='darkgreen', linewidth=1.5, label='Run 3', marker='^')
plt.scatter(throughput_run4, loss_percent_run4, c='magenta', s=100, alpha=0.6, edgecolors='darkmagenta', linewidth=1.5, label='Run 4', marker='d')

# Add connecting lines for better visualization
plt.plot(throughput_run1, loss_percent_run1, 'r-', linewidth=1, alpha=0.3)
plt.plot(throughput_run2, loss_percent_run2, 'b-', linewidth=1, alpha=0.3)
plt.plot(throughput_run3, loss_percent_run3, 'g-', linewidth=1, alpha=0.3)
plt.plot(throughput_run4, loss_percent_run4, 'm-', linewidth=1, alpha=0.3)

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
plt.ylim(-2, max(max(loss_percent_run1), max(loss_percent_run2), max(loss_percent_run3), max(loss_percent_run4)) * 1.1)

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
