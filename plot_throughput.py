#!/usr/bin/env python3
"""
Plot Throughput (bytes/s) as a function of Delay (ms)
"""

import matplotlib.pyplot as plt
import numpy as np

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

# # Run 6 data (TEMPLATE - Uncomment and fill in data)
# delays_run6 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
# duration_run6 = [41.00, 39.00, 37.00, 35.00, 33.00, 31.00, 29.00, 27.00, 25.00, 23.00, 21.00, 19.00, 17.00, 15.00, 13.00, 11.00, 10.00, 17.00, 18.00, 23.00, 15.00]
# transmitted_run6 = [409602] * 21

# # Run 7 data (TEMPLATE - Uncomment and fill in data)
# delays_run7 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
# duration_run7 = [41.00, 39.00, 37.00, 35.00, 33.00, 31.00, 29.00, 27.00, 25.00, 23.00, 21.00, 19.00, 17.00, 15.00, 13.00, 11.00, 10.00, 17.00, 18.00, 23.00, 15.00]
# transmitted_run7 = [409602] * 21

# # Run 8 data (TEMPLATE - Uncomment and fill in data)
# delays_run8 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
# duration_run8 = [41.00, 39.00, 37.00, 35.00, 33.00, 31.00, 29.00, 27.00, 25.00, 23.00, 21.00, 19.00, 17.00, 15.00, 13.00, 11.00, 10.00, 17.00, 18.00, 23.00, 15.00]
# transmitted_run8 = [409602] * 21

# # Run 9 data (TEMPLATE - Uncomment and fill in data)
# delays_run9 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
# duration_run9 = [41.00, 39.00, 37.00, 35.00, 33.00, 31.00, 29.00, 27.00, 25.00, 23.00, 21.00, 19.00, 17.00, 15.00, 13.00, 11.00, 10.00, 17.00, 18.00, 23.00, 15.00]
# transmitted_run9 = [409602] * 21

# # Run 10 data (TEMPLATE - Uncomment and fill in data)
# delays_run10 = [200, 190, 180, 170, 160, 150, 140, 130, 120, 110, 100, 90, 80, 70, 60, 50, 40, 30, 20, 10, 0]
# duration_run10 = [41.00, 39.00, 37.00, 35.00, 33.00, 31.00, 29.00, 27.00, 25.00, 23.00, 21.00, 19.00, 17.00, 15.00, 13.00, 11.00, 10.00, 17.00, 18.00, 23.00, 15.00]
# transmitted_run10 = [409602] * 21

# Calculate throughput (bytes/second)
throughput_run1 = [t / d for t, d in zip(transmitted_run1, duration_run1)]
throughput_run2 = [t / d for t, d in zip(transmitted_run2, duration_run2)]
throughput_run3 = [t / d for t, d in zip(transmitted_run3, duration_run3)]
throughput_run4 = [t / d for t, d in zip(transmitted_run4, duration_run4)]
throughput_run5 = [t / d for t, d in zip(transmitted_run5, duration_run5)]
# throughput_run6 = [t / d for t, d in zip(transmitted_run6, duration_run6)]  # Uncomment for Run 6
# throughput_run7 = [t / d for t, d in zip(transmitted_run7, duration_run7)]  # Uncomment for Run 7
# throughput_run8 = [t / d for t, d in zip(transmitted_run8, duration_run8)]  # Uncomment for Run 8
# throughput_run9 = [t / d for t, d in zip(transmitted_run9, duration_run9)]  # Uncomment for Run 9
# throughput_run10 = [t / d for t, d in zip(transmitted_run10, duration_run10)]  # Uncomment for Run 10

# Create the plot
plt.figure(figsize=(14, 8))
plt.plot(delays_run1, throughput_run1, 'ro-', linewidth=2, markersize=8, label='Run 1', alpha=0.7)
plt.plot(delays_run2, throughput_run2, 'bs-', linewidth=2, markersize=8, label='Run 2', alpha=0.7)
plt.plot(delays_run3, throughput_run3, 'g^-', linewidth=2, markersize=8, label='Run 3', alpha=0.7)
plt.plot(delays_run4, throughput_run4, 'md-', linewidth=2, markersize=8, label='Run 4', alpha=0.7)
plt.plot(delays_run5, throughput_run5, 'cv-', linewidth=2, markersize=8, label='Run 5', alpha=0.7)
# plt.plot(delays_run6, throughput_run6, 'yo-', linewidth=2, markersize=8, label='Run 6', alpha=0.7)  # Uncomment for Run 6
# plt.plot(delays_run7, throughput_run7, 'ks-', linewidth=2, markersize=8, label='Run 7', alpha=0.7)  # Uncomment for Run 7
# plt.plot(delays_run8, throughput_run8, color='orange', marker='^', linestyle='-', linewidth=2, markersize=8, label='Run 8', alpha=0.7)  # Uncomment for Run 8
# plt.plot(delays_run9, throughput_run9, color='brown', marker='s', linestyle='-', linewidth=2, markersize=8, label='Run 9', alpha=0.7)  # Uncomment for Run 9
# plt.plot(delays_run10, throughput_run10, color='purple', marker='p', linestyle='-', linewidth=2, markersize=8, label='Run 10', alpha=0.7)  # Uncomment for Run 10

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
plt.savefig('throughput_vs_delay_comparison.png', dpi=300, bbox_inches='tight')
print("Plot saved as 'throughput_vs_delay_comparison.png'")

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

# # Uncomment for Run 6 statistics
# print(f"\nRun 6 - Throughput Statistics:")
# print(f"  Max: {max(throughput_run6):.2f} bytes/s at {delays_run6[throughput_run6.index(max(throughput_run6))]}ms delay")
# print(f"  Min: {min(throughput_run6):.2f} bytes/s at {delays_run6[throughput_run6.index(min(throughput_run6))]}ms delay")
# print(f"  Avg (excluding 0ms): {np.mean(throughput_run6[:-1]):.2f} bytes/s")

# # Uncomment for additional runs (Run 7-10) as needed

plt.show()
