#!/usr/bin/env python3
"""
Plot Loss % as a function of Delay (ms)
"""

import matplotlib.pyplot as plt
import numpy as np

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

# Create the plot
plt.figure(figsize=(14, 8))
plt.plot(delays_run1, loss_percent_run1, 'ro-', linewidth=2, markersize=8, label='Run 1', alpha=0.7)
plt.plot(delays_run2, loss_percent_run2, 'bs-', linewidth=2, markersize=8, label='Run 2', alpha=0.7)
plt.plot(delays_run3, loss_percent_run3, 'g^-', linewidth=2, markersize=8, label='Run 3', alpha=0.7)
plt.plot(delays_run4, loss_percent_run4, 'md-', linewidth=2, markersize=8, label='Run 4', alpha=0.7)

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
plt.ylim(-2, max(max(loss_percent_run1), max(loss_percent_run2), max(loss_percent_run3), max(loss_percent_run4)) * 1.1)

# Adjust layout
plt.tight_layout()

# Save and show
plt.savefig('loss_rate_vs_delay_comparison.png', dpi=300, bbox_inches='tight')
print("Plot saved as 'loss_rate_vs_delay_comparison.png'")
plt.show()
